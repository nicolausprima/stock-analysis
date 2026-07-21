# StockAI — Agent Guide

## Project
AI-Powered Day Trading Screener for Indonesia Stock Exchange (BEI/IDX). Python-only (no Node).

## Key Commands
```bash
pip install -r requirements.txt          # deps: yfinance, xgboost, fastapi, uvicorn, langchain-openai
pytest --verbose                          # run all tests (-v --tb=short from pytest.ini)
python -m uvicorn dashboard.backend.main:app --host 127.0.0.1 --port 8000 --reload   # dev server
python -c "from src.scheduler.daily_scheduler import run_daily_after_market_job; run_daily_after_market_job()"  # daily pipeline
python scripts/train_real_embedding_model.py   # retrain XGBoost on 5yr real data
```

## Architecture
- **Entrypoint:** `dashboard/backend/main.py` — FastAPI app (port 8000), serves frontend at `/`, background scheduler & Telegram listener on startup
- **Core:** `src/` — collector (batch yfinance), database (SQLite), features (technical indicators + embeddings), scheduler (08:30/16:05 WIB), Telegram bot
- **Routes:** 6 routers under `/api` in `dashboard/backend/routes/` (predict, chart, news, audit, narasi, telegram)
- **Frontend:** Vanilla HTML/CSS/JS (`dashboard/frontend/`)
- **Models:** `models/best_xgboost_optuna.pkl` + `models/standard_scaler.pkl`
- **Data:** `data/stock_market.db`, `data/signals_audit.db`, `data/latest_recommendations.json`, `data/tickers.txt` (732 BEI tickers)

## Testing
- 4 test files in `tests/` (12 tests total). Run with `pytest --verbose`
- `tests/conftest.py` sets `TESTING=true` env var — this disables background scheduler & Telegram listener threads (checked in `dashboard/backend/main.py:39` and `src/scheduler/daily_scheduler.py:206`)
- CI (`.github/workflows/ci.yml`) runs on `master` and `developments` branches, Python 3.10, same `pytest --verbose --tb=short` command with `TESTING=true`
- No formatter, linter, or typechecker configured in this repo

## Import Convention
Many modules resolve absolute imports via:
```python
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path: sys.path.append(str(PROJECT_ROOT))
```
Always use project-root-relative imports (e.g., `from src.config import ...`).

## Env & Config
- `.env` file required for TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, OPENAI_API_BASE, OPENAI_API_KEY
- `src/config.py` loads `.env` via `python-dotenv`, defines paths, trading params (3% profit target, batch size 50, 2s delay)
- Default TELEGRAM_BOT_TOKEN is hardcoded as fallback in `src/config.py:32`
- AI narrative layer uses OpenCode/DeepSeek via local proxy at `OPENAI_API_BASE`

## CI/CD Quirks
- `.github/workflows/daily_scan.yml` force-adds `.gitignore`d files: `git add -f data/signals_audit.db data/latest_recommendations.json` then auto-commits with `[skip ci]`
- Docker: `python:3.11-slim` base, `docker-compose.yml` maps port 8000, mounts `.` as volume, reads `.env`
- No pre-commit hooks configured

## Operational
- Scheduler runs at 08:30 WIB (pre-market) and 16:05 WIB (after-market), checking time every 30s in background thread
- Batch collector downloads 700+ tickers in 50-stock chunks with 2s delays to avoid Yahoo Finance rate limits
- `.gitignore` excludes `*.db`, `*.json`, `*.pkl`, `*.joblib` — these are generated artifacts
- Airflow DAG (`dags/stock_pipeline_dag.py`) is a placeholder (all commented out)
