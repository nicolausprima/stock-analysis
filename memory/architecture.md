# Architecture — AKSA Stock Analysis

Kembali ke: [[project-overview]]

## Aliran data (hulu → hilir)

1. Kolektor: `src/collector/` (yfinance via `dashboard/backend/yf_client.py` timeout 25 dtk, OpenBB, Akshare, fundamental) → mentah di `data/raw/price/`, fundamental di DuckDB.
2. Penyimpanan: `src/database/duckdb_market.py` (DuckDB + RLock + transaksi + view unik per-thread), `market_db.py` (SQLite WAL, rollback, validasi ticker), `duckdb_fundamental.py` (kolom `as_of DATE`, NULL bukan 0.0).
3. Fitur: `src/features/technical_indicators.py` (warm-up = NaN, drop, median train-only) → `embedding.py` → `build_features.py` (label next-session open-to-close ≥0.03, drop `FUTURE_COLS`, tulis `model_card.json`) → `data/processed/`.
4. Model: XGBoost + scaler di `models/` (26 kolom embed, cutoff 2025-04-21, embargo 5B). Serve: `src/screener.py:build_serve_matrix` (kolom urut expected, tolak `Tick_*`, tolak NaN) + assert di `src/scheduler/daily_scheduler.py`.
5. Konsensus: `src/agents/multi_agent_v2.py` (teknikal, fundamental point-in-time max 120 hari, sentimen, debat bull/bear, risk manager) + `src/explainability/shap_explainer.py` (tolak NaN, bukan default 0.0).
6. Backtest: `src/backtest/vectorized_backtest.py` (fill next-bar open + slippage, lot-100, cap 10% volume, komisi 0.15/0.25%).
7. Saji: FastAPI `dashboard/backend/` (auth `X-API-Key`, clamp chart 1–365 hari, escape HTML, guardrail narasi, rate-limit, disclaimer) → `dashboard/frontend/` (vanilla JS + CSS) + `src/notifications/telegram_bot.py` (allowlist fail-closed, cooldown 60 dtk, single-flight, disclaimer tiap pesan).
8. Jadwal: `src/scheduler/daily_scheduler.py` (4 fase WIB: 08:30 radar, 12:00 recap, 15:30 BSJP, 16:05 audit).

## Stack

Python 3.11 pinned (`requirements.txt`): yfinance, pandas, ta, xgboost, scikit-learn, FastAPI/uvicorn, DuckDB+Polars, SHAP, vectorbt, feedparser, pytest. Frontend: HTML/CSS/JS vanilla + satu komponen `components/ui/loading-state.tsx`. CI: pytest + ruff hard-fail + pip-audit + smoke + docker build. Lihat [[glossary]] untuk singkatan domain.

## Keputusan desain penting (kenapa)

- Pipeline tunggal + `model_card.json` + assert skema: cegah train/serve skew yang dulu bikin seluruh sinyal invalid. Lihat [[decisions/2026-09-22-single-pipeline-parity]].
- Warm-up NaN + median train-only (bukan fill-0): fill-0 bikin sinyal palsu + SHAP menyesatkan.
- Backtest next-bar open + lot + cost: eksekusi realistis, bukan isi harga khayal.
- Telegram fail-closed + cooldown + disclaimer: cegah takeover bot, DoS scan, dan kesan nasihat investasi. Lihat [[decisions/2026-09-23-fail-closed-telegram]].
- Ruff baseline terarah per-file (bukan silent global): CI hijau tanpa sembunyikan risiko. Lihat [[decisions/2026-09-23-ruff-baseline-terarah]].
- Copy "simulasi" + tanpa janji profit: kepatuhan OJK/UU P2SK. Lihat [[decisions/2026-09-23-copy-legal-simulasi]].
