import numpy as np
import pandas as pd


def extract_chart_feature_embeddings(
    df: pd.DataFrame,
    *,
    strict_warmup: bool = False,
) -> pd.DataFrame:
    """Ekstraksi Vektor Chart & Stock Feature Embedding.
    Menggantikan One-Hot Encoding Ticker kaku (Tick_BBCA) dengan representasi
    karakteristik numerik umum yang berlaku untuk 500+ saham di BEI.

    Warm-up policy S-5 (AI-06): default ``strict_warmup=False`` PROPAGASI NaN
    (bar warm-up indikator inti -> Embed_* NaN, bukan 0 netral). Final
    ``fillna(0.0)`` lama DIHAPUS agar tak sembunyikan warm-up. Caller WAJIB
    ``drop_warmup_rows`` / ``dropna`` atas kolom inti SEBELUM pakai output
    (contoh: notebook sel5 dropna ``core_warmup``; train split + median-impute
    residual). ``strict_warmup=True`` raise ``ValueError`` bila kolom inti
    masih NaN (guard untuk serve path).
    """
    from src.features.technical_indicators import CORE_INDICATORS
    if strict_warmup:
        core = [c for c in CORE_INDICATORS if c in df.columns]
        if core and df[core].isna().any().any():
            bad = [c for c in core if df[c].isna().any()]
            raise ValueError(f"warm-up NaN in core cols (refuse fill-zero): {bad}")
    embeddings = pd.DataFrame(index=df.index)

    # Helper S-5: kolom inti PROPAGASI NaN (warm-up), kolom absen -> netral.
    # Bedakan "kolom tak ada" (fallback netral) vs "warm-up NaN" (pertahankan
    # NaN agar caller drop/guard, bukan sinyal palsu 0).
    def _core(name, neutral):
        if name in df.columns:
            return df[name]  # NaN warm-up dibiarkan merambat ke Embed_*
        return pd.Series(neutral, index=df.index)

    # 1. Momentum & Oscillation Embeddings (inti -> NaN merambat)
    rsi = _core('RSI_14', 50.0)
    embeddings['Embed_RSI_Norm'] = (rsi - 50.0) / 50.0
    embeddings['Embed_MACD_Diff'] = _core('MACD_Diff', 0.0)

    # Stochastic Oscillator Embedding ([-1, 1])
    stoch_k = _core('Stoch_K', 50.0)
    embeddings['Embed_Stoch_Norm'] = (stoch_k - 50.0) / 50.0

    # Williams %R Embedding ([-1, 1])
    williams_r = _core('Williams_R', -50.0)
    embeddings['Embed_Williams_Norm'] = (williams_r + 50.0) / 50.0

    # 2. Trend & Curve Shape Embeddings (inti -> NaN merambat)
    close = df.get('Close', pd.Series(0, index=df.index)).fillna(0)
    sma20 = _core('SMA_20', np.nan)
    sma50 = _core('SMA_50', np.nan)
    if 'SMA_20' not in df.columns:
        sma20 = pd.Series(close, index=df.index)
    if 'SMA_50' not in df.columns:
        sma50 = pd.Series(close, index=df.index)

    embeddings['Embed_SMA20_Ratio'] = (close - sma20) / sma20
    embeddings['Embed_SMA50_Ratio'] = (close - sma50) / sma50

    # EMA 12 vs 26 Cross Embedding (inti -> NaN merambat bila EMA NaN)
    if 'EMA_12' in df.columns:
        ema12 = df['EMA_12']
    else:
        ema12 = pd.Series(close, index=df.index)
    if 'EMA_26' in df.columns:
        ema26 = df['EMA_26']
    else:
        ema26 = pd.Series(close, index=df.index)
    embeddings['Embed_EMA_Cross'] = (ema12 - ema26) / (close + 1e-9)

    # ADX Trend Strength Normalization (>25 = strong trend, inti)
    adx = _core('ADX_14', 20.0)
    embeddings['Embed_ADX_Norm'] = (adx - 25.0) / 25.0

    # 3. Volatility & Risk Embeddings (inti -> NaN merambat)
    atr = _core('ATR_14', np.nan)
    if 'ATR_14' not in df.columns:
        atr = pd.Series(0.0, index=df.index)
    embeddings['Embed_Volatility_ATR'] = atr / close

    # Commodity Channel Index Embedding (inti -> NaN merambat)
    cci = _core('CCI_20', np.nan)
    if 'CCI_20' not in df.columns:
        cci = pd.Series(0.0, index=df.index)
    embeddings['Embed_CCI_Norm'] = np.clip(cci / 100.0, -3.0, 3.0)

    # 4. Multi-period Return Velocity Embeddings (lag warm-up -> NaN merambat)
    embeddings['Embed_Return_1d'] = _core('Return_1d', 0.0)
    embeddings['Embed_Return_2d'] = _core('Return_2d', 0.0)
    embeddings['Embed_Return_3d'] = _core('Return_3d', 0.0)
    embeddings['Embed_Return_5d'] = _core('Return_5d', 0.0)

    # 5. Liquidity & Volume Profile Embeddings (RVOL/VolZ/MFI inti -> NaN merambat)
    volume = df.get('Volume', pd.Series(1, index=df.index)).fillna(1)
    embeddings['Embed_Log_Volume'] = np.log1p(volume)
    rvol = _core('RVOL', np.nan)
    if 'RVOL' not in df.columns:
        rvol = pd.Series(1.0, index=df.index)
    embeddings['Embed_RVOL'] = np.clip(rvol - 1.0, -1.0, 5.0)
    volz = _core('Volume_Z', np.nan)
    if 'Volume_Z' not in df.columns:
        volz = pd.Series(0.0, index=df.index)
    embeddings['Embed_Volume_Z'] = np.clip(volz, -3.0, 5.0)

    # Money Flow Index (MFI) Embedding ([-1, 1], inti -> NaN merambat)
    mfi = _core('MFI_14', 50.0)
    embeddings['Embed_MFI_Norm'] = (mfi - 50.0) / 50.0

    # 6. Market Relative Embedding (BUKAN indikator: benchmark flat-0, AI-06)
    embeddings['Embed_IHSG_Return'] = df.get('IHSG_Return', pd.Series(0, index=df.index)).fillna(0)

    # S-5: inf -> NaN, tapi JANGAN fillna(0). Warm-up NaN merambat ke Embed_*
    # agar caller drop (train) / guard strict_warmup (serve), bukan sinyal palsu.
    embeddings.replace([np.inf, -np.inf], np.nan, inplace=True)

    return embeddings
