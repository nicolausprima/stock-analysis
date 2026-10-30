"""Tes alarm operasional & backup DB (audit 2026-10-30)."""
import json
import sqlite3
from datetime import UTC, datetime, timedelta

from src.observability import alerts
from src.utils.db_backup import backup_sqlite_db


def _make_snapshot(path, generated_at):
    path.write_text(
        json.dumps({"status": "success", "generated_at": generated_at.isoformat()}),
        encoding="utf-8",
    )
    return path


def _sample_db(path, rows=3):
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE signals (id INTEGER PRIMARY KEY, ticker TEXT)")
        conn.executemany(
            "INSERT INTO signals (ticker) VALUES (?)", [("BBCA.JK",) for _ in range(rows)]
        )
        conn.commit()
    return path


def test_snapshot_missing_is_stale(tmp_path):
    status = alerts.snapshot_status(tmp_path / "tidak-ada.json")
    assert status["snapshot_present"] is False
    assert status["stale"] is True
    assert status["age_minutes"] is None


def test_snapshot_fresh_and_stale(tmp_path):
    fresh = _make_snapshot(tmp_path / "fresh.json", datetime.now(UTC) - timedelta(minutes=5))
    status = alerts.snapshot_status(fresh, max_age_hours=24)
    assert status["stale"] is False
    assert 4 <= status["age_minutes"] <= 6

    old = _make_snapshot(tmp_path / "old.json", datetime.now(UTC) - timedelta(hours=30))
    status = alerts.snapshot_status(old, max_age_hours=24)
    assert status["stale"] is True
    assert status["age_minutes"] >= 30 * 60


def test_snapshot_broken_json_falls_back_to_mtime(tmp_path):
    broken = tmp_path / "broken.json"
    broken.write_text("{bukan json", encoding="utf-8")
    age = alerts.snapshot_age_minutes(broken)
    assert age is not None and age < 5


def test_alert_not_sent_in_testing_mode():
    assert alerts.send_ops_alert("uji") is False


def test_alert_once_per_day_only_first_call():
    alerts._alerted_on.clear()
    assert alerts.send_ops_alert_once("uji", kind="tes-sekali") is False
    assert alerts._alerted_on["tes-sekali"] == alerts.now_wib().strftime("%Y-%m-%d")


def test_backup_copies_rows_and_prunes_old_files(tmp_path):
    db = _sample_db(tmp_path / "signals_audit.db", rows=4)
    out = tmp_path / "backups"
    first = backup_sqlite_db(db, out, keep=2, stamp=datetime(2026, 10, 28, 16, 5, tzinfo=UTC))
    second = backup_sqlite_db(db, out, keep=2, stamp=datetime(2026, 10, 29, 16, 5, tzinfo=UTC))
    third = backup_sqlite_db(db, out, keep=2, stamp=datetime(2026, 10, 30, 16, 5, tzinfo=UTC))

    assert first and second and third
    assert first.name != second.name
    with sqlite3.connect(third) as conn:
        assert conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0] == 4
    remaining = sorted(p.name for p in out.glob("*.db"))
    assert remaining == sorted([second.name, third.name])


def test_backup_rejects_non_sqlite_file(tmp_path):
    fake = tmp_path / "nyasar.db"
    fake.write_bytes(b"version https://git-lfs.github.com/spec/v1\n")
    assert backup_sqlite_db(fake, tmp_path / "out") is None
    assert not (tmp_path / "out" / "nyasar.db").exists()
