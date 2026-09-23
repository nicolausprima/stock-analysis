import json
import logging
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from dashboard.backend.yf_client import download_with_timeout

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from src.config import PRICE_DATA_DIR, PROCESSED_DATA_DIR, PROFIT_THRESHOLD, TICKERS
from src.features.labels import add_open_to_close_label
from src.features.technical_indicators import add_technical_indicators, drop_warmup_rows

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Label contract (AI-02/AI-03): next-session open-to-close, threshold +3%.
# label(date t) = (Open[t+1] ... Close[t+1]) known only AFTER t+1 close.
# Serving horizon must match: "buy at next open, TP +3% intraday".
TARGET_FORMULA = "(Next_Close - Next_Open) / Next_Open >= 0.03"
TARGET_HORIZON = "next-session open-to-close (intraday, 1 bar)"
FUTURE_COLS = ['Next_Day_Open', 'Next_Day_Close', 'Next_Day_Return']


def build_features_for_ticker(ticker: str, ihsg_returns: pd.DataFrame) -> pd.DataFrame:
    file_path = PRICE_DATA_DIR / f"{ticker}.csv"
    if not file_path.exists():
        logging.warning(f"Data for {ticker} not found. Skipping.")
        return pd.DataFrame()

    df = pd.read_csv(file_path, index_col='Date', parse_dates=True)
    if df.empty:
        return pd.DataFrame()

    # 1. Tambahkan indikator teknikal & volume (LAMA)
    df = add_technical_indicators(df)

    # 2. FASE 3: Lagged Returns (Sejarah masa lalu)
    df['Return_1d'] = df['Close'].pct_change(1, fill_method=None)
    df['Return_2d'] = df['Close'].pct_change(2, fill_method=None)
    df['Return_3d'] = df['Close'].pct_change(3, fill_method=None)
    df['Return_5d'] = df['Close'].pct_change(5, fill_method=None)

    # 3. FASE 3: Day of Week (0=Senin, 4=Jumat)
    df['Day_of_Week'] = df.index.dayofweek

    # 4. FASE 3: IHSG Return
    # Pastikan zona waktu dihilangkan agar bisa di-join
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    df = df.join(ihsg_returns, how='left')
    # Kalender libur beda (AI-06): benchmark flat 0 HANYA untuk kolom IHSG
    # (bukan indikator). Guard join kosong: join di atas no-op bila
    # ihsg_returns kosong sehingga kolom belum ada -> buat 0.0 eksplisit.
    if 'IHSG_Return' in df.columns:
        df['IHSG_Return'] = df['IHSG_Return'].fillna(0)
    else:
        df['IHSG_Return'] = 0.0

    # 5. Target Label day-trading (S-4): helper label tunggal, sama dgn notebook
    # sel4. Open[t+1]->Close[t+1] >= threshold; baris akhir tanpa masa depan
    # di-drop (bukan label 0) di dalam helper.
    df = add_open_to_close_label(df, threshold=PROFIT_THRESHOLD)

    # 6. Ticker identitas
    df['Ticker'] = ticker

    # Drop warm-up indikator (AI-06): jangan isi nol. Drop baris inti-NaN dulu,
    # lalu drop sisa NaN fitur (bukan kolom future).
    df = drop_warmup_rows(df)
    features_to_check = [col for col in df.columns if col not in FUTURE_COLS + ['Target']]
    df.dropna(subset=features_to_check, inplace=True)

    # AI-02: kolom masa depan TIDAK BOLEH keluar dari builder (label leak).
    df.drop(columns=[c for c in FUTURE_COLS if c in df.columns], inplace=True)

    return df


def write_model_card(out_dir, feature_cols, n_rows, cutoff=None,
                     embargo_days=5, extra=None) -> str:
    """Tulis model_card.json: definisi target, horizon, cutoff, daftar fitur."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    card = {
        "target_formula": f"{TARGET_FORMULA} (PROFIT_THRESHOLD={PROFIT_THRESHOLD})",
        "horizon": TARGET_HORIZON,
        "cutoff": str(cutoff) if cutoff is not None else None,
        "embargo_days": embargo_days,
        "feature_cols": list(feature_cols),
        "n_rows": int(n_rows),
        "generated_on": date.today().isoformat(),
    }
    if extra:
        card.update(extra)
    path = out_dir / "model_card.json"
    path.write_text(json.dumps(card, indent=2), encoding="utf-8")
    return str(path)


def main():
    all_features = []

    logging.info("Fetching IHSG (^JKSE) data...")
    ihsg = download_with_timeout('^JKSE', period='10y', progress=False)

    if isinstance(ihsg.columns, pd.MultiIndex):
        close_col = ('Close', '^JKSE') if ('Close', '^JKSE') in ihsg.columns else ihsg.columns[0]
        ihsg_close = ihsg[close_col]
    else:
        ihsg_close = ihsg['Close']

    ihsg_returns = pd.DataFrame(index=ihsg.index)
    ihsg_returns['IHSG_Return'] = ihsg_close.pct_change()

    if ihsg_returns.index.tz is not None:
        ihsg_returns.index = ihsg_returns.index.tz_localize(None)

    logging.info(f"Building features for {len(TICKERS)} tickers...")
    for ticker in TICKERS:
        df_features = build_features_for_ticker(ticker, ihsg_returns)
        if not df_features.empty:
            all_features.append(df_features)

    if not all_features:
        logging.error("No features built. Make sure data is fetched first.")
        return

    final_df = pd.concat(all_features)
    final_df.sort_index(inplace=True)

    # AI-02: jangan simpan kolom future ke artefak.
    final_df.drop(columns=[c for c in FUTURE_COLS if c in final_df.columns], inplace=True)

    output_path = PROCESSED_DATA_DIR / "feature_matrix.csv"
    final_df.to_csv(output_path)

    feature_cols = [c for c in final_df.columns if c not in ('Target', 'Ticker')]
    write_model_card(PROCESSED_DATA_DIR, feature_cols, len(final_df),
                     cutoff=str(final_df.index.max().date()) if len(final_df) else None)

    logging.info(f"Successfully saved feature matrix to {output_path}")
    logging.info(f"Total rows: {len(final_df)}, Total columns: {len(final_df.columns)}")

    valid_targets = final_df['Target'].dropna()
    label_dist = valid_targets.value_counts(normalize=True) * 100
    logging.info(f"Label Distribution (%):\n{label_dist}")

if __name__ == "__main__":
    main()
