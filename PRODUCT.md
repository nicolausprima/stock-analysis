# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Retail trader IDX (BEI). Butuh screener harian cepat sebelum / saat jam bursa: scan Top 10, deep-dive per ticker, narasi quant Bahasa Indonesia, TP/SL + sizing siap eksekusi manual. Bukan operator institusi, bukan algo-execution otomatis.

## Product Purpose

AKSA (Analisis Kuantitatif Saham) = screener kuantitatif harian untuk 700+ ticker aktif BEI. Scan DuckDB + Polars, skor XGBoost + embedding chart, jelaskan via SHAP + debat multi-agent, keluarkan rekomendasi + ATR TP/SL + Kelly sizing + cache JSON + broadcast Telegram. Sukses = trader dapat daftar pantau pagi/sore yang konsisten, teraudit, tanpa klaim jaminan profit.

## Positioning

Pipeline tunggal teraudit: XGBoost Classifier + Dense Chart Embedding + SHAP TreeExplainer + konsensus 5-agent V2 (Technical, Fundamental, Sentiment, Bull/Bear Debate, Risk Manager) + ATR TP/SL dinamis + Half-Kelly sizing + audit track-record time-aware WIB. Pesaing tampilkan skor; AKSA tampilkan driver positif/negatif per prediksi + debat + audit SIM-WIN/LOSS.

## Operating Context

Jam BEI WIB, 4 fase Telegram: 08:30 Morning Radar (pre-open 09:00), 12:00 Midday Recap sesi 1, 15:30 BSJP Radar (buy 15:30-15:50, jual open besok), 16:05 After-Market Audit + update SQLite + cache JSON. CLI interaktif `python main_cli.py`: /scan, /analyze <TICKER>, /macro, /audit, /sizing, /chart, /help. Dashboard web `http://127.0.0.1:8000` + Swagger `/docs`. Ritual harian: scheduler 15:30/16:05 ingest batch 50 ticker/chunk, guard suspend/delist, indikator, inferensi, booster sektor, filter sentimen, cache.

## Capabilities and Constraints

Fungsi: batch ingest yfinance + OpenBB SDK + Akshare fallback; indikator 30+ (ADX, RVOL, MFI, Stochastic, EMA Cross, Williams %R, CCI); rotasi 11 sektor IDX + booster top-3 +2.0%; macro guard IHSG (USD/IDR, DXY, Nikkei, Wall St, komoditas) mode NORMAL/CAUTIOUS/BLOCK; sentimen lexicon ID/EN + Asymmetric Risk Veto -25% + cache SQLite 24h; valuasi fundamental (PER, PBV, ROE, DER, Market Cap, Dividend Yield); backtest vectorized vectorbt (komisi buy 0.15%, sell 0.25%, slippage 0.10%, ATR exit); narasi DeepSeek LLM / fallback keyword; API FastAPI + Uvicorn; hardening (CSP, headers, X-API-Key proxy LLM, escaping XSS, regex validasi).

Batasan abadi: edukasi/riset kuantitatif saja, bukan advice finansial. Semua angka performa = simulasi backtest hipotetis gross-of-cost, bukan hasil nyata, bukan jaminan. Metodologi teraudit belum publikasi. Verifikasi via `pytest` (52 passed). Data via yfinance/OpenBB/Akshare, bisa stale/gap; guard suspend (volume nol 5 hari, harga beku 10 hari) + filter delist. Undecided: tidak ada.

## Brand Commitments

Nama AKSA — Analisis Kuantitatif Saham · Autonomous IDX Screener. Voice Indonesia karış Inggris quant, disclaimer edukasi selalu tampil. UI incumbent: Helin-inspired white-card system, tipografi Instrument Serif + Montserrat + ui-monospace, Lightweight Charts, kartu putih elevation Helin. Klaim UI sub-5ms via pre-computed JSON cache.

## Evidence on Hand

Kode: `dashboard/backend/main.py`, `dashboard/frontend/dashboard.html`, `src/screener.py`, `src/agents/multi_agent_v2.py`, `src/explainability/shap_explainer.py`, `src/backtest/vectorized_backtest.py`. Dokumen: `README.md`, `AUDIT_REPORT_2026-09-22.md`, `VERIFICATION_REPORT_2026-09-23.md`, `SCHEDULER_REVIEW.md`, `ML_PIPELINE_ROBUSTNESS_REVIEW.md`. Data: `data/latest_recommendations.json` (cache), SQLite audit store. Absen: tidak ada testimoni, pelanggan, benchmark independen, pricing; jangan fabrikasi.

## Product Principles

1. Jujur simulasi: label SIM-WIN/hipotetis, jangan samarkan sebagai real.
2. Satu pipeline, satu audit: paritas CLI/API/Telegram, time-aware WIB.
3. Jelaskan tiap skor: SHAP driver + debat + risk verdict, bukan angka polos.
4. Cepat tapi aman: cache instan, guard suspend/delist/macro/sentimen veto.
5. Risiko dulu: ATR TP/SL + Half-Kelly + BLOCK mode di atasConviction.

## Accessibility & Inclusion

Kebutuhan produk: Bahasa Indonesia default, kontras terbaca untuk tabel quant, keyboard-navigable dashboard. Standar formal belum ditetapkan.
