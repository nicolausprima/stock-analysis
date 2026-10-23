"""
Pre-Market Global Commodity Cues & Sector Transmissions for BEI (IDX).

Fetches overnight commodity derivatives and global equity proxies (ASX, CBOT, NYMEX, COMEX)
between 07:00 - 08:30 WIB before BEI opens at 09:00 WIB using free Yahoo Finance feeds.

Proxies:
- Batubara (Coal): WHC.AX (Whitehaven Coal on ASX Sydney, trades from 07:00 WIB) & BTU
- Nikel & Logam (Nickel/Copper): NIC.AX (Nickel Industries on ASX) & HG=F (Copper)
- CPO: ZL=F (CBOT Soybean Oil Futures, proxy korelasi >0.85 terhadap MDEX FCPO)
- Emas (Gold): GC=F (COMEX Gold Futures)
- Minyak Mentah (Crude Oil): CL=F (WTI) & BZ=F (Brent)
"""

import logging
from typing import Any

import pandas as pd

from dashboard.backend.yf_client import download_with_timeout

logger = logging.getLogger(__name__)

# Pemetaan Ticker Komoditas Global -> Sektor BEI
COMMODITY_PROXIES = {
    "COAL": {
        "tickers": ["WHC.AX", "BTU"],
        "name": "Batubara (Coal Proxy)",
        "idx_sector": "Energi",
        "affected_stocks": ["ADRO", "PTBA", "ITMG", "BUMI", "INDY", "DOID", "BYAN", "MBMA"],
        "weight": 1.0,
    },
    "NICKEL_COPPER": {
        "tickers": ["NIC.AX", "HG=F"],
        "name": "Nikel & Tembaga (Metals)",
        "idx_sector": "Bahan Baku",
        "affected_stocks": ["INCO", "ANTM", "MDKA", "BRMS", "NCKL", "TINS", "AMMN"],
        "weight": 1.0,
    },
    "CPO": {
        "tickers": ["ZL=F"],
        "name": "Minyak Nabati / CPO (CBOT Soyoil)",
        "idx_sector": "Konsumer Primer",
        "affected_stocks": ["AALI", "TAPG", "LSIP", "DSNG", "SIMP", "BWPT"],
        "weight": 0.8,
    },
    "GOLD": {
        "tickers": ["GC=F"],
        "name": "Emas Dunia (COMEX Gold)",
        "idx_sector": "Bahan Baku",
        "affected_stocks": ["MDKA", "ANTM", "BRMS", "PSAB", "ARCI"],
        "weight": 0.7,
    },
    "OIL": {
        "tickers": ["CL=F", "BZ=F"],
        "name": "Minyak Mentah (WTI / Brent)",
        "idx_sector": "Energi",
        "affected_stocks": ["MEDC", "ELSA", "AKRA", "PGAS", "ENRG"],
        "weight": 0.8,
    },
}


def fetch_overnight_return(symbol: str) -> float | None:
    """Mengambil return 1-hari terakhir dari simbol komoditas global."""
    try:
        df = download_with_timeout(symbol, period="5d", progress=False)
        if df.empty or len(df) < 2:
            return None

        close_col = df["Close"]
        if isinstance(close_col, pd.DataFrame):
            close_series = close_col.iloc[:, 0]
        else:
            close_series = close_col

        close_series = close_series.dropna()
        if len(close_series) < 2:
            return None

        p_curr = float(close_series.iloc[-1])
        p_prev = float(close_series.iloc[-2])
        if p_prev <= 0:
            return None

        pct_change = ((p_curr - p_prev) / p_prev) * 100.0
        return round(pct_change, 2)
    except Exception as e:
        logger.warning("Gagal mengunduh proxy komoditas %s: %s", symbol, e)
        return None


def get_global_commodity_cues() -> dict[str, Any]:
    """
    Evaluasi transmisi harga komoditas global semalam (overnight cues).

    Returns:
        dict: {
            "timestamp": str,
            "cues": dict of proxy performance,
            "sector_boosters": dict of sector probability modifiers (+/- %),
            "stock_modifiers": dict of ticker -> probability delta,
            "summary_badges": list of formatted status strings
        }
    """
    cues: dict[str, dict[str, Any]] = {}
    stock_modifiers: dict[str, float] = {}
    sector_boosters: dict[str, float] = {}
    summary_badges: list[str] = []

    for key, info in COMMODITY_PROXIES.items():
        returns: list[float] = []
        for symbol in info["tickers"]:
            ret = fetch_overnight_return(symbol)
            if ret is not None:
                returns.append(ret)

        if not returns:
            avg_ret = 0.0
            status = "FLAT"
        else:
            avg_ret = round(sum(returns) / len(returns), 2)
            if avg_ret >= 1.5:
                status = "BULLISH_BOOST"
            elif avg_ret <= -1.5:
                status = "BEARISH_DRAG"
            else:
                status = "NEUTRAL"

        # Tentukan delta probabilitas (+2.0% s.d. +3.5% untuk penguatan kuat)
        booster = 0.0
        if avg_ret >= 3.0:
            booster = +3.0
            badge = f"🔥 {info['name']}: +{avg_ret:.1f}% (Strong Inflow Cue)"
        elif avg_ret >= 1.2:
            booster = +1.5
            badge = f"🟢 {info['name']}: +{avg_ret:.1f}% (Positive Momentum)"
        elif avg_ret <= -3.0:
            booster = -3.0
            badge = f"🔴 {info['name']}: {avg_ret:.1f}% (Sharp Correction Warning)"
        elif avg_ret <= -1.2:
            booster = -1.5
            badge = f"⚠️ {info['name']}: {avg_ret:.1f}% (Mild Correction Drag)"
        else:
            badge = f"➖ {info['name']}: {avg_ret:+.1f}% (Neutral)"

        summary_badges.append(badge)

        cues[key] = {
            "name": info["name"],
            "avg_return_pct": avg_ret,
            "status": status,
            "booster": booster,
        }

        # Simpan ke daftar saham terdampak
        for stk in info["affected_stocks"]:
            clean_stk = stk.upper().replace(".JK", "").strip()
            # Akumulasikan jika satu saham terdampak beberapa komoditas (misal ANTM: Nikel & Emas)
            curr = stock_modifiers.get(clean_stk, 0.0)
            stock_modifiers[clean_stk] = round(curr + booster, 1)

        # Simpan booster sektor agregat
        sec = info["idx_sector"]
        prev_sec_boost = sector_boosters.get(sec, 0.0)
        sector_boosters[sec] = round(max(prev_sec_boost, booster), 1)

    return {
        "status": "success",
        "cues": cues,
        "sector_boosters": sector_boosters,
        "stock_modifiers": stock_modifiers,
        "summary_badges": summary_badges,
    }


def get_ticker_commodity_boost(ticker: str, commodity_cues: dict[str, Any] | None = None) -> float:
    """
    Mengambil penyesuaian probabilitas (booster) untuk ticker tertentu
    berdasarkan sentimen komoditas global semalam.
    """
    if commodity_cues is None:
        return 0.0

    clean_t = ticker.upper().replace(".JK", "").strip()
    return float(commodity_cues.get("stock_modifiers", {}).get(clean_t, 0.0))
