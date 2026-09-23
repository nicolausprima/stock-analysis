"""
Fundamental data collector.
Fetch PER, PBV, ROE etc using yfinance and store to DuckDB fundamental store.

Point-in-time policy (AI-07): yfinance `ticker.info` is a NOWCAST snapshot —
it reflects the latest published fundamentals, not what was known at a past
decision-time bar. Each record carries an `as_of` date so downstream code can
lag it. Missing fields are stored as NULL (None), never 0.0: a 0.0 PER/PBV
is a plausible-but-false cheap-value signal.
"""
from datetime import date

from dashboard.backend.yf_client import get_ticker_info
from src.config import TICKERS
from src.database.duckdb_fundamental import save_fundamental


def _clean(value):
    """None for missing/non-finite; else float. Never 0.0-invented."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v != v:  # noqa: PLR0124 - idiom cek NaN tanpa math.isnan (value bisa non-float)
        return None
    return v


def fetch_fundamental_snapshot(ticker: str) -> dict:
    """Fetch one snapshot: NULLs for missing + as-of date. No DB write."""
    info = get_ticker_info(ticker) or {}
    return {
        "per": _clean(info.get("trailingPE")),
        "pbv": _clean(info.get("priceToBook")),
        "roe": _clean(info.get("returnOnEquity")),
        "debt_to_equity": _clean(info.get("debtToEquity")),
        "market_cap": _clean(info.get("marketCap")),
        "dividend_yield": _clean(info.get("dividendYield")),
        "revenue_growth": _clean(info.get("revenueGrowth")),
        "as_of": date.today().isoformat(),
        "source": "yfinance-info-nowcast",
    }


def run_fundamental_collection():
    print(f"[Fundamental] Memulai pengunduhan data fundamental {len(TICKERS)} saham...")
    for t in TICKERS:
        try:
            data = fetch_fundamental_snapshot(t)
            save_fundamental(t, data)
            print(f"  [OK] Fundamental {t}")
        except Exception as e:
            print(f"  [ERROR] {t}: {e}")
    print("[Fundamental] Selesai.")

if __name__ == "__main__":
    run_fundamental_collection()
