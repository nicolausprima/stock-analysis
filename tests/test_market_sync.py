"""Regresi D-03: SQLite kanonik -> DuckDB mirror tidak boleh tertinggal diam-diam."""

import sqlite3

from src.database.sync_market import (
    data_lag_days,
    duckdb_latest_date,
    sync_duckdb_from_sqlite,
)


def _make_sqlite(path, last_date: str, ticker: str = "BBCA.JK"):
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS daily_prices (ticker TEXT, date TEXT, open REAL, "
            "high REAL, low REAL, close REAL, volume REAL, PRIMARY KEY (ticker, date))"
        )
        conn.executemany(
            "INSERT OR REPLACE INTO daily_prices VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (ticker, "2026-09-24", 6000, 6100, 5950, 6050, 1_000_000),
                (ticker, last_date, 6050, 6150, 6000, 6120, 1_200_000),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def test_sync_copies_canonical_rows_and_closes_lag(tmp_path):
    sqlite_path = tmp_path / "market.db"
    _make_sqlite(sqlite_path, "2026-09-25")

    # Mirror masih kosong -> jeda tidak bisa dihitung (bukan angka palsu).
    assert duckdb_latest_date() is None
    assert data_lag_days(sqlite_path) is None

    result = sync_duckdb_from_sqlite(limit_days=30, db_path=sqlite_path)
    assert result["status"] == "success"
    assert result["tickers"] == 1
    assert result["duckdb_latest"] == "2026-09-25"

    # Setelah sinkron, jeda harus nol.
    assert data_lag_days(sqlite_path) == 0

    # Idempoten: sync kedua tidak menggandakan baris.
    sync_duckdb_from_sqlite(limit_days=30, db_path=sqlite_path)
    from src.database.duckdb_market import get_ticker_history_polars

    assert get_ticker_history_polars("BBCA.JK", limit_days=30).height == 2


def test_lag_reports_stale_mirror(tmp_path):
    """Mirror yang lebih tua harus terukur sebagai jeda positif (0 < lag)."""
    sqlite_path = tmp_path / "market.db"
    _make_sqlite(sqlite_path, "2026-09-24")

    sync_duckdb_from_sqlite(limit_days=30, db_path=sqlite_path)
    assert data_lag_days(sqlite_path) == 0

    # Satu hari bursa baru masuk ke SQLite saja: mirror kini tertinggal 1 hari.
    _make_sqlite(sqlite_path, "2026-09-25")
    assert data_lag_days(sqlite_path) == 1
