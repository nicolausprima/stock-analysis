# Known Issues

Kembali ke: [[project-overview]]. Diketahui, belum diperbaiki — cek sini sebelum lapor temuan baru.

- 2026-09-23 SELESAI S-4/S-5/S-6/S-7/S-8 (detail `../VERIFICATION_REPORT_2026-09-23.md`).
- Ruff ignores terarah di `ruff.toml` (BLE001/S110/S112/LOG015/DTZ per-file) — hapus = perbaiki call-site dulu.
- `data/signals_audit.db` berubah tiap run — jangan commit (revert 2026-09-23).
- `models/model_card.json` + `data/processed/model_card.json` gitignored (tidak ter-track) — regenerasi tiap retrain.
- Hanya 89/732 ticker ada CSV lokal (`data/raw/price/`); IHSG offline → `IHSG_Return=0.0` sesuai guard.
- Panel dashboard: recom sembunyi via class, audit via inline style — inkonsisten tapi fungsi benar.
- CATATAN: `embedding.py` kini propagasi NaN — artefak S-1 (retrain sebelum S-5) berperilaku warm-up lama; retrain ulang sebelum klaim parity artefak.
