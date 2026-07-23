# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

StockAI is an AI-powered day trading screener for the Indonesia Stock Exchange (IDX/BEI). It scans 700+ BEI tickers daily using an XGBoost classifier trained on 5 years of historical data with 20+ technical indicators, dense feature embeddings, an IHSG Market Regime Guard, and an asymmetric AI news sentiment filter. Outputs are served via a FastAPI web dashboard (sub-5ms via JSON cache) and a 4-phase Telegram broadcast system (08:30, 12:00, 15:30, 16:05 WIB).

## Key Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest --verbose

# Run a specific test file
pytest tests/test_technical_indicators.py --verbose

# Start dev server
python -m uvicorn dashboard.backend.main:app --host 127.0.0.1 --port 8000 --reload

# Run the full daily after-market pipeline (download 700+ tickers → features → predict → audit → cache → Telegram)
python -c "from src.scheduler.daily_scheduler import run_daily_after_market_job; run_daily_after_market_job()"

# Run a specific scheduler phase (pre-market / midday / BSJP / after-market)
python -c "from src.scheduler.daily_scheduler import run_morning_premarket_job; run_morning_premarket_job()"

# Retrain the XGBoost model on real 5-year data
python scripts/train_real_embedding_model.py

# Run with Docker
docker-compose up --build
```

No formatter, linter, or type checker is configured in this repo.

## Architecture

### Import Convention

Every module resolves the project root relative to its own file and appends it to `sys.path`:

```python
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.config import ...
```

Always use project-root-relative imports. The `.env` file lives at `PROJECT_ROOT / ".env"` and is loaded via `python-dotenv` in `src/config.py`.

### Code Layout

```
stock-analysis/
├── dashboard/backend/
│   ├── main.py                         # FastAPI entrypoint — mounts static frontend, 7 API routers, starts background threads
│   └── routes/
│       ├── predict.py                  # GET /api/recommendations (cache or fresh), GET /api/sync
│       ├── chart.py                    # OHLCV chart data for TradingView Lightweight Charts
│       ├── audit.py                    # Signal track record DB, quant backtest engine, save/sync/audit APIs
│       ├── narasi.py                   # AI narrative generation (Indonesian language analysis)
│       ├── news_agent.py               # News aggregation & sentiment analysis
│       ├── sentiment_filter.py         # Asymmetric risk keyword filter (veto negative news, boost positive)
│       ├── features.py                 # Shared helpers: derive_signals(), generate_reason()
│       └── telegram.py                 # GET /api/telegram-status — bot health check endpoint
├── dashboard/frontend/                 # Vanilla HTML/CSS/JS — glassmorphism UI, TradingView charts
│
├── src/
│   ├── agents/
│   │   └── multi_agent_system.py       # 4-agent trading framework: Technical, Sentiment, Bull-Bear Debate, Risk Manager + optional LLM synthesis
│   ├── config.py                       # Paths, trading params (TP +3%/SL -1.5%, batch 50, 2s delay), env loading
│   ├── collector/
│   │   ├── batch_collector.py          # yfinance batch downloader (50 stocks/chunk, 2s delay)
│   │   └── openbb_provider.py          # OpenBB data provider with graceful yfinance fallback
│   ├── database/market_db.py           # SQLite daily_prices table (ticker, date, OHLCV)
│   ├── features/
│   │   ├── technical_indicators.py     # RSI, MACD, BB, ATR, VWAP, OBV, SMA, ROC — all indicators
│   │   ├── embedding.py                # Dense chart feature embeddings (volatility, momentum, curve shape, return velocity)
│   │   └── build_features.py           # Pipeline to combine indicators + embeddings
│   ├── notifications/telegram_bot.py   # 4-phase broadcaster + interactive command listener (/today, /audit, etc.)
│   └── scheduler/daily_scheduler.py    # 4-phase background thread scheduler + individual job entrypoints
│
├── models/
│   ├── best_xgboost_optuna.pkl         # Trained XGBoost classifier
│   └── standard_scaler.pkl             # Fitted StandardScaler with feature_names_in_
│
├── data/
│   ├── stock_market.db                 # Daily OHLCV for 700+ tickers
│   ├── signals_audit.db                # Trading signal audit track record
│   ├── latest_recommendations.json     # Pre-computed JSON cache (sub-5ms UI load)
│   └── tickers.txt                     # 700+ BEI ticker symbols
│
├── tests/
│   ├── conftest.py                     # Sets TESTING=true to disable background threads
│   ├── test_technical_indicators.py    # RSI, MACD, BB calculation tests
│   ├── test_feature_embeddings.py      # Embedding extraction tests
│   ├── test_asymmetric_sentiment.py    # Sentiment filter logic tests
│   ├── test_backend_api.py             # FastAPI endpoint integration tests
│   └── test_openbb_and_agents.py       # OpenBB provider & multi-agent system tests
│
├── scripts/
│   ├── train_embedding_model.py        # Training pipeline
│   ├── train_real_embedding_model.py   # Training on real 5-year historical data
│   ├── clean_ticker_universe.py        # Prunes suspended & delisted tickers from tickers.txt
│   └── update_notebooks.py             # Jupyter notebook helper utilities
│
└── dags/stock_pipeline_dag.py          # Airflow DAG (placeholder, all commented out)
```

### 4-Phase Daily Scheduler

| Phase | Time (WIB) | Function | Action |
|-------|-------------|----------|--------|
| ☀️ Morning Radar | 08:30 | `run_morning_premarket_job()` | Reads cached recommendations from JSON, broadcasts top picks to Telegram 30 min before open |
| ☕ Midday Recap | 12:00 | `run_midday_recap_job()` | Real-time Sesi 1 audit, sends midday progress update |
| 🌇 BSJP Radar | 15:30 | `run_bsjp_radar_job()` | Downloads fresh data, scans for late-session momentum (Beli Sore Jual Pagi) |
| 📊 After-Market | 16:05 | `run_daily_after_market_job()` | Full pipeline: download → indicators → embeddings → predict → audit → cache → Telegram broadcast |

The background scheduler (`start_background_scheduler()`) runs in a daemon thread, checking time every 30s. In GitHub Actions, the 4 phases run independently via cron-triggered workflows.

### Pipeline Flow (After-Market Job)

1. **Download** 700+ tickers in 50-stock batches via yfinance (2s delay between batches)
2. **Store** OHLCV in `data/stock_market.db`
3. **Compute** 20+ technical indicators (RSI, MACD, BB, ATR, VWAP, OBV, SMA, ROC) via `add_technical_indicators()`
4. **Generate** return features (1d/2d/3d/5d returns) and IHSG market regime context
5. **Extract** dense chart feature embeddings (volatility, momentum, curve shape, return velocity) via `extract_chart_feature_embeddings()`
6. **Predict** with XGBoost classifier (≥70% confidence threshold)
7. **Derive signals** (target price = max(close × 1.03, close + 1.5×ATR), stop loss = close × 0.985)
8. **Audit** existing signals (check WIN/LOSS against real market prices)
9. **Apply** asymmetric sentiment filter (veto stocks with negative news, boost probability for positive catalysts)
10. **Optionally enhance** with Multi-Agent System (`src/agents/multi_agent_system.py`) — 4 agents (Technical, Sentiment, Bull-Bear Debate, Risk Manager) generate consensus narrative with optional LLM synthesis
11. **Save** top 10 recommendations to `data/latest_recommendations.json` + `data/signals_audit.db`
12. **Broadcast** to Telegram

### Multi-Agent System

The `src/agents/multi_agent_system.py` implements a 4-agent trading consensus framework (inspired by TauricResearch/TradingAgents):

| Agent | Role |
|-------|------|
| **TechnicalAnalystAgent** | Analyzes RSI, MACD, trend direction, upside potential to target price |
| **SentimentAnalystAgent** | Evaluates market sentiment status and catalyst impact |
| **BullBearDebateAgent** | Simulates bull (upside) vs bear (risk) debate with ticker-specific arguments |
| **RiskManagerAgent** | Computes risk/reward ratio and outputs BUY or WAIT & SEE verdict |

The system can optionally enhance its consensus via LLM proxy (`_call_llm_synthesis`) for polished Indonesian-language synthesis — falls back to rule-based output if the LLM call fails.

### OpenBB Provider

`src/collector/openbb_provider.py` provides unified access to historical data and technical indicators:
- Tries the OpenBB Platform SDK first (`from openbb import obb`)
- Falls back gracefully to yfinance + pandas if OpenBB is not installed
- Used by the multi-agent system and can be swapped in as an alternative data source throughout the pipeline

### API Routes (all under `/api`)

| Endpoint | File | Description |
|----------|------|-------------|
| `GET /api/recommendations?force=true` | `predict.py` | Top 10 picks (default: JSON cache, `?force=true`: fresh scan) |
| `GET /api/sync` | `predict.py` | Force full data download + re-scan |
| `GET /api/chart/{ticker}` | `chart.py` | OHLCV + indicator chart data |
| `GET /api/news/{ticker}` | `news_agent.py` | News + sentiment for a ticker |
| `GET /api/track-record` | `audit.py` | 6-month accumulative performance audit |
| `GET /api/audit-summary` | `audit.py` | Today's audit breakdown |
| `GET /api/save-signals` | `audit.py` | Save today's signals to audit DB |
| `POST /api/save-signals` | `audit.py` | Bulk insert signals |
| `GET /api/narasi` | `narasi.py` | AI narrative via LLM proxy |
| `GET /api/sentiment/{ticker}` | `sentiment_filter.py` | Asymmetric news sentiment (VETO/BOOST/NETRAL) |
| `POST /api/sentiment/batch` | `sentiment_filter.py` | Batch sentiment evaluation |
| `GET /api/telegram-status` | `telegram.py` | Telegram bot health check |

## Testing

- **4 test files** in `tests/` (12 tests total, all pass).
- `tests/conftest.py` sets `os.environ["TESTING"] = "true"` globally.
- The `TESTING` env var is checked in `main.py:startup_event()` and `daily_scheduler.py:start_background_scheduler()` — when set, background scheduler and Telegram listener threads are skipped.
- API tests use `httpx` TestClient against the FastAPI app.
- CI (`.github/workflows/ci.yml`) runs on `master` and `developments` branches with Python 3.10.
- No mocks for yfinance; tests use synthetic/static data.

## Configuration

- **`.env`** (required): `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `OPENAI_API_BASE`, `OPENAI_API_KEY`
- **`src/config.py`**: Loads `.env`, defines paths, trading parameters (PROFIT_THRESHOLD=3%, BATCH_SIZE=50, BATCH_DELAY=2s), reads ticker list
- Trading parameters: Target Profit = +3.0%, Stop Loss = -1.5%, ATR-based dynamic TP scaling
- AI narrative uses OpenCode/DeepSeek via local proxy at `OPENAI_API_BASE`

