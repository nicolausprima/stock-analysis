"""Backup harian ``data/signals_audit.db`` dengan retensi.

Dijalankan otomatis oleh scheduler setelah job 16:05, dan bisa juga dipanggil
manual/cron:

    python scripts/backup_audit_db.py
    python scripts/backup_audit_db.py --keep 14 --out /var/backups/stockai

Retensi menghapus file backup terlama di luar ``--keep`` file terbaru.
Exit code 1 bila backup gagal (agar cron/monitoring tahu).
"""
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.utils.db_backup import (
    DEFAULT_BACKUP_DIR,
    DEFAULT_DB_PATH,
    DEFAULT_KEEP,
    backup_sqlite_db,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup DB audit SQLite (VACUUM INTO).")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="path signals_audit.db")
    parser.add_argument("--out", default=str(DEFAULT_BACKUP_DIR), help="folder tujuan backup")
    parser.add_argument("--keep", type=int, default=DEFAULT_KEEP, help="jumlah backup yang disimpan")
    args = parser.parse_args()

    dest = backup_sqlite_db(args.db, args.out, keep=args.keep)
    return 0 if dest else 1


if __name__ == "__main__":
    raise SystemExit(main())
