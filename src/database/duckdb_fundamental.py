"""
DuckDB-backed fundamental data store for IDX tickers.
Stores PER, PBV, ROE, Debt/Equity, Market Cap, and Dividend Yield.
"""
import sys
from pathlib import Path

import duckdb

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
                updated_at TIMESTAMP,
                as_of DATE
            )
        """)
        # Migrasi ringan: DB lama tanpa kolom as_of.
        try:
            _cols = [r[1] for r in _conn.execute("PRAGMA table_info(fundamentals)").fetchall()]
            if "as_of" not in _cols:
                _conn.execute("ALTER TABLE fundamentals ADD COLUMN as_of DATE")
        except Exception:
            pass
    return _conn

def save_fundamental(ticker: str, data: dict):
    conn = get_fundamental_db_connection()
    clean_t = ticker.replace(".JK", "").upper()
    # AI-07: NULL untuk missing (None), bukan 0.0. Simpan as_of agar
    # downstream bisa tolak snapshot basi (point-in-time).
    conn.execute("""
        INSERT OR REPLACE INTO fundamentals (ticker, per, pbv, roe, debt_to_equity, market_cap, dividend_yield, revenue_growth, updated_at, as_of)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
    """, [
        clean_t,
        data.get("per"),
        data.get("pbv"),
        data.get("roe"),
        data.get("debt_to_equity"),
        data.get("market_cap"),
        data.get("dividend_yield"),
        data.get("revenue_growth"),
        data.get("as_of"),
    ])

def get_fundamental(ticker: str) -> dict:
    conn = get_fundamental_db_connection()
    clean_t = ticker.replace(".JK", "").upper()
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(fundamentals)").fetchall()]
    except Exception:
        cols = []
    sel_asof = ", as_of" if "as_of" in cols else ""
    res = conn.execute(
        f"SELECT per, pbv, roe, debt_to_equity, market_cap, dividend_yield, revenue_growth{sel_asof} "
        "FROM fundamentals WHERE ticker = ?", [clean_t]).fetchone()
    if not res:
        return {"per": None, "pbv": None, "roe": None, "debt_to_equity": None,
                "market_cap": None, "dividend_yield": None, "revenue_growth": None,
                "as_of": None}
    out = {
        "per": res[0],
        "pbv": res[1],
        "roe": res[2],
        "debt_to_equity": res[3],
        "market_cap": res[4],
        "dividend_yield": res[5],
        "revenue_growth": res[6],
    }
    # AI-07: NULL (None) untuk missing — 0.0 = sinyal cheap palsu.
    # Legacy row 0.0 tanpa as_of tidak bisa dibedakan -> perlakukan 0.0
    # pada rasio valuasi sebagai missing bila as_of tidak ada.
    has_asof = bool("as_of" in cols and len(res) > 7 and res[7])
    if not has_asof:
        for k in ("per", "pbv", "roe", "debt_to_equity", "market_cap",
                  "dividend_yield", "revenue_growth"):
            if out[k] == 0.0:
                out[k] = None
    out["as_of"] = str(res[7])[:10] if has_asof else None
    return out
