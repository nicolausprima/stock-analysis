"""Penulisan JSON atomik untuk snapshot cache (audit 2026-10-30, C-02).

Masalah yang diperbaiki: `open(path, 'w')` + `json.dump()` menulis langsung ke
file final. Pembaca yang masuk di tengah penulisan melihat payload terpotong,
menganggap cache rusak, lalu memicu scan ulang / data contoh.

Strategi: tulis ke file sementara di direktori yang sama, `fsync`, lalu
`os.replace()` (atomik di POSIX maupun NTFS). Pembaca selalu melihat versi
lama yang utuh atau versi baru yang utuh — tidak pernah setengah jadi.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def write_json_atomic(path: str | Path, payload: object, *, indent: int = 2) -> Path:
    """Tulis ``payload`` sebagai JSON ke ``path`` secara atomik.

    Return path final. File sementara selalu dibersihkan bila terjadi error.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=indent, default=str)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return target


def read_json(path: str | Path) -> object | None:
    """Baca JSON; return None bila file tidak ada atau tidak valid."""
    target = Path(path)
    if not target.exists():
        return None
    try:
        with open(target, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None
