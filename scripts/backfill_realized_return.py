"""Backfill `realized_return` + `exit_price` dari harga entry/target/stop nyata.

Latar belakang (audit 2026-10-30, D-01): versi lama menulis P&L LOSS sebagai
konstanta -1.5% padahal stop loss dihitung ATR-based (-1.2%..-2.0%). Akibatnya
win rate, total profit, equity curve, dan broadcast Telegram tidak akurat.

Cakupan sengaja SEMPIT — hanya baris LOSS yang nilainya masih konstanta -1.5
(atau NULL). Alasan:

- LOSS -> exit = stop_loss nyata (ATR-based), return dihitung dari harga.
- WIN  -> TIDAK disentuh: return-nya sudah berupa harga exit nyata (bisa jauh
  di atas target), sehingga menghitung ulang dari target_price justru
  merusak angka historis.
- PENDING -> tidak disentuh.

Default DRY-RUN. Tidak ada baris yang berubah tanpa `--apply`.

Contoh:
    python scripts/backfill_realized_return.py            # lihat selisih
    python scripts/backfill_realized_return.py --apply    # tulis ke DB
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.utils.paths import DATA_DIR

DB_PATH = DATA_DIR / "signals_audit.db"


def _recompute(row: sqlite3.Row) -> tuple[float, float] | None:
    """Return (exit_price, realized_return) yang seharusnya, atau None."""
    status = str(row["status"] or "").upper()
    if status not in ("WIN", "LOSS"):
        return None
    entry = float(row["entry_price"] or 0)
    exit_price = row["exit_price"]
    if exit_price is None:
        exit_price = row["target_price"] if status == "WIN" else row["stop_loss"]
    exit_price = float(exit_price or 0)
    if entry <= 0 or exit_price <= 0:
        return None
    return exit_price, round((exit_price - entry) / entry * 100, 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="tulis perubahan ke DB")
    parser.add_argument("--db", default=str(DB_PATH), help="path signals_audit.db")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"[ERROR] DB tidak ditemukan: {db_path}")
        return 1

    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        rows = conn.execute(
              "SELECT * FROM signals WHERE status = 'LOSS' "
            "AND (realized_return IS NULL OR ABS(realized_return + 1.5) < 0.001) "
            "ORDER BY id"
        ).fetchall()

        updates = []
        before_sum = 0.0
        after_sum = 0.0
        for row in rows:
            recomputed = _recompute(row)
            if recomputed is None:
                continue
            exit_price, new_return = recomputed
            old_return = row["realized_return"]
            before_sum += float(old_return or 0)
            after_sum += new_return
            if row["exit_price"] is None or old_return is None or abs(float(old_return) - new_return) > 0.005:
                updates.append((new_return, exit_price, row["id"]))

        print(f"DB        : {db_path}")
        print(f"Baris     : {len(rows)} sinyal LOSS dengan P&L konstanta/NULL")
        print(f"Perlu ubah: {len(updates)} baris")
        print(f"Sum return sebelum: {before_sum:+.1f}%")
        print(f"Sum return sesudah: {after_sum:+.1f}%")

        if not args.apply:
            print("\nDRY-RUN. Tambahkan --apply untuk menulis perubahan.")
            return 0

        with conn:
            conn.executemany(
                "UPDATE signals SET realized_return = ?, exit_price = ?, "
                "updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP) WHERE id = ?",
                updates,
            )
        print(f"\n[OK] {len(updates)} baris diperbarui.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
