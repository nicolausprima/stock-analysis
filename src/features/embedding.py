import numpy as np
import pandas as pd

def extract_chart_feature_embeddings(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ekstraksi Vektor Chart & Stock Feature Embedding.
    Menggantikan One-Hot Encoding Ticker kaku (Tick_BBCA) dengan representasi
    karakteristik numerik umum yang berlaku untuk 500+ saham di BEI.
    """
    embeddings = pd.DataFrame(index=df.index)

    # 1. Momentum & Oscillation Embeddings
    rsi = df.get('RSI_14', pd.Series(50, index=df.index)).fillna(50)
    embeddings['Embed_RSI_Norm'] = (rsi - 50.0) / 50.0
    embeddings['Embed_MACD_Diff'] = df.get('MACD_Diff', pd.Series(0, index=df.index)).fillna(0)

    # 2. Trend & Curve Shape Embeddings
    close = df.get('Close', pd.Series(0, index=df.index)).fillna(0)
    sma20 = df.get('SMA_20', close).replace(0, np.nan).fillna(close)
    sma50 = df.get('SMA_50', close).replace(0, np.nan).fillna(close)

    embeddings['Embed_SMA20_Ratio'] = (close - sma20) / sma20
    embeddings['Embed_SMA50_Ratio'] = (close - sma50) / sma50

    # 3. Volatility & Risk Embeddings
    atr = df.get('ATR_14', pd.Series(0, index=df.index)).fillna(0)
    embeddings['Embed_Volatility_ATR'] = (atr / close).fillna(0)

    # 4. Multi-period Return Velocity Embeddings
    embeddings['Embed_Return_1d'] = df.get('Return_1d', pd.Series(0, index=df.index)).fillna(0)
    embeddings['Embed_Return_2d'] = df.get('Return_2d', pd.Series(0, index=df.index)).fillna(0)
    embeddings['Embed_Return_3d'] = df.get('Return_3d', pd.Series(0, index=df.index)).fillna(0)
    embeddings['Embed_Return_5d'] = df.get('Return_5d', pd.Series(0, index=df.index)).fillna(0)

    # 5. Liquidity & Volume Profile Embeddings
    volume = df.get('Volume', pd.Series(1, index=df.index)).fillna(1)
    embeddings['Embed_Log_Volume'] = np.log1p(volume)
    
    # 6. Market Relative Embedding
    embeddings['Embed_IHSG_Return'] = df.get('IHSG_Return', pd.Series(0, index=df.index)).fillna(0)

    # Bersihkan inf / NaN
    embeddings.replace([np.inf, -np.inf], np.nan, inplace=True)
    embeddings.fillna(0.0, inplace=True)

    return embeddings
