"""Pulihkan/merge `data/signals_audit.db` dari backup, karantina, atau artifact CI.

Sejak audit 2026-10-30 (C-03) DB audit tidak lagi di-commit ke git, jadi
deployment baru mulai dengan riwayat kosong. Skrip ini menyalin riwayat dari
sumber yang dipercaya TANPA menimpa baris yang sudah ada.

Sumber yang dicari otomatis bila `--from` tidak diberikan (terbaru dulu):
    data/signals_audit.backup-*.db
    data/signals_audit.db.corrupt-*
    artifacts/**/signals_audit.db

Sifat operasi:
- Validasi sumber: header SQLite, `PRAGMA integrity_check`, tabel `signals`.
- Target kosong/hilang -> salinan atomik utuh.
- Target sudah ada    -> MERGE: hanya baris yang belum ada yang dimasukkan
  (kunci natural: ticker + created_at + source), lalu jumlahnya dilaporkan.
- Default DRY-RUN; tambahkan `--apply` untuk menulis.

Contoh:
    python scripts/restore_audit_db.py                       # lihat rencana
    python scripts/restore_audit_db.py --apply               # jalankan
    python scripts/restore_audit_db.py --from backup.db --apply
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.utils.paths import DATA_DIR
from src.utils.sqlite_guard import is_sqlite_file

DB_PATH = DATA_DIR / "signals_audit.db"
NATURAL_KEY = ("ticker", "created_at", "source")


def _validate(path: Path) -> sqlite3.Connection:
    """Buka & validasi kandidat DB. Raise RuntimeError bila tidak layak."""
    if not path.exists():
        raise RuntimeError(f"Sumber tidak ditemukan: {path}")
    if not is_sqlite_file(path):
        raise RuntimeError(f"Bukan file SQLite valid (pointer LFS?): {path}")

    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10.0)
    try:
        ok = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if ok != "ok":
            raise RuntimeError(f"integrity_check gagal pada {path}: {ok}")
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        if "signals" not in tables:
            raise RuntimeError(f"Tabel 'signals' tidak ada di {path}")
    except Exception:
        conn.close()
        raise
    return conn


def _columns(conn: sqlite3.Connection, table: str = "signals") -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


def _candidates() -> list[Path]:
    found: list[Path] = []
    found += sorted(DATA_DIR.glob("signals_audit.backup-*.db"))
    found += sorted(DATA_DIR.glob("signals_audit.db.corrupt-*"))
    artifacts = PROJECT_ROOT / "artifacts"
    if artifacts.exists():
        found += sorted(artifacts.rglob("signals_audit.db"))
    return [p for p in found if p.is_file()]


def _count(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="source", help="path DB sumber")
    parser.add_argument("--to", dest="target", default=str(DB_PATH), help="path DB tujuan")
    parser.add_argument("--apply", action="store_true", help="tulis perubahan")
    args = parser.parse_args()

    target = Path(args.target)
    source = Path(args.source) if args.source else next(iter(_candidates()), None)
    if source is None:
        print("[ERROR] Tidak ada kandidat backup/artifact. Berikan --from <path>.")
        return 1

    try:
        src = _validate(Path(source))
    except Exception as exc:
        print(f"[ERROR] {exc}")
        return 1

    src_count = _count(src)
    print(f"Sumber : {source} ({src_count} sinyal)")

    if not target.exists() or target.stat().st_size == 0:
        print(f"Target : {target} (belum ada) -> salinan penuh")
        if not args.apply:
            print("\nDRY-RUN. Tambahkan --apply untuk menulis.")
            src.close()
            return 0
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=".restore-", suffix=".db", dir=str(target.parent))
        import os

        os.close(fd)
        try:
            shutil.copy2(source, tmp_name)
            check = _validate(Path(tmp_name))
            check.close()
            os.replace(tmp_name, target)
        except Exception as exc:
            Path(tmp_name).unlink(missing_ok=True)
            print(f"[ERROR] Restore gagal: {exc}")
            src.close()
            return 1
        src.close()
        print(f"[OK] DB dipulihkan ({src_count} sinyal).")
        return 0

    dst = _validate(target)
    dst_count = _count(dst)
    shared = [c for c in _columns(src) if c in _columns(dst) and c != "id"]
    key_cols = [c for c in NATURAL_KEY if c in shared]
    if len(key_cols) != len(NATURAL_KEY):
        print(f"[ERROR] Kolom kunci {NATURAL_KEY} tidak lengkap di target: {key_cols}")
        src.close()
        dst.close()
        return 1

    where = " AND ".join(f"{c} = ?" for c in key_cols)
    missing = []
    for row in src.execute(f"SELECT {', '.join(shared)} FROM signals"):
        record = dict(zip(shared, row, strict=True))
        exists = dst.execute(
            f"SELECT 1 FROM signals WHERE {where} LIMIT 1",
            tuple(record[c] for c in key_cols),
        ).fetchone()
        if not exists:
            missing.append(tuple(record[c] for c in shared))

    print(f"Target : {target} ({dst_count} sinyal)")
    print(f"Baris baru dari sumber: {len(missing)}")

    if not args.apply:
        print("\nDRY-RUN. Tambahkan --apply untuk menulis.")
        src.close()
        dst.close()
        return 0

    if missing:
        placeholders = ", ".join("?" for _ in shared)
        with dst:
            dst.executemany(
                f"INSERT INTO signals ({', '.join(shared)}) VALUES ({placeholders})",
                missing,
            )
    src.close()
    print(f"Total sinyal setelah merge: {_count(dst)}")
    dst.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
