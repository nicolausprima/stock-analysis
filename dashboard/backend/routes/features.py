"""
routes/features.py
Helper functions untuk feature engineering & label generation.
Digunakan oleh predict.py.
"""
import pandas as pd


def generate_reason(row: pd.Series) -> str:
    """Menghasilkan teks alasan AI berbahasa Indonesia berdasarkan indikator teknikal."""
    reasons = []

    rsi = row.get('RSI_14', 50)
    if rsi < 30:
        reasons.append("Sangat Oversold (Obral Murah)")
    elif rsi < 45:
        reasons.append("Oversold (Koreksi Sehat)")

    macd_diff = row.get('MACD_Diff', 0)
    if macd_diff > 0:
        reasons.append("MACD Menguat (Uptrend)")

    if row.get('Close', 0) > row.get('SMA_50', 100_000):
        reasons.append("Harga di atas MA-50")

    if row.get('IHSG_Return', 0) > 0:
        reasons.append("IHSG Mendukung (Hijau)")

    if not reasons:
        reasons.append("Pola Volume & Momentum tersembunyi yang dikenali AI")

    return ", ".join(reasons)


def derive_signals(row: pd.Series) -> dict:
    """Menurunkan sinyal teknikal dari baris data untuk tampilan di UI."""
    rsi       = float(row.get('RSI_14', 50))
    macd_diff = float(row.get('MACD_Diff', 0))
    close     = float(row.get('_raw_close', 0)) or float(row.get('Close', 0))
    sma50     = float(row.get('SMA_50', 0))
    atr       = float(row.get('ATR_14', 0)) or float(row.get('ATR', 0))

    rsi_signal  = 'Oversold'  if rsi < 40  else ('Overbought' if rsi > 70 else 'Netral')
    macd_signal = 'Bullish'   if macd_diff > 0 else 'Bearish'
    trend       = 'Uptrend'   if (close > 0 and sma50 > 0 and close > sma50) else 'Downtrend'

    # Target Profit: Minimal +3.0%, atau lebih tinggi jika volatilitas/ATR mengizinkan
    if close > 0:
        if atr > 0:
            raw_target = max(close * 1.03, close + (1.5 * atr))
        else:
            raw_target = close * 1.03
        target = round(raw_target, 0)
        stop_loss = round(close * 0.985, 0)
    else:
        target = 0
        stop_loss = 0

    return {
        "close_price":  close,
        "target_price": target,
        "stop_loss":    stop_loss,
        "rsi":          round(rsi, 1),
        "rsi_signal":   rsi_signal,
        "macd_signal":  macd_signal,
        "trend":        trend,
    }
