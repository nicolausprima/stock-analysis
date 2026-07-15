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
    # Simple Moving Averages (SMA)
    df['SMA_20'] = ta.trend.sma_indicator(close=df['Close'], window=20)
    df['SMA_50'] = ta.trend.sma_indicator(close=df['Close'], window=50)
    
    return df
