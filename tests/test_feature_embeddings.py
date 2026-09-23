import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.features.embedding import extract_chart_feature_embeddings
from src.features.technical_indicators import add_technical_indicators


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
        'Embed_SMA50_Ratio', 'Embed_ADX_Norm', 'Embed_Volatility_ATR', 'Embed_Return_1d',
        'Embed_Return_2d', 'Embed_Return_3d', 'Embed_Return_5d',
        'Embed_Log_Volume', 'Embed_RVOL', 'Embed_Volume_Z', 'Embed_IHSG_Return'
    ]
    
    for col in expected_embed_cols:
        assert col in embeds.columns, f"Kolom embedding {col} hilang"

def test_no_inf_or_nan_in_embeddings_after_warmup_drop():
    from src.features.technical_indicators import drop_warmup_rows
    df = create_sample_indicator_df(60)
    embeds = extract_chart_feature_embeddings(df)
    # S-5: warm-up NaN MERAMBAT ke Embed_* (bukan fill-zero); caller drop.
    assert embeds["Embed_RSI_Norm"].iloc[:13].isna().all(), "warm-up NaN must propagate"
    kept = drop_warmup_rows(df)
    emb_kept = embeds.loc[kept.index]
    assert not emb_kept.isna().any().any(), "post-warmup embeddings must be NaN-free"
    assert not np.isinf(emb_kept.values).any(), "Terdapat nilai Inf pada matriks Feature Embedding"


def test_embedding_strict_warmup_guard():
    import pytest

    df = create_sample_indicator_df(60)
    with pytest.raises(ValueError):
        extract_chart_feature_embeddings(df, strict_warmup=True)
