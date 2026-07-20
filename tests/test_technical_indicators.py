import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.features.technical_indicators import add_technical_indicators

def create_sample_ohlcv_data(num_rows=60):
    """Membuat Dataframe sintesis OHLCV valid untuk testing."""
    np.random.seed(42)
    dates = pd.date_range(start="2026-01-01", periods=num_rows, freq="D")
    
    close = 1000 + np.cumsum(np.random.randn(num_rows) * 10)
    high = close + np.random.uniform(5, 20, num_rows)
    low = close - np.random.uniform(5, 20, num_rows)
    open_p = low + (high - low) * np.random.uniform(0.1, 0.9, num_rows)
    volume = np.random.uniform(100000, 5000000, num_rows)
    
    return pd.DataFrame({
        'Open': open_p,
        'High': high,
        'Low': low,
        'Close': close,
        'Volume': volume
    }, index=dates)

def test_add_technical_indicators_returns_dataframe():
    df = create_sample_ohlcv_data(60)
    res = add_technical_indicators(df)
    
    assert isinstance(res, pd.DataFrame)
    assert len(res) == 60

def test_technical_indicator_columns_present():
    df = create_sample_ohlcv_data(60)
    res = add_technical_indicators(df)
    
    expected_cols = [
        'OBV', 'ADI', 'VWAP', 'RSI_14', 'MACD', 'MACD_Signal', 
        'MACD_Diff', 'BB_High', 'BB_Low', 'BB_Mid', 'ATR_14', 'SMA_20', 'SMA_50'
    ]
    
    for col in expected_cols:
        assert col in res.columns, f"Kolom {col} hilang dari output indikator"

def test_rsi_bounds():
    df = create_sample_ohlcv_data(60)
    res = add_technical_indicators(df)
    rsi_valid = res['RSI_14'].dropna()
    
    assert (rsi_valid >= 0).all() and (rsi_valid <= 100).all(), "Nilai RSI berada di luar rentang 0-100"

def test_moving_averages_calculation():
    df = create_sample_ohlcv_data(60)
    res = add_technical_indicators(df)
    
    # Baris ke-20 harus memiliki SMA_20 yang tidak NaN
    assert not np.isnan(res['SMA_20'].iloc[20])
