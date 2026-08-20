"""
routes/features.py
Helper functions untuk feature engineering & label generation.
Digunakan oleh predict.py.
"""
import pandas as pd


def generate_reason(row: pd.Series) -> str:
    """Menghasilkan teks alasan AI berbahasa Indonesia berdasarkan indikator teknikal, RVOL, ADX, MFI & Stochastic."""
    reasons = []

    rvol = float(row.get('RVOL', 1.0))
    if rvol >= 1.5:
        reasons.append(f"Volume Melonjak {rvol:.1f}x (RVOL Breakout)")
    elif rvol >= 1.2:
        reasons.append(f"Akumulasi Volume ({rvol:.1f}x Rata-rata)")

    mfi = float(row.get('MFI_14', 50))
    if mfi >= 70:
        reasons.append(f"Inflow Uang Kuat (MFI {mfi:.0f})")
    elif mfi < 30:
        reasons.append("Money Flow Oversold")

    stoch_k = float(row.get('Stoch_K', 50))
    stoch_d = float(row.get('Stoch_D', 50))
    if stoch_k < 25 and stoch_k > stoch_d:
        reasons.append("Stochastic Golden Cross (Reversal)")

    adx = float(row.get('ADX_14', 20))
    if adx >= 25:
        reasons.append(f"Tren Kuat (ADX {adx:.0f})")

    rsi = float(row.get('RSI_14', 50))
    if rsi < 30:
        reasons.append("Sangat Oversold (Obral Murah)")
    elif rsi < 45:
        reasons.append("Oversold (Koreksi Sehat)")

    macd_diff = float(row.get('MACD_Diff', 0))
    if macd_diff > 0:
        reasons.append("MACD Menguat (Bullish)")

    close = float(row.get('Close', 0))
    sma50 = float(row.get('SMA_50', 100_000))
    if close > sma50 and sma50 > 0:
        reasons.append("Harga di atas MA-50")

    ema12 = float(row.get('EMA_12', 0))
    ema26 = float(row.get('EMA_26', 0))
    if ema12 > ema26 and ema26 > 0:
        reasons.append("EMA-12 Golden Cross EMA-26")

    if float(row.get('IHSG_Return', 0)) > 0:
        reasons.append("IHSG Mendukung")

    if not reasons:
        reasons.append("Pola Volume & Momentum tersembunyi yang dikenali AI")

    return ", ".join(reasons)


def derive_signals(row: pd.Series) -> dict:
    """Menurunkan sinyal teknikal, ATR Dynamic TP/SL, dan alokasi Kelly Criterion."""
    rsi       = float(row.get('RSI_14', 50))
    macd_diff = float(row.get('MACD_Diff', 0))
    close     = float(row.get('_raw_close', 0)) or float(row.get('Close', 0))
    sma50     = float(row.get('SMA_50', 0))
    atr       = float(row.get('ATR_14', 0)) or float(row.get('ATR', 0))
    adx       = float(row.get('ADX_14', 20))
    rvol      = float(row.get('RVOL', 1.0))
    prob      = float(row.get('Probability', row.get('probability', 0.65)))
    if prob > 1.0:
        prob = prob / 100.0  # normalize 65.0 -> 0.65

    rsi_signal  = 'Oversold'  if rsi < 40  else ('Overbought' if rsi > 70 else 'Netral')
    macd_signal = 'Bullish'   if macd_diff > 0 else 'Bearish'
    trend       = 'Uptrend'   if (close > 0 and sma50 > 0 and close > sma50) else 'Downtrend'

    # 3. Dynamic Volatility-Adjusted Target Profit & Stop Loss (ATR-Based)
    if close > 0:
        if atr > 0:
            # TP buffer: 1.5x - 2.0x ATR, clamped between +2.5% dan +5.0%
            tp_delta = max(close * 0.025, min(close * 0.050, 1.5 * atr))
            # SL buffer: 1.0x ATR, clamped between -1.2% dan -2.0%
            sl_delta = max(close * 0.012, min(close * 0.020, 1.0 * atr))
            raw_target = close + tp_delta
            raw_sl     = close - sl_delta
        else:
            raw_target = close * 1.030
            raw_sl     = close * 0.985

        target = round(raw_target, 0)
        stop_loss = round(raw_sl, 0)

        # 4. Kelly Criterion Position Sizing (% alokasi portofolio yang direkomendasikan)
        reward_dist = max(1.0, target - close)
        risk_dist   = max(1.0, close - stop_loss)
        b_ratio     = reward_dist / risk_dist  # Payoff ratio
        p_win       = max(0.50, min(0.90, prob if prob > 0 else 0.65))
        q_loss      = 1.0 - p_win

        # Half-Kelly for capital preservation: 0.5 * (p*b - q) / b
        raw_kelly = 0.5 * ((p_win * b_ratio - q_loss) / (b_ratio + 1e-9))
        kelly_pct = round(max(5.0, min(25.0, raw_kelly * 100.0)), 1)
        rr_ratio  = round(b_ratio, 2)
    else:
        target = 0
        stop_loss = 0
        kelly_pct = 10.0
        rr_ratio = 2.0

    return {
        "close_price":       close,
        "target_price":      target,
        "stop_loss":         stop_loss,
        "rsi":               round(rsi, 1),
        "rsi_signal":        rsi_signal,
        "macd_signal":       macd_signal,
        "trend":             trend,
        "adx":               round(adx, 1),
        "rvol":              round(rvol, 2),
        "risk_reward_ratio": rr_ratio,
        "kelly_allocation":  kelly_pct
    }
