"""Backup harian DB audit SQLite tanpa memblokir pembaca.

``VACUUM INTO`` menghasilkan salinan konsisten dalam satu transaksi baca,
jadi aman dijalankan saat dashboard sedang melayani request (tidak seperti
menyalin file mentah + ``-wal`` yang bisa menghasilkan DB rusak).

Retensi default 7 hari (harian). Kegagalan backup hanya dicatat/dikembalikan,
tidak pernah melempar exception ke pemanggil scheduler (audit 2026-10-30).
"""
import sqlite3
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "signals_audit.db"
DEFAULT_BACKUP_DIR = PROJECT_ROOT / "data" / "backups"
DEFAULT_KEEP = 7
# Nama backup memakai WIB agar cocok dengan jam scan di dashboard/log.
WIB = timezone(timedelta(hours=7))


def sqlite_header_ok(path: Path) -> bool:
    """True bila file benar-benar SQLite (bukan pointer LFS / file kosong)."""
    try:
        with open(path, "rb") as fh:
            return fh.read(16).startswith(b"SQLite format 3")
    except OSError:
        return False


def backup_sqlite_db(
    db_path: Path | str = DEFAULT_DB_PATH,
    out_dir: Path | str = DEFAULT_BACKUP_DIR,
    keep: int = DEFAULT_KEEP,
    stamp: datetime | None = None,
) -> Path | None:
    """Buat ``<nama>-YYYYMMDD-HHMMSS.db`` lalu pangkas backup lama.

    Return path backup baru, atau ``None`` bila sumber tidak ada/tidak valid
    atau proses backup gagal (alasan dicetak ke stdout).
    """
    src = Path(db_path)
    if not src.exists():
        print(f"[BACKUP] Dilewati: {src} tidak ada.")
        return None
    if not sqlite_header_ok(src):
        print(f"[BACKUP] Dilewati: {src} bukan file SQLite valid (pointer LFS / rusak).")
        return None

    target_dir = Path(out_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    moment = (stamp or datetime.now(UTC)).astimezone(WIB)
    dest = target_dir / f"{src.stem}-{moment.strftime('%Y%m%d-%H%M%S')}.db"

    try:
        # VACUUM INTO menolak menimpa file yang sudah ada: hapus sisa run
        # dengan detik yang sama agar backup ulang tetap berhasil.
        if dest.exists():
            dest.unlink()
        with sqlite3.connect(str(src), timeout=60) as conn:
            conn.execute("VACUUM INTO ?", (str(dest),))
    except sqlite3.Error as exc:
        print(f"[BACKUP] Gagal membuat backup: {exc!s}")
        return None

    if not sqlite_header_ok(dest) or dest.stat().st_size == 0:
        print("[BACKUP] Gagal: hasil backup tidak valid, file dibuang.")
        dest.unlink(missing_ok=True)
        return None

    _prune(target_dir, keep)
    print(f"[BACKUP] OK: {dest.name} ({dest.stat().st_size / 1024:.0f} KB), retensi {keep} file.")
    return dest


def _prune(out_dir: Path, keep: int) -> None:
    if keep <= 0:
        return
    backups = sorted(out_dir.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in backups[keep:]:
        try:
            old.unlink()
            print(f"[BACKUP] Hapus backup lama: {old.name}")
        except OSError as exc:
            print(f"[BACKUP] Gagal menghapus {old.name}: {exc!s}")
