"""Penjaga file SQLite: karantina, JANGAN hapus.

Latar belakang (audit 2026-10-30, B-05): `_ensure_valid_db` versi lama menghapus
file DB bila header 16 byte pertama bukan "SQLite format 3". Pada kasus nyata
file itu bukan sampah — ia Git LFS pointer 131 byte (akibat DB biner di-commit),
salinan yang terpotong, atau file yang masih di-sync. Menghapusnya membuat
riwayat audit hilang permanen tanpa jejak.

Perilaku baru: file dipindahkan ke `<nama>.corrupt-<timestamp>` (beserta
`-wal`/`-shm`) sehingga bisa diperiksa/dipulihkan, lalu proses berjalan dengan
DB baru yang kosong. Semua langkah dicetak, tidak ada kegagalan senyap.
"""
from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

SQLITE_MAGIC = b"SQLite format 3"


def is_sqlite_file(path: str | Path) -> bool:
    """True bila file ada dan diawali header SQLite yang valid."""
    target = Path(path)
    try:
        if not target.exists() or target.stat().st_size == 0:
            return False
        with open(target, "rb") as handle:
            return handle.read(16).startswith(SQLITE_MAGIC)
    except OSError:
        return False


def quarantine_if_not_sqlite(path: str | Path) -> Path | None:
    """Pindahkan file non-SQLite ke karantina. Return path karantina atau None.

    Tidak pernah menghapus data. ``-wal``/``-shm`` ikut dipindah agar tidak
    tertinggal sebagai pasangan yatim milik DB baru.
    """
    target = Path(path)
    if not target.exists() or is_sqlite_file(target):
        return None

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    quarantined = target.with_name(f"{target.name}.corrupt-{stamp}")
    try:
        shutil.move(str(target), str(quarantined))
    except OSError as exc:
        print(
            f"[DB] PERINGATAN: {target.name} bukan SQLite valid dan gagal "
            f"dikarantina ({exc!s}). Periksa manual sebelum melanjutkan."
        )
        raise RuntimeError(
            f"{target} bukan file SQLite valid dan tidak bisa dipindahkan otomatis."
        ) from exc

    print(
        f"[DB] {target.name} bukan SQLite valid (kemungkinan pointer LFS / file "
        f"terpotong). Dipindahkan ke {quarantined.name}; riwayat TIDAK dihapus. "
        "Pulihkan dari file karantina/backup bila ini tidak disengaja."
    )

    for suffix in ("-wal", "-shm"):
        sidecar = target.with_name(target.name + suffix)
        if sidecar.exists():
            try:
                shutil.move(str(sidecar), str(quarantined.with_name(quarantined.name + suffix)))
            except OSError:
                pass
    return quarantined
