import pytest
import pandas as pd
from main_cli import execute_command, calculate_indicators, render_ascii_chart, _clean_text

def test_clean_text():
    raw = "🟡 MODE CAUTIOUS ⚡ LEADING ✅ OK ⚠️ WARNING"
    cleaned = _clean_text(raw)
    assert "[CAUTION]" in cleaned
    assert "[HOT]" in cleaned
    assert "[+]" in cleaned
    assert "[!]" in cleaned
    assert "🟡" not in cleaned

def test_calculate_indicators_structure():
    dates = pd.date_range("2026-01-01", periods=40, freq="D")
    prices = [1000 + i * 10 for i in range(40)]
    df = pd.DataFrame({
        "Open": prices,
        "High": [p + 20 for p in prices],
        "Low": [p - 10 for p in prices],
        "Close": prices,
        "Volume": [1000000 for _ in prices]
    }, index=dates)

    ind = calculate_indicators(df)
    assert "price" in ind
    assert "rsi" in ind
    assert "macd_signal" in ind
    assert "target_price" in ind
    assert "stop_loss" in ind
    assert "kelly_allocation" in ind
    assert ind["price"] == 1390.0
    assert ind["trend"] == "UPTREND"

def test_render_ascii_chart():
    prices = [100, 105, 102, 110, 115, 120]
    chart = render_ascii_chart(prices, height=5, width=20)
    assert isinstance(chart, str)
    assert "120" in chart
    assert "100" in chart

def test_cli_execute_command_help():
    assert execute_command("/help") is True
    assert execute_command("help") is True

def test_cli_execute_command_sizing():
    assert execute_command("/sizing BBCA 50000000") is True

def test_cli_execute_command_exit():
    assert execute_command("/exit") is False
    assert execute_command("quit") is False
