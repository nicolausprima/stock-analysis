"""Tandai baris audit lama sebagai backtest simulasi (``source='seed'``).

Latar belakang: sebelum kolom ``source`` dipakai konsisten, hasil "Simulasi 6
Bulan" tersimpan dengan ``source='scan'``. Akibatnya kartu "Scan Harian Nyata"
menampilkan angka simulasi (audit 2026-10-30). Skrip ini mengganti label baris
sebelum tanggal batas menjadi ``seed`` supaya rekap per sumber jujur.

Default DRY-RUN (hanya menghitung). Perubahan data hanya terjadi dengan
``--apply`` dan tanggal batas eksplisit:

    python scripts/classify_legacy_audit_rows.py --before 2026-10-01
    python scripts/classify_legacy_audit_rows.py --before 2026-10-01 --apply

Catatan: baris berlabel ``seed`` akan dihapus bila tombol "Jalankan Simulasi
6 Bulan (Lab)" ditekan — itu memang perilaku seed (digenerate ulang).
"""
import argparse
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "signals_audit.db"


def main() -> int:
    parser = argparse.ArgumentParser(description="Relabel baris audit lama jadi source='seed'.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument(
        "--before",
        required=True,
        help="Batas eksklusif YYYY-MM-DD: baris dengan created_at < batas akan dilabeli seed.",
    )
    parser.add_argument("--apply", action="store_true", help="Tulis perubahan (default dry-run).")
    args = parser.parse_args()

    db = Path(args.db)
    if not db.exists():
        print(f"[CLASSIFY] DB tidak ditemukan: {db}")
        return 1
    if len(args.before) != 10 or args.before[4] != "-" or args.before[7] != "-":
        print("[CLASSIFY] Format --before harus YYYY-MM-DD.")
        return 1

    with sqlite3.connect(str(db)) as conn:
        dist = conn.execute(
            "SELECT source, COUNT(*) FROM signals GROUP BY source ORDER BY source"
        ).fetchall()
        print("[CLASSIFY] Distribusi source sekarang:", dist or "(kosong)")

        rows = conn.execute(
            "SELECT status, COUNT(*), MIN(created_at), MAX(created_at) "
            "FROM signals WHERE source = 'scan' AND date(created_at) < date(?) "
            "GROUP BY status",
            (args.before,),
        ).fetchall()
        if not rows:
            print(f"[CLASSIFY] Tidak ada baris scan sebelum {args.before}. Tidak ada perubahan.")
            return 0

        total = 0
        for status, count, earliest, latest in rows:
            print(f"[CLASSIFY]   {status or 'PENDING'}: {count} ({earliest} s/d {latest})")
            total += count
        print(f"[CLASSIFY] Total kandidat {total} baris (< {args.before}).")

        if not args.apply:
            print("[CLASSIFY] DRY-RUN. Jalankan ulang dengan --apply untuk menulis.")
            return 0

        cur = conn.execute(
            "UPDATE signals SET source = 'seed', "
            "updated_at = datetime('now', 'localtime') "
            "WHERE source = 'scan' AND date(created_at) < date(?)",
            (args.before,),
        )
        conn.commit()
        print(f"[CLASSIFY] Selesai: {cur.rowcount} baris dilabeli 'seed'.")
        print(
            "[CLASSIFY] Distribusi baru:",
            conn.execute(
                "SELECT source, COUNT(*) FROM signals GROUP BY source ORDER BY source"
            ).fetchall(),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
