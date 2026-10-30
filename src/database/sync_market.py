"""Satu arah sinkronisasi harga: SQLite (kanonik) -> DuckDB (turunan).

Konteks (audit 2026-10-30, D-03): pipeline harian menulis ke SQLite
(`stock_market.db`) sementara backtest vektor membaca DuckDB
(`stock_market.duckdb`). DuckDB hanya terisi bila `polars_batch_collector`
dijalankan manual, sehingga backtest bisa memakai harga berhari-hari lebih tua
daripada sinyal yang disajikan API — tanpa peringatan apa pun.

Keputusan yang diambil: **SQLite adalah satu-satunya sumber kebenaran** untuk
harga harian yang dipakai serve/audit. DuckDB tetap ada sebagai store OLAP
untuk backtest, tetapi statusnya turunan (mirror) dan tidak pernah ditulis
oleh jalur serve. Sinkronisasi eksplisit lewat skrip:

    python scripts/sync_duckdb_from_sqlite.py

Dengan begitu tidak ada dua penulis yang saling menimpa, dan jeda data bisa
diukur (`data_lag_days`) bukan ditebak.
"""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd
import polars as pl

from src.config import DB_PATH

PRICE_COLUMNS = ["ticker", "date", "open", "high", "low", "close", "volume"]
MAX_HISTORY_DAYS = 365


def _resolve(db_path: Path | str | None) -> Path:
    return Path(db_path) if db_path else Path(DB_PATH)


def sqlite_latest_date(db_path: Path | str | None = None) -> str | None:
    """Tanggal harga terbaru di SQLite (kanonik). None bila belum ada data."""
    path = _resolve(db_path)
    if not path.exists():
        return None
    conn = sqlite3.connect(str(path), timeout=30.0)
    try:
        row = conn.execute("SELECT MAX(date) FROM daily_prices").fetchone()
        return str(row[0])[:10] if row and row[0] else None
    except sqlite3.Error:
        return None
    finally:
        conn.close()


def duckdb_latest_date() -> str | None:
    """Tanggal harga terbaru di DuckDB (turunan). None bila belum ada data."""
    try:
        from src.database.duckdb_market import get_duckdb_connection

        conn = get_duckdb_connection()
        row = conn.execute("SELECT MAX(date) FROM daily_prices").fetchone()
        return str(row[0])[:10] if row and row[0] else None
    except Exception:
        return None


def data_lag_days(db_path: Path | str | None = None) -> int | None:
    """Berapa hari DuckDB tertinggal dari SQLite. None bila salah satu kosong.

    Positif = DuckDB lebih tua (backtest memakai harga basi).
    """
    canonical = sqlite_latest_date(db_path)
    derived = duckdb_latest_date()
    if not canonical or not derived:
        return None
    try:
        return (date.fromisoformat(canonical) - date.fromisoformat(derived)).days
    except ValueError:
        return None


def read_sqlite_prices(db_path: Path | str | None = None,
                       limit_days: int = MAX_HISTORY_DAYS) -> pd.DataFrame:
    """Baca harga harian dari SQLite (kanonik) untuk `limit_days` baris terakhir."""
    path = _resolve(db_path)
    if not path.exists():
        return pd.DataFrame(columns=PRICE_COLUMNS)
    limit = max(1, min(int(limit_days or MAX_HISTORY_DAYS), MAX_HISTORY_DAYS))
    conn = sqlite3.connect(str(path), timeout=30.0)
    try:
        frame = pd.read_sql_query(
            "SELECT ticker, date, open, high, low, close, volume FROM daily_prices "
            "ORDER BY ticker ASC, date ASC",
            conn,
        )
    except (sqlite3.Error, pd.errors.DatabaseError):
        return pd.DataFrame(columns=PRICE_COLUMNS)
    finally:
        conn.close()

    if frame.empty:
        return frame
    frame["ticker"] = frame["ticker"].astype(str).str.strip()
    frame["date"] = frame["date"].astype(str).str.slice(0, 10)
    return frame.groupby("ticker", group_keys=False).tail(limit).reset_index(drop=True)


def sync_duckdb_from_sqlite(limit_days: int = MAX_HISTORY_DAYS,
                             db_path: Path | str | None = None) -> dict:
    """Salin riwayat harga SQLite -> DuckDB (idempoten, INSERT OR REPLACE)."""
    from src.database.duckdb_market import save_daily_prices_polars

    frame = read_sqlite_prices(db_path, limit_days=limit_days)
    if frame.empty:
        return {
            "status": "error",
            "message": "SQLite belum berisi data harga",
            "tickers": 0,
            "rows": 0,
        }

    save_daily_prices_polars(pl.from_pandas(frame[PRICE_COLUMNS]))

    return {
        "status": "success",
        "tickers": int(frame["ticker"].nunique()),
        "rows": len(frame),
        "sqlite_latest": sqlite_latest_date(db_path),
        "duckdb_latest": duckdb_latest_date(),
    }
