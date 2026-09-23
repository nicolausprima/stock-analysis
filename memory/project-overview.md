# Project Overview — AKSA Stock Analysis

Pintu masuk vault. Semua note lain taut balik ke sini.

## Apa ini

AKSA (Analisis Kuantitatif Saham): screener saham harian Bursa Efek Indonesia (IDX/BEI) berbasis kuantitatif. Pindai 700+ ticker aktif tiap hari pakai XGBoost Classifier + Dense Chart Feature Embeddings, lapis fundamental (PER/PBV/ROE/DER), sentimen, konsensus multi-agent, backtest vektor realistis. Output: rekomendasi Top-10, analisis per ticker, broadcast Telegram 4 fase, dashboard web.

## Tujuan

Riset kuantitatif + edukasi. BUKAN nasihat investasi, BUKAN robo-advisory berlisensi. Semua angka profit = hasil simulasi backtest (gross-of-cost), bukan hasil nyata, bukan jaminan. Lihat [[glossary]] (SIM-WIN, BSJP, TP/SL) dan [[decisions/2026-09-23-copy-legal-simulasi]].

## Pengguna

- Pemilik/pengembang: riset strategi, audit track record simulasi.
- Pembaca dashboard/Telegram: edukasi, DYOR. Wajib baca disclaimer di hero, CTA, footer, tiap broadcast.

## Status saat ini

Aktif, branch `developments` (basis `f64f5ea`, worktree kotor belum di-commit per 2026-09-23).
Terakhir: S-1 retrain artefak SELESAI, S-2 ruff 0 errors SELESAI, S-3 token/allowlist oleh user, S-4–S-8 pending. Detail: [[progress/2026-09-23-verifikasi-dan-sisa]], [[todo]], [[known-issues]].
Uji: `uv run pytest tests/ -q` = 52 passed; `ruff check .` = All checks passed; notebook 02 VALID; `node --check app.js` OK.

## Peta note

- Teknis: [[architecture]], [[conventions]], [[glossary]]
- Riwayat kenapa: [[decisions/2026-09-22-single-pipeline-parity]], [[decisions/2026-09-23-ruff-baseline-terarah]], [[decisions/2026-09-23-copy-legal-simulasi]], [[decisions/2026-09-23-fail-closed-telegram]]
- Kerja: [[progress/2026-09-23-verifikasi-dan-sisa]], [[todo]], [[known-issues]]
- Bukti audit repo: `../AUDIT_REPORT_2026-09-22.md`, `../VERIFICATION_REPORT_2026-09-23.md` (di root repo, bukan vault)
