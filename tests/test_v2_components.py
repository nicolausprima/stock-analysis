import pytest
import pandas as pd
import polars as pl
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.database.duckdb_market import add_technical_indicators_polars, save_daily_prices_polars, get_ticker_history_polars
from src.database.duckdb_fundamental import save_fundamental, get_fundamental
from src.explainability.shap_explainer import explain_single_prediction, _get_feature_columns
from src.agents.multi_agent_v2 import MultiAgentSystemV2

def test_duckdb_fundamental_save_and_get():
    test_ticker = "TEST_TICKER.JK"
    data = {
        "per": 12.5,
        "pbv": 1.8,
        "roe": 0.18,
        "debt_to_equity": 85.0,
        "market_cap": 50000000000,
        "dividend_yield": 0.04,
        "revenue_growth": 0.15
    }
    save_fundamental(test_ticker, data)
    res = get_fundamental(test_ticker)
    assert res["per"] == 12.5
    assert res["pbv"] == 1.8
    assert res["roe"] == 0.18

def test_duckdb_market_polars_indicators():
    df = pl.DataFrame({
        "date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
        "open": [100.0, 102.0, 101.0, 105.0, 106.0],
        "high": [103.0, 104.0, 106.0, 108.0, 109.0],
        "low": [99.0, 101.0, 100.0, 103.0, 104.0],
        "close": [102.0, 101.0, 105.0, 107.0, 108.0],
        "volume": [1000.0, 1500.0, 1200.0, 1800.0, 2000.0]
    })
    res = add_technical_indicators_polars(df)
    assert "RSI_14" in res.columns
    assert "MACD" in res.columns
    assert "MACD_Signal" in res.columns
    assert "MACD_Diff" in res.columns
    assert "BB_High" in res.columns
    assert "BB_Low" in res.columns
    assert "ADX_14" in res.columns
    assert "Stoch_K" in res.columns
    assert len(res) == 5

def test_shap_explain_single_prediction():
    cols = _get_feature_columns()
    assert len(cols) == 20
    df = pd.DataFrame([{c: 1.0 for c in cols}])
    res = explain_single_prediction("BBCA", df)
    assert res["ticker"] == "BBCA"
    assert "top_contributors" in res
    assert len(res["top_contributors"]) > 0

def test_multi_agent_system_v2_consensus():
    sys = MultiAgentSystemV2()
    payload = {
        "ticker": "BBCA.JK",
        "close_price": 10000,
        "target_price": 10500,
        "stop_loss": 9800,
        "rsi": 55.0,
        "macd_signal": "BULLISH",
        "trend": "UPTREND",
        "probability": 75.0
    }
    consensus = sys.generate_consensus(payload, macro_info={"mode": "NORMAL", "mode_badge": "NORMAL"})
    assert consensus["ticker"] == "BBCA"
    assert "technical_view" in consensus
    assert "fundamental_view" in consensus
    assert "bull_case" in consensus
    assert "bear_case" in consensus
    assert "risk_verdict" in consensus
    assert consensus["engine"] == "multi-agent-v2"
    assert "Driver model utama" in consensus["consensus_summary"] or "Konsensus" in consensus["consensus_summary"]
