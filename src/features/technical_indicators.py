import pandas as pd
import ta

def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Menambahkan indikator teknikal ke dalam DataFrame harga historis.
    Termasuk proxy Bandarmologi menggunakan indikator berbasis volume.
    
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
    # Relative Strength Index (RSI)
    df['RSI_14'] = ta.momentum.rsi(close=df['Close'], window=14)
    
    # MACD
    macd = ta.trend.MACD(close=df['Close'])
    df['MACD'] = macd.macd()
    df['MACD_Signal'] = macd.macd_signal()
    df['MACD_Diff'] = macd.macd_diff()
    
    # 3. VOLATILITY INDICATORS
    # Bollinger Bands
    bb = ta.volatility.BollingerBands(close=df['Close'], window=20, window_dev=2)
    df['BB_High'] = bb.bollinger_hband()
    df['BB_Low'] = bb.bollinger_lband()
    df['BB_Mid'] = bb.bollinger_mavg()
    
    # Average True Range (ATR)
    df['ATR_14'] = ta.volatility.average_true_range(high=df['High'], low=df['Low'], close=df['Close'], window=14)
    
    # 4. TREND INDICATORS
    # Average Directional Index (ADX) - Kekuatan Tren
    df['ADX_14'] = ta.trend.adx(high=df['High'], low=df['Low'], close=df['Close'], window=14).fillna(20)
    df['ADX_Pos'] = ta.trend.adx_pos(high=df['High'], low=df['Low'], close=df['Close'], window=14).fillna(20)
    df['ADX_Neg'] = ta.trend.adx_neg(high=df['High'], low=df['Low'], close=df['Close'], window=14).fillna(20)

    # Simple Moving Averages (SMA)
    df['SMA_20'] = ta.trend.sma_indicator(close=df['Close'], window=20)
    df['SMA_50'] = ta.trend.sma_indicator(close=df['Close'], window=50)
    
    # 5. RELATIVE VOLUME & VOLUME Z-SCORE (RVOL Breakout confirmation)
    vol_sma20 = df['Volume'].rolling(20).mean().replace(0, 1)
    vol_std20 = df['Volume'].rolling(20).std().replace(0, 1)
    df['RVOL'] = (df['Volume'] / (vol_sma20 + 1e-9)).fillna(1.0)
    df['Volume_Z'] = ((df['Volume'] - vol_sma20) / (vol_std20 + 1e-9)).fillna(0.0)

    # 6. ADVANCED OSCILLATORS & MONEY FLOW (Institutional Proxies)
    # Stochastic Oscillator (%K & %D)
    df['Stoch_K'] = ta.momentum.stoch(high=df['High'], low=df['Low'], close=df['Close'], window=14, smooth_window=3).fillna(50)
    df['Stoch_D'] = ta.momentum.stoch_signal(high=df['High'], low=df['Low'], close=df['Close'], window=14, smooth_window=3).fillna(50)

    # Money Flow Index (MFI) - Volume-weighted RSI proxy
    df['MFI_14'] = ta.volume.money_flow_index(high=df['High'], low=df['Low'], close=df['Close'], volume=df['Volume'], window=14).fillna(50)

    # Exponential Moving Averages (EMA)
    df['EMA_12'] = ta.trend.ema_indicator(close=df['Close'], window=12).fillna(df['Close'])
    df['EMA_26'] = ta.trend.ema_indicator(close=df['Close'], window=26).fillna(df['Close'])

    # Williams %R
    df['Williams_R'] = ta.momentum.williams_r(high=df['High'], low=df['Low'], close=df['Close'], lbp=14).fillna(-50)

    # Commodity Channel Index (CCI)
    df['CCI_20'] = ta.trend.cci(high=df['High'], low=df['Low'], close=df['Close'], window=20).fillna(0)

    return df

