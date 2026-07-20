import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.features.technical_indicators import add_technical_indicators
from src.features.embedding import extract_chart_feature_embeddings

def create_sample_indicator_df(num_rows=60):
    np.random.seed(42)
    dates = pd.date_range(start="2026-01-01", periods=num_rows, freq="D")
    
    close = 1000 + np.cumsum(np.random.randn(num_rows) * 10)
    high = close + 10
    low = close - 10
    open_p = close - 2
    volume = np.random.uniform(100000, 5000000, num_rows)
    
    df = pd.DataFrame({
        'Open': open_p, 'High': high, 'Low': low, 'Close': close, 'Volume': volume
    }, index=dates)
    
    df = add_technical_indicators(df)
    df['Return_1d'] = df['Close'].pct_change(1, fill_method=None)
    df['Return_2d'] = df['Close'].pct_change(2, fill_method=None)
    df['Return_3d'] = df['Close'].pct_change(3, fill_method=None)
    df['Return_5d'] = df['Close'].pct_change(5, fill_method=None)
    df['IHSG_Return'] = np.random.uniform(-0.01, 0.01, num_rows)
    
    return df

def test_feature_embeddings_shape_and_columns():
    df = create_sample_indicator_df(60)
    embeds = extract_chart_feature_embeddings(df)
    
    assert isinstance(embeds, pd.DataFrame)
    assert len(embeds) == 60
    
    expected_embed_cols = [
        'Embed_RSI_Norm', 'Embed_MACD_Diff', 'Embed_SMA20_Ratio',
        'Embed_SMA50_Ratio', 'Embed_Volatility_ATR', 'Embed_Return_1d',
        'Embed_Return_2d', 'Embed_Return_3d', 'Embed_Return_5d',
        'Embed_Log_Volume', 'Embed_IHSG_Return'
    ]
    
    for col in expected_embed_cols:
        assert col in embeds.columns, f"Kolom embedding {col} hilang"

def test_no_inf_or_nan_in_embeddings():
    df = create_sample_indicator_df(60)
    embeds = extract_chart_feature_embeddings(df)
    
    assert not embeds.isna().any().any(), "Terdapat nilai NaN pada matriks Feature Embedding"
    assert not np.isinf(embeds.values).any(), "Terdapat nilai Inf pada matriks Feature Embedding"
