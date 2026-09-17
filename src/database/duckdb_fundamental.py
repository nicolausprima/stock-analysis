"""
DuckDB-backed fundamental data store for IDX tickers.
Stores PER, PBV, ROE, Debt/Equity, Market Cap, and Dividend Yield.
"""
import duckdb
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.utils.paths import DATA_DIR

DUCKDB_FUNDAMENTAL_PATH = DATA_DIR / "stock_fundamentals.duckdb"

_conn = None

def get_fundamental_db_connection() -> duckdb.DuckDBPyConnection:
    global _conn
    if _conn is None:
        _conn = duckdb.connect(str(DUCKDB_FUNDAMENTAL_PATH))
        _conn.execute("""
            CREATE TABLE IF NOT EXISTS fundamentals (
                ticker VARCHAR PRIMARY KEY,
                per DOUBLE,
                pbv DOUBLE,
                roe DOUBLE,
                debt_to_equity DOUBLE,
                market_cap DOUBLE,
                dividend_yield DOUBLE,
                revenue_growth DOUBLE,
                updated_at TIMESTAMP
            )
        """)
    return _conn

def save_fundamental(ticker: str, data: dict):
    conn = get_fundamental_db_connection()
    clean_t = ticker.replace(".JK", "").upper()
    conn.execute("""
        INSERT OR REPLACE INTO fundamentals (ticker, per, pbv, roe, debt_to_equity, market_cap, dividend_yield, revenue_growth, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, [
        clean_t,
        data.get("per", 0.0),
        data.get("pbv", 0.0),
        data.get("roe", 0.0),
        data.get("debt_to_equity", 0.0),
        data.get("market_cap", 0.0),
        data.get("dividend_yield", 0.0),
        data.get("revenue_growth", 0.0)
    ])

def get_fundamental(ticker: str) -> dict:
    conn = get_fundamental_db_connection()
    clean_t = ticker.replace(".JK", "").upper()
    res = conn.execute("SELECT per, pbv, roe, debt_to_equity, market_cap, dividend_yield, revenue_growth FROM fundamentals WHERE ticker = ?", [clean_t]).fetchone()
    if not res:
        return {"per": 0.0, "pbv": 0.0, "roe": 0.0, "debt_to_equity": 0.0, "market_cap": 0.0, "dividend_yield": 0.0, "revenue_growth": 0.0}
    return {
        "per": res[0] or 0.0,
        "pbv": res[1] or 0.0,
        "roe": res[2] or 0.0,
        "debt_to_equity": res[3] or 0.0,
        "market_cap": res[4] or 0.0,
        "dividend_yield": res[5] or 0.0,
        "revenue_growth": res[6] or 0.0
    }
