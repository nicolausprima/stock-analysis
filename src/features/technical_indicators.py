import numpy as np
import pandas as pd
import ta

# Indicators whose leading NaNs are pure warm-up (lookback not yet satisfied).
# Downstream code must DROP these rows for training, never fillna(0).
CORE_INDICATORS = [
    'RSI_14', 'MACD', 'MACD_Signal', 'MACD_Diff',
    'BB_High', 'BB_Low', 'BB_Mid', 'ATR_14',
    'ADX_14', 'ADX_Pos', 'ADX_Neg',
    'SMA_20', 'SMA_50', 'EMA_12', 'EMA_26',
    'Stoch_K', 'Stoch_D', 'MFI_14', 'Williams_R', 'CCI_20',
    'RVOL', 'Volume_Z',
]


def drop_warmup_rows(df: pd.DataFrame, cols=None) -> pd.DataFrame:
    """Drop rows where any core indicator is still NaN (warm-up period).

    Use for training matrices. Serving must instead refuse/skip a ticker
    whose latest row is still in warm-up — never fill it with zero.
    """
    cols = cols or [c for c in CORE_INDICATORS if c in df.columns]
    if not cols:
        return df.copy()
    return df.dropna(subset=cols).copy()


def median_impute_train_only(train: pd.DataFrame, test: pd.DataFrame, cols=None):
    """Impute residual NaNs with medians fit on TRAIN only (no test leakage).

    Call AFTER drop_warmup_rows. Returns (train_filled, test_filled, medians).
    Warm-up NaNs must be dropped first; this only covers stray gaps
    (e.g. isolated history holes), never the leading warm-up block.
    """
    cols = cols or [c for c in (train.columns if cols is None else cols) if c in train.columns]
    medians = train[cols].median()
    return train.fillna(medians), test.fillna(medians), medians


def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Menambahkan indikator teknikal ke dalam DataFrame harga historis.
    Termasuk proxy Bandarmologi menggunakan indikator berbasis volume.

    Warm-up policy (AI-06): leading NaNs from indicator lookback are LEFT
    as NaN. Callers drop them via drop_warmup_rows() (train) or skip the
    ticker (serve). No blind fillna(0): a zero RSI/MACD/ATR is a false
    signal, not a neutral value.

    Args:
        df: DataFrame dengan kolom ['Open', 'High', 'Low', 'Close', 'Volume']

    Returns:
        DataFrame yang sudah ditambahkan kolom indikator teknikal
    """
    df = df.copy()

    # Pastikan data terurut berdasarkan waktu dari lama ke baru
    df.sort_index(inplace=True)

    # 1. BANDARMOLOGI PROXIES (Volume-based Indicators)
    # On-Balance Volume (OBV)
    df['OBV'] = ta.volume.on_balance_volume(close=df['Close'], volume=df['Volume'])

    # Accumulation/Distribution Index (ADI)
    df['ADI'] = ta.volume.acc_dist_index(high=df['High'], low=df['Low'], close=df['Close'], volume=df['Volume'])

    # Volume Weighted Average Price (VWAP)
    df['VWAP'] = ta.volume.volume_weighted_average_price(
        high=df['High'], low=df['Low'], close=df['Close'], volume=df['Volume']
    )

    # 2. MOMENTUM INDICATORS
    # Relative Strength Index (RSI) — warm-up NaN dibiarkan
    df['RSI_14'] = ta.momentum.rsi(close=df['Close'], window=14)

    # MACD — warm-up NaN dibiarkan
    macd = ta.trend.MACD(close=df['Close'])
    df['MACD'] = macd.macd()
    df['MACD_Signal'] = macd.macd_signal()
    df['MACD_Diff'] = macd.macd_diff()

    # 3. VOLATILITY INDICATORS
    # Bollinger Bands — warm-up NaN dibiarkan
    bb = ta.volatility.BollingerBands(close=df['Close'], window=20, window_dev=2)
    df['BB_High'] = bb.bollinger_hband()
    df['BB_Low'] = bb.bollinger_lband()
    df['BB_Mid'] = bb.bollinger_mavg()

    # Average True Range (ATR) — warm-up NaN dibiarkan.
    # ta lib kembalikan 0.0 untuk bar awal (bukan NaN) -> paksa NaN eksplisit
    # agar kebijakan warm-up (AI-06) berlaku: bar tanpa lookback penuh = NaN.
    df['ATR_14'] = ta.volatility.average_true_range(high=df['High'], low=df['Low'], close=df['Close'], window=14)
    df.loc[df.index[:13], 'ATR_14'] = np.nan

    # 4. TREND INDICATORS
    # Average Directional Index (ADX) — warm-up NaN dibiarkan.
    # ta lib kembalikan 0.0 untuk bar awal (bukan NaN) -> paksa NaN eksplisit
    # untuk 2*window-1 = 27 bar pertama (smoothing ADX butuh lookback ganda).
    df['ADX_14'] = ta.trend.adx(high=df['High'], low=df['Low'], close=df['Close'], window=14)
    df['ADX_Pos'] = ta.trend.adx_pos(high=df['High'], low=df['Low'], close=df['Close'], window=14)
    df['ADX_Neg'] = ta.trend.adx_neg(high=df['High'], low=df['Low'], close=df['Close'], window=14)
    df.loc[df.index[:27], ['ADX_14', 'ADX_Pos', 'ADX_Neg']] = np.nan

    # Simple Moving Averages — warm-up NaN dibiarkan (bukan fill Close)
    df['SMA_20'] = ta.trend.sma_indicator(close=df['Close'], window=20)
    df['SMA_50'] = ta.trend.sma_indicator(close=df['Close'], window=50)

    # 5. RELATIVE VOLUME & VOLUME Z-SCORE — warm-up NaN dibiarkan
    vol_sma20 = df['Volume'].rolling(20).mean()
    vol_std20 = df['Volume'].rolling(20).std()
    df['RVOL'] = df['Volume'] / (vol_sma20 + 1e-9)
    df['Volume_Z'] = (df['Volume'] - vol_sma20) / (vol_std20 + 1e-9)

    # 6. ADVANCED OSCILLATORS & MONEY FLOW — warm-up NaN dibiarkan
    df['Stoch_K'] = ta.momentum.stoch(high=df['High'], low=df['Low'], close=df['Close'], window=14, smooth_window=3)
    df['Stoch_D'] = ta.momentum.stoch_signal(high=df['High'], low=df['Low'], close=df['Close'], window=14, smooth_window=3)
    df['MFI_14'] = ta.volume.money_flow_index(high=df['High'], low=df['Low'], close=df['Close'], volume=df['Volume'], window=14)
    df['EMA_12'] = ta.trend.ema_indicator(close=df['Close'], window=12)
    df['EMA_26'] = ta.trend.ema_indicator(close=df['Close'], window=26)
    df['Williams_R'] = ta.momentum.williams_r(high=df['High'], low=df['Low'], close=df['Close'], lbp=14)
    df['CCI_20'] = ta.trend.cci(high=df['High'], low=df['Low'], close=df['Close'], window=20)

    return df
