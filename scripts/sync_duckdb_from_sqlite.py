"""Sinkronkan mirror DuckDB dari SQLite (kanonik), lalu laporkan jeda data.

Dipakai sebelum backtest vektor agar backtest tidak memakai harga yang lebih
tua dari sinyal harian (audit 2026-10-30, D-03).

Contoh:
    python scripts/sync_duckdb_from_sqlite.py --check   # lihat jeda saja
    python scripts/sync_duckdb_from_sqlite.py           # sinkronkan
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.database.sync_market import (
    data_lag_days,
    duckdb_latest_date,
    sqlite_latest_date,
    sync_duckdb_from_sqlite,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="hanya laporkan jeda data")
    parser.add_argument("--days", type=int, default=365, help="kedalaman riwayat (default 365)")
    args = parser.parse_args()

    print(f"SQLite (kanonik) terbaru : {sqlite_latest_date()}")
    print(f"DuckDB  (turunan) terbaru: {duckdb_latest_date()}")
    lag = data_lag_days()
    print(f"Jeda                     : {'tidak diketahui' if lag is None else f'{lag} hari'}")

    if args.check:
        return 0

    result = sync_duckdb_from_sqlite(limit_days=args.days)
    print(result)
    if result.get("status") != "success":
        return 1

    remaining = data_lag_days()
    print(f"Jeda setelah sinkron     : {remaining} hari")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
