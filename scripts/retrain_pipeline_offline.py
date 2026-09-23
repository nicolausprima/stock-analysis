"""Retrain offline pipeline tunggal (S-1 ulang pasca S-4/S-5).

Sumber: data/raw/price/*.csv lokal (tanpa network; IHSG_Return=0.0 flat
per kebijakan AI-06 bila benchmark tak tersedia). Kode terbaru:
add_technical_indicators + add_open_to_close_label (labels.py) +
extract_chart_feature_embeddings (propagasi NaN, tanpa fillna) +
drop_warmup_rows + cutoff quantile(0.8) tanggal + embargo 5B +
median-train-only + StandardScaler + XGB (param notebook 03).

Output:
  data/processed/feature_matrix.csv (X bersih + Target + Ticker, sort tanggal)
  data/processed/X_train.csv X_test.csv y_train.csv y_test.csv
  data/processed/model_card.json + models/model_card.json (identik)
  models/best_xgboost_optuna.pkl + models/standard_scaler.pkl
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import PROFIT_THRESHOLD
from src.features.embedding import extract_chart_feature_embeddings
from src.features.labels import add_open_to_close_label
from src.features.technical_indicators import (
    add_technical_indicators,
    drop_warmup_rows,
)

FEATURE_COLS = [
    "RSI_14", "MACD_Diff", "SMA_20", "SMA_50", "ATR_14", "ADX_14", "RVOL", "Volume_Z",
    "Return_1d", "Return_2d", "Return_3d", "Return_5d",
    "Embed_RSI_Norm", "Embed_MACD_Diff", "Embed_SMA20_Ratio",
    "Embed_SMA50_Ratio", "Embed_ADX_Norm", "Embed_Volatility_ATR",
    "Embed_Return_1d", "Embed_Return_2d", "Embed_Return_3d", "Embed_Return_5d",
    "Embed_Log_Volume", "Embed_RVOL", "Embed_Volume_Z", "Embed_IHSG_Return",
]
CORE_WARMUP = ["RSI_14", "MACD_Diff", "SMA_20", "SMA_50", "ATR_14", "ADX_14", "RVOL", "Volume_Z"]
FUTURE_COLS = ["Next_Day_Open", "Next_Day_Close", "Next_Day_Return"]


def build_one(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, index_col="Date", parse_dates=True)
    if df.empty:
        return pd.DataFrame()
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    if len(df) < 100:
        return pd.DataFrame()
    df = add_technical_indicators(df)
    df["Return_1d"] = df["Close"].pct_change(1, fill_method=None)
    df["Return_2d"] = df["Close"].pct_change(2, fill_method=None)
    df["Return_3d"] = df["Close"].pct_change(3, fill_method=None)
    df["Return_5d"] = df["Close"].pct_change(5, fill_method=None)
    df["Day_of_Week"] = df.index.dayofweek
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df["IHSG_Return"] = 0.0  # offline: benchmark flat-0 (AI-06)
    df = add_open_to_close_label(df, threshold=PROFIT_THRESHOLD)  # drop baris akhir
    df["Ticker"] = csv_path.stem
    df = drop_warmup_rows(df)
    feats = [c for c in df.columns if c not in FUTURE_COLS + ["Target"]]
    df = df.dropna(subset=feats)
    df = df.drop(columns=[c for c in FUTURE_COLS if c in df.columns])
    return df


def main() -> None:
    price_dir = PROJECT_ROOT / "data" / "raw" / "price"
    processed = PROJECT_ROOT / "data" / "processed"
    models_dir = PROJECT_ROOT / "models"
    processed.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    frames = []
    for csv_path in sorted(price_dir.glob("*.csv")):
        try:
            out = build_one(csv_path)
        except Exception as e:
            print(f"[SKIP] {csv_path.stem}: {e}")
            continue
        if not out.empty:
            frames.append(out)
    full = pd.concat(frames).sort_index()
    full = full.drop(columns=[c for c in FUTURE_COLS if c in full.columns])
    assert not any(c.startswith("Tick_") for c in full.columns)
    assert not any(c.startswith("Next_Day_") for c in full.columns)

    embed = extract_chart_feature_embeddings(full)
    combined = pd.concat([full, embed], axis=1)
    # Align positionally (duplicate dates across tickers: label .loc explodes).
    combined["__Target"] = full["Target"].astype(int).to_numpy()
    combined["__Ticker"] = full["Ticker"].astype(object).to_numpy()
    for c in FUTURE_COLS:
        if c in combined.columns and not c.startswith("__"):
            combined.drop(columns=[c], inplace=True)
    combined.replace([np.inf, -np.inf], np.nan, inplace=True)
    combined = combined.dropna(subset=[c for c in CORE_WARMUP if c in combined.columns])
    combined = combined.sort_index()

    X = combined[FEATURE_COLS]
    y = combined["__Target"].astype(int)
    tickers = combined["__Ticker"].astype(str)
    all_dates = pd.Series(X.index.sort_values())
    cutoff = all_dates.quantile(0.8)
    embargo = pd.tseries.offsets.BDay(5)
    idx = X.index
    lo = np.asarray(idx < (cutoff - embargo))
    hi = np.asarray(idx > (cutoff + embargo))
    X_train, X_test = X.iloc[lo], X.iloc[hi]
    y_train, y_test = y.iloc[lo], y.iloc[hi]
    dropped_gap = len(X) - len(X_train) - len(X_test)

    medians = X_train.median()
    X_train = X_train.fillna(medians)
    X_test = X_test.fillna(medians)
    assert X_train.notna().all().all() and X_test.notna().all().all()

    # feature_matrix bersih: X penuh pasca-warmup + Target + Ticker
    fm = X.copy()
    fm["Target"] = y.to_numpy()
    fm["Ticker"] = tickers.to_numpy()
    fm.to_csv(processed / "feature_matrix.csv")
    X_train.to_csv(processed / "X_train.csv")
    X_test.to_csv(processed / "X_test.csv")
    y_train.to_csv(processed / "y_train.csv", header=True)
    y_test.to_csv(processed / "y_test.csv", header=True)

    # model: scaler fit train-only + XGB (param notebook 03)
    ratio = float((y_train == 0).sum()) / max(int((y_train == 1).sum()), 1)
    scaler = StandardScaler()
    Xtr_s = scaler.fit_transform(X_train)
    Xte_s = scaler.transform(X_test)
    model = XGBClassifier(
        n_estimators=120, max_depth=4, learning_rate=0.03,
        subsample=0.8, colsample_bytree=0.8,
        scale_pos_weight=min(ratio, 3.0), random_state=42,
    )
    model.fit(pd.DataFrame(Xtr_s, columns=FEATURE_COLS), y_train)
    y_pred = model.predict(pd.DataFrame(Xte_s, columns=FEATURE_COLS))
    cm = confusion_matrix(y_test, y_pred).tolist()
    rep = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
    joblib.dump(model, models_dir / "best_xgboost_optuna.pkl")
    joblib.dump(scaler, models_dir / "standard_scaler.pkl")

    card = {
        "target_formula": f"(Next_Close - Next_Open) / Next_Open >= {PROFIT_THRESHOLD}",
        "horizon": "next-session open-to-close (intraday, 1 bar)",
        "cutoff": str(pd.Timestamp(cutoff).date()),
        "embargo_days": 5,
        "feature_cols": FEATURE_COLS,
        "n_rows": len(X),
        "train_rows": len(X_train),
        "test_rows": len(X_test),
        "dropped_gap_rows": int(dropped_gap),
        "train_date_min": str(X_train.index.min().date()),
        "train_date_max": str(X_train.index.max().date()),
        "test_date_min": str(X_test.index.min().date()),
        "test_date_max": str(X_test.index.max().date()),
        "tickers": int(tickers.nunique()),
        "label_policy": "last bar dropped (no future), warm-up dropped, median-train-only",
        "imbalance_ratio": round(ratio, 4),
        "test_precision_1": round(float(rep["1"]["precision"]), 4),
        "test_recall_1": round(float(rep["1"]["recall"]), 4),
        "test_f1_1": round(float(rep["1"]["f1-score"]), 4),
        "test_confusion_matrix": cm,
        "generated_on": datetime.now(timezone.utc).date().isoformat(),
    }
    (processed / "model_card.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
    (models_dir / "model_card.json").write_text(json.dumps(card, indent=2), encoding="utf-8")

    print(f"tickers_ok={tickers.nunique()} n_total={len(X)}")
    print(f"cutoff={pd.Timestamp(cutoff).date()} embargo=5B "
          f"train={X_train.shape} test={X_test.shape} gap={dropped_gap}")
    print(f"cols={len(FEATURE_COLS)} no_tick={not any(c.startswith('Tick_') for c in FEATURE_COLS)}")
    print("test report:\n" + classification_report(y_test, y_pred, zero_division=0))
    print(f"scaler_features={list(scaler.feature_names_in_)}")


if __name__ == "__main__":
    main()
