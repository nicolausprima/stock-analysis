# Glossary

Kembali ke: [[project-overview]]

| Istilah | Arti |
|---|---|
| AKSA | Analisis Kuantitatif Saham — nama proyek ini |
| IDX/BEI | Bursa Efek Indonesia (Indonesia Stock Exchange) |
| IHSG | Indeks Harga Saham Gabungan — benchmark pasar |
| SIM-WIN / SIM-LOSS | Menang/kalah dalam simulasi backtest, BUKAN profit nyata |
| TP/SL | Target Profit / Stop Loss (model: +3.0% / −1.5%) |
| BSJP | Beli Sore Jual Pagi — scan momentum 15:30 WIB, jual pagi berikut |
| Warm-up | Bar awal tanpa lookback penuh — indikator = NaN lalu drop, bukan 0 |
| `Tick_*` | Skema one-hot lama (basi) — serve wajib tolak |
| `Embed_*` | Skema embedding 26 kolom aktif |
| `model_card.json` | Metadata artefak: target, horizon, cutoff, embargo, feature_cols |
| Embargo 5B | Jeda 5 hari bursa antara train dan test anti-leakage |
| Fail-closed | Tanpa allowlist = tolak semua (Telegram) |
| Allowlist | `TELEGRAM_CHAT_ID` + `TELEGRAM_ALLOWED_CHAT_IDS` |
| DYOR | Do Your Own Research — risiko milik pengguna |
| P0/P1/P2 | Severity: blokir rilis / penting / minor |
| S-1…S-8 | ID sisa temuan di `../VERIFICATION_REPORT_2026-09-23.md` §6 |
| OJK/UU P2SK | Regulator dan UU sektor keuangan — alasan copy legal ketat |
| WCAG | Standar aksesibilitas web (target 44px, fokus, motion, live region) |
