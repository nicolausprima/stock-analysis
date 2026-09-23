# ADR 2026-09-23 — Ruff baseline terarah per-file

Kembali ke: [[../project-overview]]

## Masalah

`ruff check .` = 461 errors → CI hard-fail, merge tertahan.

## Opsi

1. Matikan gate ruff di CI — ditolak: hilangkan pengaman.
2. `--fix` buta semua — ditolak: risiko ubah logika.
3. Auto-fix aman + `ruff.toml` per-file-ignores beralasan (dipilih).

## Keputusan

Opsi 3: auto-fix ~255 (I001, UP, F401, F541, RUF, SIM, PLR aman + manual minimal tanpa ubah logika); `ruff.toml` exclude `_retrain_tmp.py`/notebooks/data, per-file-ignore BLE001/S110/S112/LOG015/DTZ per modul dengan alasan, tanpa `select` global. Hasil: 0 errors, pytest 52 passed.

## Konsekuensi

Hapus satu ignore = perbaiki call-site dulu (review manual). Sisa tercatat di [[../known-issues]].
