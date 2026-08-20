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


def test_extended_technical_indicators_presence_and_bounds():
    np.random.seed(42)
    n = 60
    dates = pd.date_range("2026-01-01", periods=n, freq="D")
    close = 5000 + np.cumsum(np.random.randn(n) * 20)
    high = close + np.random.uniform(5, 30, n)
    low = close - np.random.uniform(5, 30, n)
    open_p = close + np.random.uniform(-10, 10, n)
    volume = np.random.uniform(500000, 2000000, n)

    df = pd.DataFrame({"Open": open_p, "High": high, "Low": low, "Close": close, "Volume": volume}, index=dates)
    df = add_technical_indicators(df)

    # Check new columns presence
    expected_new = ["Stoch_K", "Stoch_D", "MFI_14", "EMA_12", "EMA_26", "Williams_R", "CCI_20"]
    for col in expected_new:
        assert col in df.columns, f"Indikator {col} tidak ditemukan pada dataframe"

    # Check value bounds
    assert (df["Stoch_K"] >= 0).all() and (df["Stoch_K"] <= 100).all()
    assert (df["MFI_14"] >= 0).all() and (df["MFI_14"] <= 100).all()
    assert (df["Williams_R"] >= -100).all() and (df["Williams_R"] <= 0).all()


def test_extended_feature_embeddings_no_nan():
    np.random.seed(42)
    n = 60
    dates = pd.date_range("2026-01-01", periods=n, freq="D")
    close = 5000 + np.cumsum(np.random.randn(n) * 20)
    high = close + 15
    low = close - 15
    open_p = close - 5
    volume = np.random.uniform(500000, 2000000, n)

    df = pd.DataFrame({"Open": open_p, "High": high, "Low": low, "Close": close, "Volume": volume}, index=dates)
    df = add_technical_indicators(df)
    df['Return_1d'] = df['Close'].pct_change(1, fill_method=None)
    df['Return_2d'] = df['Close'].pct_change(2, fill_method=None)
    df['Return_3d'] = df['Close'].pct_change(3, fill_method=None)
    df['Return_5d'] = df['Close'].pct_change(5, fill_method=None)
    df['IHSG_Return'] = 0.001

    embeds = extract_chart_feature_embeddings(df)

    assert "Embed_Stoch_Norm" in embeds.columns
    assert "Embed_MFI_Norm" in embeds.columns
    assert "Embed_EMA_Cross" in embeds.columns
    assert "Embed_Williams_Norm" in embeds.columns
    assert "Embed_CCI_Norm" in embeds.columns

    assert not embeds.isna().any().any(), "Terdapat NaN di feature embeddings"
    assert not np.isinf(embeds.values).any(), "Terdapat Inf di feature embeddings"
