"""AI & Data P0/P1 contract tests (TDD RED first).
Covers: AI-01 serve/train schema parity, AI-02 future-col leak + model card,
AI-04 date-cutoff split + embargo, AI-06 warm-up NaN (no blind fill-zero),
AI-07 fundamental NULL + as-of, AI-08 next-bar entry + equity curve + lot-100.
Offline: all network/DB access monkeypatched or avoided.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

TRAIN_SCHEMA = [
    'RSI_14', 'MACD_Diff', 'SMA_20', 'SMA_50', 'ATR_14', 'ADX_14', 'RVOL', 'Volume_Z',
    'Return_1d', 'Return_2d', 'Return_3d', 'Return_5d',
    'Embed_RSI_Norm', 'Embed_MACD_Diff', 'Embed_SMA20_Ratio',
    'Embed_SMA50_Ratio', 'Embed_ADX_Norm', 'Embed_Volatility_ATR',
    'Embed_Return_1d', 'Embed_Return_2d', 'Embed_Return_3d', 'Embed_Return_5d',
    'Embed_Log_Volume', 'Embed_RVOL', 'Embed_Volume_Z', 'Embed_IHSG_Return',
]


def _ohlcv(n=80, seed=7):
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    close = 1000 + np.cumsum(rng.normal(0, 8, n))
    high = close + np.abs(rng.normal(5, 3, n))
    low = close - np.abs(rng.normal(5, 3, n))
    open_p = low + (high - low) * 0.5
    vol = np.full(n, 1_000_000.0) + rng.normal(0, 10_000, n)
    return pd.DataFrame(
        {"Open": open_p, "High": high, "Low": low, "Close": close, "Volume": vol},
        index=dates,
    )


def test_ai06_indicators_leave_warmup_nan():
    """Warm-up RSI/MACD/BB/ATR must stay NaN, never filled with 0/median."""
    from src.features.technical_indicators import add_technical_indicators
    df = add_technical_indicators(_ohlcv(30))
    assert df["RSI_14"].iloc[:13].isna().all(), "RSI warm-up must be NaN"
    assert (df["RSI_14"].iloc[:13] != 0.0).all()
    assert df["ATR_14"].iloc[:13].isna().all(), "ATR warm-up must be NaN"
    assert df["BB_Mid"].iloc[:19].isna().all(), "BB warm-up must be NaN"
    # ADX pakai smoothing ganda: 27 bar pertama NaN (2*14-1).
    assert df["ADX_14"].iloc[:27].isna().all(), "ADX warm-up must be NaN"
    # After warm-up, values exist (60-row frame: SMA_50 still warming, RSI ready)
    df60 = add_technical_indicators(_ohlcv(60))
    assert df60["RSI_14"].iloc[-1] == df60["RSI_14"].iloc[-1]  # not NaN
    assert not (df60["RSI_14"].dropna() == 0.0).all()


def test_ai06_drop_warmup_helper():
    from src.features.technical_indicators import (
        CORE_INDICATORS,
        add_technical_indicators,
        drop_warmup_rows,
    )
    df = add_technical_indicators(_ohlcv(60))
    kept = drop_warmup_rows(df)
    assert len(kept) < len(df)
    assert kept[CORE_INDICATORS].notna().all().all()


def test_ai01_serve_matrix_matches_train_schema_and_order():
    """Serve matrix must equal scaler expected_cols order; no Tick_ cols; no fill-zero."""
    from src.features.embedding import extract_chart_feature_embeddings
    from src.features.technical_indicators import add_technical_indicators
    from src.screener import build_serve_matrix
    df = add_technical_indicators(_ohlcv(80))
    df["Return_1d"] = df["Close"].pct_change(1)
    df["Return_2d"] = df["Close"].pct_change(2)
    df["Return_3d"] = df["Close"].pct_change(3)
    df["Return_5d"] = df["Close"].pct_change(5)
    df["IHSG_Return"] = 0.001
    from src.features.technical_indicators import drop_warmup_rows
    df = drop_warmup_rows(df)
    emb = extract_chart_feature_embeddings(df)
    latest = df.iloc[-1:].copy()
    emb_latest = emb.iloc[-1:].copy()
    X = build_serve_matrix(latest, emb_latest, TRAIN_SCHEMA)
    assert list(X.columns) == TRAIN_SCHEMA, "column order must match train schema"
    assert not any(c.startswith("Tick_") for c in X.columns)
    assert X.notna().all().all(), "serve matrix must have no NaN after warm-up drop"


def test_ai01_serve_matrix_rejects_warmup_nan():
    """build_serve_matrix must raise on indicator NaN, not fill-zero it."""
    from src.screener import build_serve_matrix
    df = pd.DataFrame({"RSI_14": [np.nan]})
    emb = pd.DataFrame(index=df.index)
    try:
        build_serve_matrix(df, emb, ["RSI_14"])
    except ValueError:
        return
    raise AssertionError("expected ValueError for warm-up NaN")


def test_ai02_build_features_drops_future_columns(tmp_path, monkeypatch):
    """No Next_Day_* may leave the feature builder output."""
    import src.features.build_features as bf
    d = tmp_path / "prices"
    d.mkdir()
    df = _ohlcv(80)
    df.to_csv(d / "BBCA.JK.csv", index_label="Date")
    monkeypatch.setattr(bf, "PRICE_DATA_DIR", d)
    out = bf.build_features_for_ticker("BBCA.JK", pd.DataFrame())
    assert "Target" in out.columns
    assert not any(c.startswith("Next_Day_") for c in out.columns), \
        f"future leak: {[c for c in out.columns if c.startswith('Next_Day_')]}"


def test_ai02_model_card_writer(tmp_path):
    from src.features.build_features import write_model_card
    p = write_model_card(
        tmp_path, feature_cols=TRAIN_SCHEMA, n_rows=1000,
        cutoff="2024-06-01", embargo_days=5,
    )
    card = json.loads(Path(p).read_text())
    assert "target_formula" in card and "horizon" in card
    assert card["cutoff"] == "2024-06-01" and card["embargo_days"] == 5
    assert card["feature_cols"] == TRAIN_SCHEMA
    assert "0.03" in card["target_formula"]


def test_ai04_notebook_uses_date_cutoff_and_embargo():
    nb = json.loads((PROJECT_ROOT / "notebooks" / "02_Preprocessing.ipynb").read_text(encoding="utf-8"))
    src = "\n".join("".join(c.get("source", [])) for c in nb["cells"] if c.get("cell_type") == "code")
    assert "embargo" in src.lower(), "notebook must implement embargo gap"
    assert "cutoff" in src.lower() or "quantile(0.8" in src or "0.8" in src
    assert "sort" in src.lower(), "notebook must sort by date before split"
    assert "split_idx = int(len(X) * 0.8)" not in src, "positional 80% split must be gone"


def test_ai08_next_bar_entry_and_equity_curve():
    """Signal at bar i fills at open[i+1]; equity_curve has one entry per bar; lot-100."""
    from src.backtest.vectorized_backtest import simulate_sma_trades
    n = 120
    dates = pd.date_range("2024-01-01", periods=n, freq="B").to_numpy()
    # flat 100 (SMA20==SMA50) lalu rally -> cross-up di bar 60; rally terus
    # memaksa exit via TP +3%. Uptrend linear murni TIDAK hasilkan cross
    # (SMA20 selalu di atas SMA50) -> total_trades=0.
    closes = np.full(n, 100.0)
    closes[60:] = np.linspace(100, 140, n - 60)
    opens = closes * 1.001
    vols = np.full(n, 5_000_000.0)
    res = simulate_sma_trades(dates, opens, closes, vols, initial_capital=100_000_000.0)
    assert res["total_trades"] >= 1
    t0 = res["trade_history"][0]
    # entry must be next-bar open (incl slippage), not signal-bar close
    assert t0["entry_price"] > closes[t0["signal_idx"]] * 1.0
    assert abs(t0["entry_price"] / (opens[t0["signal_idx"] + 1] * 1.001) - 1.0) < 1e-9
    assert len(res["equity_curve"]) == n - 20 - 5 or len(res["equity_curve"]) == n, \
        f"equity_curve must cover every simulated bar, got {len(res['equity_curve'])}"
    assert t0["shares"] % 100 == 0, "shares must be lot-100 multiples"


def test_ai07_fundamental_missing_is_null_with_asof(monkeypatch):
    import src.collector.fundamental_collector as fc
    captured = {}

    monkeypatch.setattr(fc, "get_ticker_info", lambda t: {"trailingPE": 12.5})  # everything else missing
    monkeypatch.setattr(fc, "TICKERS", ["BBCA.JK"])
    monkeypatch.setattr(fc, "save_fundamental", lambda t, d: captured.update(d))
    fc.run_fundamental_collection()
    assert captured["per"] == 12.5
    assert captured["pbv"] is None, f"missing PBV must be NULL, got {captured['pbv']!r}"
    assert captured["roe"] is None
    assert captured.get("as_of"), "as-of date required"
