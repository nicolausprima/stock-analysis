import os
import tempfile
from pathlib import Path

# Direct global environment configuration for Pytest test suite
os.environ["TESTING"] = "true"

# Isolasi DuckDB antar-test run: pakai file temp per-worker agar tidak lock
# file produksi data/stock_*.duckdb (penyebab flaky 42 vs 43 passed).
_tmpdir = Path(tempfile.gettempdir()) / f"stockai-test-{os.getpid()}"
_tmpdir.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("DUCKDB_FUNDAMENTAL_PATH", str(_tmpdir / "stock_fundamentals.duckdb"))
os.environ.setdefault("DUCKDB_MARKET_PATH", str(_tmpdir / "stock_market.duckdb"))

import pytest


@pytest.fixture(autouse=True)
def _isolate_duckdb(tmp_path, monkeypatch):
    """Setiap test pakai file DuckDB sendiri + tutup koneksi setelah test."""
    fund = tmp_path / "fundamentals.duckdb"
    mkt = tmp_path / "market.duckdb"
    monkeypatch.setenv("DUCKDB_FUNDAMENTAL_PATH", str(fund))
    monkeypatch.setenv("DUCKDB_MARKET_PATH", str(mkt))
    try:
        from src.database import duckdb_fundamental as _f
        _f.set_fundamental_db_path(str(fund))
    except Exception:
        pass
    try:
        from src.database import duckdb_market as _m
        _m.set_market_db_path(str(mkt))
    except Exception:
        pass
    yield
    try:
        from src.database import duckdb_fundamental as _f
        _f.close_fundamental_db()
    except Exception:
        pass
    try:
        from src.database import duckdb_market as _m
        _m.close_connection()
    except Exception:
        pass