## CI/CD Quirks

- `.github/workflows/daily_scan.yml` force-adds gitignored artifacts (`git add -f data/signals_audit.db data/latest_recommendations.json`) and auto-commits with `[skip ci]`
- `.gitignore` excludes `*.db`, `*.json`, `*.pkl`, `*.joblib` — these are generated/CI artifacts
- Docker: `python:3.11-slim` base, `docker-compose.yml` maps port 8000, mounts `.` as volume, reads `.env`

## Key Trading Engine Concepts

- **IHSG Market Regime Guard**: Blocks buy signals when IHSG (^JKSE) is below its SMA20 — prevents catching downtrends
- **70% Confidence Cut-Off**: Only processes signals with XGBoost probability ≥ 70%
- **Asymmetric Risk Filter**: VETO rule for negative news, probability boost for positive catalysts
- **Dynamic TP/SL**: Target price = max(close × 1.03, close + 1.5 × ATR); stop loss = close × 0.985
- **Pre-computed JSON Cache**: `data/latest_recommendations.json` enables sub-5ms dashboard load
- **Dual SQLite DBs**: `stock_market.db` (daily OHLCV prices) + `signals_audit.db` (signal track record with WIN/LOSS/PENDING status)

## Design System

The frontend uses a warm neutral design system documented in `DESIGN.md`:
- **Palette**: Charcoal Black (#1C1C1C), Cream Surface (#F2F0EC), Light Cream (#F7F5F2), Border Gray (#E8E5E0)
- **Typography**: Epilogue (sans-serif body), Fraunces (serif headings)
- **Components**: Glassmorphism cards, pill buttons (100px border-radius), 4px base spacing unit
- **Charts**: TradingView Lightweight Charts library
- **Responsive**: 1200px max-width container, 3-column → 2-column → 1-column card layout
