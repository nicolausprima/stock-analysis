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

    # Stochastic Oscillator Embedding ([-1, 1])
    stoch_k = df.get('Stoch_K', pd.Series(50, index=df.index)).fillna(50)
    embeddings['Embed_Stoch_Norm'] = (stoch_k - 50.0) / 50.0

    # Williams %R Embedding ([-1, 1])
    williams_r = df.get('Williams_R', pd.Series(-50, index=df.index)).fillna(-50)
    embeddings['Embed_Williams_Norm'] = (williams_r + 50.0) / 50.0

    # 2. Trend & Curve Shape Embeddings
    close = df.get('Close', pd.Series(0, index=df.index)).fillna(0)
    sma20 = df.get('SMA_20', close).replace(0, np.nan).fillna(close)
    sma50 = df.get('SMA_50', close).replace(0, np.nan).fillna(close)

    embeddings['Embed_SMA20_Ratio'] = (close - sma20) / sma20
    embeddings['Embed_SMA50_Ratio'] = (close - sma50) / sma50

    # EMA 12 vs 26 Cross Embedding
    ema12 = df.get('EMA_12', close).fillna(close)
    ema26 = df.get('EMA_26', close).fillna(close)
    embeddings['Embed_EMA_Cross'] = (ema12 - ema26) / (close + 1e-9)
    
    # ADX Trend Strength Normalization (>25 = strong trend)
    adx = df.get('ADX_14', pd.Series(20, index=df.index)).fillna(20)
    embeddings['Embed_ADX_Norm'] = (adx - 25.0) / 25.0

    # 3. Volatility & Risk Embeddings
    atr = df.get('ATR_14', pd.Series(0, index=df.index)).fillna(0)
    embeddings['Embed_Volatility_ATR'] = (atr / close).fillna(0)

    # Commodity Channel Index Embedding
    cci = df.get('CCI_20', pd.Series(0, index=df.index)).fillna(0)
    embeddings['Embed_CCI_Norm'] = np.clip(cci / 100.0, -3.0, 3.0)

    # 4. Multi-period Return Velocity Embeddings
    embeddings['Embed_Return_1d'] = df.get('Return_1d', pd.Series(0, index=df.index)).fillna(0)
    embeddings['Embed_Return_2d'] = df.get('Return_2d', pd.Series(0, index=df.index)).fillna(0)
    embeddings['Embed_Return_3d'] = df.get('Return_3d', pd.Series(0, index=df.index)).fillna(0)
    embeddings['Embed_Return_5d'] = df.get('Return_5d', pd.Series(0, index=df.index)).fillna(0)

    # 5. Liquidity & Volume Profile Embeddings (RVOL & Volume Z-Score & MFI)
    volume = df.get('Volume', pd.Series(1, index=df.index)).fillna(1)
    embeddings['Embed_Log_Volume'] = np.log1p(volume)
    embeddings['Embed_RVOL'] = np.clip(df.get('RVOL', pd.Series(1.0, index=df.index)).fillna(1.0) - 1.0, -1.0, 5.0)
    embeddings['Embed_Volume_Z'] = np.clip(df.get('Volume_Z', pd.Series(0.0, index=df.index)).fillna(0.0), -3.0, 5.0)
    
    # Money Flow Index (MFI) Embedding ([-1, 1])
    mfi = df.get('MFI_14', pd.Series(50, index=df.index)).fillna(50)
    embeddings['Embed_MFI_Norm'] = (mfi - 50.0) / 50.0
    
    # 6. Market Relative Embedding
    embeddings['Embed_IHSG_Return'] = df.get('IHSG_Return', pd.Series(0, index=df.index)).fillna(0)

    # Bersihkan inf / NaN
    embeddings.replace([np.inf, -np.inf], np.nan, inplace=True)
    embeddings.fillna(0.0, inplace=True)

    return embeddings
