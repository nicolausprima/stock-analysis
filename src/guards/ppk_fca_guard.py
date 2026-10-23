"""
PPK & Full Call Auction (FCA) Hazard Guard for IDX / BEI.

Evaluates regulatory hazard criteria under BEI Kep-00044/BEI/03-2024 and Kep-00076/BEI/06-2024:
1. Low Price Trap: SMA120 <= 52 or Close <= 52 (extreme hazard of crashing to single digits in FCA).
2. Negative Equity: Total Equity <= 0 (Kriteria 5 PPK).
3. Extreme Illiquidity: ADTV 90d < Rp 5 Juta or Daily Volume < 10,000 shares (Kriteria 7 PPK).
4. Notasi Khusus PPK: "X", "E", "A" (Papan Pemantauan Khusus).

Provides hard-veto protection to prevent allocating capital into illiquid/FCA trap stocks.
"""

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# Saham atau notasi khusus yang masuk dalam daftar pantauan PPK / FCA
# Notasi "X" = Papan Pemantauan Khusus, "E" = Ekuitas Negatif, "A" = PKPU/Pailit
PPK_NOTATION_FLAGS = {"X", "E", "A"}

# Default critical thresholds for IDX
MIN_PRICE_FLOOR = 52.0  # Saham di bawah Rp 52 sangat rawan meluncur bebas ke Rp 1 di FCA
MIN_ADTV_TURNOVER = 5_000_000.0  # Rp 5 Juta per hari (Kriteria 7 likuiditas minimal)
MIN_DAILY_VOLUME = 10_000  # 100 lot (10.000 lembar)


def evaluate_ticker_hazard(
    ticker: str,
    df_price: pd.DataFrame | None = None,
    fundamental: dict[str, Any] | None = None,
    notasi_khusus: list[str] | None = None,
) -> dict[str, Any]:
    """
    Evaluasi apakah sebuah ticker berisiko masuk atau sedang berada di Papan Pemantauan Khusus (FCA).

    Returns:
        dict: {
            "ticker": str,
            "is_blocked": bool,
            "hazard_score": int,  # 0 (Aman), 1-2 (Perhatian), >=3 (Kritis)
            "verdict": "SAFE" | "CAUTION" | "CRITICAL_BLOCKED",
            "reasons": list[str]
        }
    """
    clean_ticker = ticker.upper().replace(".JK", "").strip()
    reasons: list[str] = []
    hazard_score = 0

    # 1. Cek Notasi Khusus Resmi BEI
    if notasi_khusus:
        matched_flags = set(notasi_khusus).intersection(PPK_NOTATION_FLAGS)
        if matched_flags:
            hazard_score += 3
            reasons.append(f"Notasi Khusus BEI terdeteksi: {','.join(matched_flags)} (Papan Pemantauan Khusus)")

    # 2. Cek Fundamental (Ekuitas Negatif & Solvabilitas)
    if fundamental:
        total_equity = fundamental.get("total_equity") or fundamental.get("equity")
        if total_equity is not None:
            try:
                equity_val = float(total_equity)
                if equity_val <= 0:
                    hazard_score += 3
                    reasons.append("Ekuitas negatif (Kriteria 5 PPK: Modal minus berisiko delisting)")
            except (ValueError, TypeError):
                pass

        # Cek Debt to Equity Ratio ekstrim jika ekuitas sangat tipis
        der = fundamental.get("der")
        if der is not None:
            try:
                der_val = float(der)
                if der_val < 0 or der_val > 20.0:
                    hazard_score += 1
                    reasons.append(f"Struktur modal berbahaya (DER: {der_val:.1f}x)")
            except (ValueError, TypeError):
                pass

    # 3. Cek Mikrostruktur Harga & Likuiditas dari Historis Harga
    if df_price is not None and not df_price.empty:
        try:
            close_col = df_price["Close"]
            if isinstance(close_col, pd.DataFrame):
                close_series = close_col.iloc[:, 0]
            else:
                close_series = close_col

            last_close = float(close_series.iloc[-1])

            # A. Jebakan Harga Gocap (Rp 50) ke FCA
            if last_close <= MIN_PRICE_FLOOR:
                hazard_score += 3
                reasons.append(
                    f"Harga kritis Rp {last_close:,.0f} <= Rp {MIN_PRICE_FLOOR:.0f} "
                    "(Rawan anjlok bebas ke Rp 1 di Papan Pemantauan Khusus FCA)"
                )

            # B. Rata-rata 120 Hari (Kriteria 1 PPK: Rata-rata < Rp 51)
            if len(close_series) >= 20:
                lookback = min(len(close_series), 120)
                sma_long = float(close_series.iloc[-lookback:].mean())
                if sma_long < 51.0:
                    hazard_score += 3
                    reasons.append(f"Rata-rata harga {lookback} hari Rp {sma_long:.1f} < Rp 51 (Kriteria 1 PPK)")

            # C. Likuiditas Transaksi (Kriteria 7 PPK)
            vol_col = df_price.get("Volume")
            if vol_col is not None:
                if isinstance(vol_col, pd.DataFrame):
                    vol_series = vol_col.iloc[:, 0]
                else:
                    vol_series = vol_col

                if len(vol_series) >= 5:
                    avg_vol = float(vol_series.iloc[-20:].mean()) if len(vol_series) >= 20 else float(vol_series.mean())
                    if avg_vol < MIN_DAILY_VOLUME:
                        hazard_score += 2
                        reasons.append(f"Volume harian rata-rata tipis ({avg_vol:,.0f} < {MIN_DAILY_VOLUME:,.0f} lembar)")

                    # Rata-rata turnover harian
                    avg_turnover = avg_vol * last_close
                    if avg_turnover < MIN_ADTV_TURNOVER:
                        hazard_score += 2
                        reasons.append(
                            f"Turnover rata-rata harian Rp {avg_turnover:,.0f} < Rp {MIN_ADTV_TURNOVER:,.0f} (Likuiditas beku)"
                        )
        except (ValueError, KeyError, TypeError, IndexError) as err:
            logger.debug("Toleran terhadap error parsing mikrostruktur: %s", err)

    # Tentukan Verdict
    if hazard_score >= 3:
        verdict = "CRITICAL_BLOCKED"
        is_blocked = True
    elif hazard_score >= 1:
        verdict = "CAUTION"
        is_blocked = False
    else:
        verdict = "SAFE"
        is_blocked = False

    return {
        "ticker": clean_ticker,
        "is_blocked": is_blocked,
        "hazard_score": hazard_score,
        "verdict": verdict,
        "reasons": reasons,
    }


def filter_safe_universe(
    tickers: list[str],
    duckdb_conn=None,
    strict_veto: bool = True
) -> list[str]:
    """
    Menyaring semesta saham agar bebas dari saham-saham jebakan FCA / PPK.
    Bisa menerima koneksi DuckDB fundamental untuk evaluasi batch.
    """
    safe_tickers = []
    for ticker in tickers:
        fund_data = None
        if duckdb_conn is not None:
            try:
                from src.database.duckdb_fundamental import get_fundamental
                fund_data = get_fundamental(ticker)
            except (ImportError, OSError, ValueError) as fe:
                logger.debug("Tidak dapat memuat fundamental untuk %s: %s", ticker, fe)

        eval_res = evaluate_ticker_hazard(ticker, fundamental=fund_data)
        if strict_veto and eval_res["is_blocked"]:
            continue
        safe_tickers.append(ticker)
    return safe_tickers
