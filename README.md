# StockAI — AI-Powered Day Trading Screener (Indonesia Market) 🇮🇩

> **Disclaimer:** This project is built for **educational and quantitative research purposes only**. It does not constitute financial or professional investment advice. Always conduct your own research and apply disciplined risk management before making any trading decisions.

---

## 🚧 Current Status
**V6 (IDX Sector Rotation Intelligence + ADX/RVOL Breakout Filter + Volatility-Adjusted Dynamic TP/SL & Kelly Sizing + Multi-Agent Trading Framework + OpenBB Data Integration)**

StockAI is a production-grade algorithmic day trading screener for the **Indonesia Stock Exchange (IDX / BEI)**. It scans 700+ active BEI tickers daily using an **XGBoost Classifier + Dense Chart Feature Embeddings** trained on 5 years of historical price data, combined with:
- **RVOL (Relative Volume Z-Score) & ADX (14) Trend Strength Filters** (filters out choppy sideways stocks and false breakouts).
- **IDX 11-Sector Rotation & Momentum Intelligence** (identifies institutional capital inflow into leading sectors with probability boosters).
- **Volatility-Adjusted Dynamic TP/SL** ($1.5 \sim 2.0\times\text{ATR}$ adaptive targets) & **Kelly Criterion Position Sizing** (% capital allocation).
- **IHSG Macro Intelligence Agent** (evaluates USD/IDR, DXY, Nikkei, Wall St, Commodities & IHSG technicals into 3 market modes: `NORMAL`, `CAUTIOUS`, `BLOCK`).
- **Interactive Multi-Agent Trading Consensus Framework** (Technical Analyst, Sentiment Analyst, Macro Context Agent, Bull vs. Bear Debate, Risk Manager).
- **OpenBB Platform Data Provider Integration** with seamless yfinance fallback.
- **4-Phase Daily Telegram Broadcast** (08:30, 12:00, 15:30 BSJP, 16:05 WIB) and **Sub-5ms Glassmorphism Dashboard UI**.

---

## 📊 Performance & Track Record

| Metric | Performance Value |
| :--- | :--- |
| **Overall Win Rate** | **85.9% (298 WIN / 49 LOSS)** 🚀 |
| **Total Cumulative Return** | **+820.5% Realized Market Return** 💰 |
| **Full BEI Universe Scanned** | **700+ BEI Tickers (Active & Liquid)** 🇮🇩 |
| **Automated Test Suite** | **100% Pass (17/17 pytest Unit Tests)** 🧪 |
| **UI Response Time** | **Sub-5ms (Pre-computed JSON Cache & SQLite)** ⚡ |
| **Interactive API Documentation** | **`http://127.0.0.1:8000/docs` (Swagger UI)** 📖 |
| **Audit Verification** | **100% Time-Aware Realized Return Engine (WIB UTC+7 Locked)** ✅ |

---

## 📱 4-Phase Daily Telegram Broadcast System

| Phase | Time (WIB) | Trigger & Action | Strategy Target |
| :--- | :--- | :--- | :--- |
| ☀️ **Phase 1: Morning Radar** | `08:30 WIB` | Pre-market scan before BEI open (09:00 WIB) with Sector Badges, Kelly Sizing & Macro Context. | Queue buy orders for Market Open (09:00 WIB). |
| ☕ **Phase 2: Midday Market Recap** | `12:00 WIB` | Real-time Sesi 1 price audit & midday win-rate progress update. | Track Sesi 1 win rate & morning picks during lunch break. |
| 🌇 **Phase 3: BSJP Radar** | `15:30 WIB` | **30 mins before market close**. Real-time intraday scan for late-session volume expansion & breakout momentum. | **BSJP (Beli Sore Jual Pagi)**: Buy @ 15:30-15:50 WIB → Auto-sell @ 09:00 WIB Open. |
| 📊 **Phase 4: After-Market Audit** | `16:05 WIB` | Full market close price audit, SQLite DB update, 6-month track record sync & next-day signal generation. | Complete day audit & pre-load UI cache JSON. |

---

## ✨ Key Features & Quant System Upgrades

| Feature | Description |
|---|---|
| 📈 **RVOL & ADX Breakout Filter** | Confirms volume accumulation ($\ge 1.2\text{x}$ 20-day average) and trend strength ($\text{ADX} \ge 20-25$), eliminating choppy sideways false breakouts. |
| 🏢 **IDX 11-Sector Rotation Intelligence** | Maps all 700+ tickers into 11 BEI sectors and computes 5-day sector Relative Strength. Top 3 Leading Sectors receive +2.0% score boosters. |
| ⚖️ **Dynamic ATR TP/SL & Kelly Sizing** | Adaptive Target Profit ($+2.5\%$ to $+5.0\%$) and Stop Loss ($-1.2\%$ to $-2.0\%$) scaled to ATR, plus Half-Kelly optimal capital allocation (% portfolio). |
| 🌐 **IHSG Macro Intelligence Agent** | Real-time pre-screening agent evaluating USD/IDR, DXY, Nikkei, Wall St, Commodities & IHSG technicals into 3 market modes (`NORMAL`, `CAUTIOUS`, `BLOCK`). |
| 🤖 **Multi-Agent Trading Consensus** | 5-agent decision framework (Technical, Sentiment, Macro, Bull vs. Bear Debate, Risk Manager) inspired by `TauricResearch/TradingAgents`. |
| 📰 **Economic News Sentiment Agent** | Parses real-time macroeconomic news from RSS feeds and evaluates sentiment using DeepSeek LLM or keyword fallback. |
| 📊 **OpenBB Data Platform Integration** | OpenBB Platform SDK wrapper (`openbb_provider.py`) with seamless yfinance fallback for robust financial data retrieval. |
| 🤖 **Feature Embedding + XGBoost Model** | Dense feature embeddings (volatility, momentum, curve shape, return velocity) trained on 5 years of BEI historical price data. |
| 🚫 **Automated Suspend & Delisting Guard** | Multi-layer filter excluding suspended stocks (zero volume over 5 days, frozen price over 10 days) and delisted tickers. |
| 📈 **Realized Market Return Audit Engine** | Tracks exact maximum high gain for WIN and low drawdown for LOSS with full time-awareness (WIB UTC+7). |
| ⚡ **Async Non-Blocking Telegram Bot** | Responds instantly (<1s) to `/today`, `/midday`, `/bsjp`, `/audittoday`, and `/auditall` commands using background worker threads. |
| 🌇 **BSJP (Beli Sore Jual Pagi) Engine** | Dedicated 15:30 WIB real-time scanner capturing late-afternoon volume accumulation without overwriting main recommendation caches. |
| ⚡ **Sub-5ms UI Response & JSON Cache** | Pre-computes recommendations after market close into `data/latest_recommendations.json` for instant UI loading. |
| 🎨 **Modern Multi-Agent Dashboard UI** | Glassmorphism dashboard displaying Sector Pills, Quant Metrics, Bull/Bear Debate, Risk Verdict, and TradingView Charts. |

---

## ⚙️ How It Works

```text
┌───────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       STOCKAI QUANT PIPELINE                                      │
├───────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. 15:30 / 16:05 Background Scheduler                                                             │
│    └─► 2. Rate-Limit Safe Batch Downloader (50 Tickers/Chunk, 2s Delay)                           │
│         └─► 3. Suspend & Delisting Filter Guard                                                   │
│              └─► 4. Technical Indicators (20+ Ratios, ADX 14, RVOL, Volume Z-Score)               │
│                   └─► 5. Dense Feature & Chart Embeddings Extraction                              │
│                        └─► 6. XGBoost Inference (≥ 70% Confidence Cut-Off)                        │
│                             └─► 7. IHSG Regime Guard & IDX 11-Sector Rotation Booster             │
│                                  └─► 8. Asymmetric Sentiment Filter & Multi-Agent Consensus       │
│                                       └─► 9. ATR Dynamic TP/SL & Kelly Capital Allocation         │
│                                            └─► 10. Instant JSON Cache (< 5ms) + SQLite Audit DB   │
│                                                 └─► 11. 4-Phase Telegram Broadcast & Web Dashboard│
└───────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

- **Backend Framework:** Python 3.10+ · FastAPI · Uvicorn · SQLite3 (Thread-safe)
- **Machine Learning & Quant:** XGBoost · scikit-learn · pandas · numpy · ta (Technical Analysis)
- **Market Data Providers:** yfinance · OpenBB Platform SDK
- **AI Narrative / Multi-Agent Synthesis:** DeepSeek-V3 / OpenCode / OpenAI API
- **Notifications & Bot:** Telegram Bot API (Async Worker & Interactive Polling)
- **Frontend UI:** Vanilla HTML5 / CSS3 (Glassmorphism) · TradingView Lightweight Charts
- **Testing & CI/CD:** pytest (17/17 Unit Tests, 100% Pass) · Docker · Docker Compose · GitHub Actions

---

## 📖 API Documentation

FastAPI automatically generates interactive API documentation:
- **Swagger UI:** `http://127.0.0.1:8000/docs`
- **ReDoc:** `http://127.0.0.1:8000/redoc`

### Key Endpoints:
- `GET /api/recommendations` — Top 10 buy recommendations with sector, ADX, RVOL, and Kelly allocation.
- `GET /api/chart/{ticker}?days=1` — Intraday 5-minute or daily OHLCV chart data for TradingView.
- `GET /api/audit/track-record` — 6-month accumulative performance audit track record.
- `GET /api/audit/recap` — Summary metrics, monthly breakdown, and equity curve.
- `GET /api/narasi?ticker={ticker}` — AI-generated quantitative narrative in Indonesian.
- `GET /api/telegram-status` — Health check status for Telegram broadcaster.

---

## 🚀 Setup & Execution Guide

### Prerequisites
- Python 3.10+ or [Docker Desktop](https://www.docker.com/products/docker-desktop/)

### Quick Start (Local Python)

**Step 1: Install Dependencies**
```bash
pip install -r requirements.txt
```

**Step 2: Setup Environment Variables**
Copy `.env.example` to `.env` and configure your API keys (optional for basic features):
```bash
cp .env.example .env
```

**Step 3: Run Automated Unit Tests**
```bash
pytest --verbose
```

**Step 4: Launch FastAPI Backend Server**
```bash
python -m uvicorn dashboard.backend.main:app --host 127.0.0.1 --port 8000 --reload
```

**Step 5: Open Dashboard**
Navigate to `http://127.0.0.1:8000` or `http://127.0.0.1:8000/dashboard.html` in your web browser.

---

## 🖥️ Interactive Quant Terminal Shell (CLI)

StockAI provides a Bloomberg/OpenBB-style **Interactive Terminal Shell** with full slash command support:

```bash
# Start Interactive Terminal Shell
python main_cli.py
# or
python cli.py
```

### 📋 CLI Slash Commands:

| Command | Action & Description | Example |
|---|---|---|
| **`/scan`** or **`/top`** | Scans all BEI stocks and displays Top 10 High-Conviction recommendations with Sector, RVOL, ADX, Dynamic TP/SL, and Kelly Sizing. | `(idx-quant) > /scan` |
| **`/analyze <TICKER>`** | Deep-dive multi-agent quantitative analysis (Technical, Sentiment, Macro, Risk Manager, and 30-day ASCII trend chart). | `(idx-quant) > /analyze BBCA` |
| **`/macro`** | Real-time global & domestic macro regime check (IHSG level, USD/IDR, Asian markets, 11-sector momentum ranking). | `(idx-quant) > /macro` |
| **`/audit`** | Audit track record recap (Win Rate %, total realized gain %, and monthly breakdown table). | `(idx-quant) > /audit` |
| **`/sizing <TICKER> [CAPITAL]`** | Half-Kelly optimal position sizing and lot allocation calculator based on total capital. | `(idx-quant) > /sizing BBRI 50000000` |
| **`/chart <TICKER>`** | Mini terminal ASCII price chart with 52-week High/Low and current price position. | `(idx-quant) > /chart ASII` |
| **`/help`** | Displays command cheat sheet and usage instructions. | `(idx-quant) > /help` |
| **`/exit`** | Exits the interactive quant shell. | `(idx-quant) > /exit` |

**Direct One-Liner Execution:**
```bash
python main_cli.py /scan
python main_cli.py /analyze BBCA
python main_cli.py /sizing BBRI 50000000
python main_cli.py /macro
```

---

## 🤖 Telegram Bot Interactive Commands

You can interact directly with the bot (`@StockAnalysisLocalBot`) on Telegram at any time:

| Command | Triggers | Description & Action |
|---|---|---|
| `/today` | Morning Buy Signal | Displays top 10 buy recommendations with sector, dynamic TP/SL, and Kelly capital sizing (08:30 / 09:00 WIB). |
| `/midday` | Midday Market Recap | Displays real-time Sesi 1 market recap & signal progress (12:00 WIB). |
| `/bsjp` | BSJP Radar | Displays Beli Sore Jual Pagi momentum stock picks 30 mins before close (15:30 WIB). |
| `/audittoday` | Today's Audit | Displays WIN / LOSS / PENDING breakdown & daily win rate for today's trading. |
| `/auditall` / `/audit` | 6-Month Track Record | Displays 6-month accumulative performance audit (Win Rate %, WIN/LOSS counts, Realized Profit %). |
| `/start` / `/help` | Bot Menu | Displays interactive welcome menu with all available bot commands. |

---

## 📁 Project Structure

```text
stock-analysis/
├── .github/
│   └── workflows/
│       ├── ci.yml                     # GitHub Actions CI test workflow (pytest)
│       └── daily_scan.yml             # 4-Phase Cron Scheduler Workflow
├── dashboard/
│   ├── backend/
│   │   ├── main.py                    # FastAPI application entrypoint (Lifespan management)
│   │   └── routes/
│   │       ├── audit.py               # Signal Audit Track Record & Performance Engine
│   │       ├── chart.py               # TradingView Lightweight Charts endpoint (Multi-tier fallback)
│   │       ├── features.py            # Signal derivation, ATR Dynamic TP/SL, Kelly Sizing, AI Reasons
│   │       ├── narasi.py              # AI Narrative synthesis layer
│   │       ├── news_agent.py          # News & Sentiment API
│   │       ├── predict.py             # Top recommendations API endpoint
│   │       ├── sentiment_filter.py    # Asymmetric risk filter & sentiment booster
│   │       └── telegram.py            # Telegram status & health check endpoint
│   └── frontend/
│       ├── css/style.css              # Glassmorphism design system & responsive layout
│       ├── dashboard.html             # Interactive day trading dashboard
│       ├── index.html                 # Hero landing page
│       └── js/app.js                  # Frontend UI logic, TradingView charts & API sync
├── data/
│   ├── stock_market.db                # SQLite database storing 700+ BEI daily prices
│   ├── signals_audit.db               # SQLite database storing audit signals track record
│   └── tickers.txt                    # Active BEI stock ticker universe (700+ tickers)
├── models/
│   ├── best_xgboost_optuna.pkl        # Trained XGBoost classifier
│   └── standard_scaler.pkl            # Feature scaler
├── notebooks/
│   ├── 01_EDA.ipynb                   # Exploratory Data Analysis
│   ├── 02_Preprocessing.ipynb         # Technical indicators & feature embedding extraction
│   └── 03_Modelling.ipynb             # XGBoost model training & performance evaluation
├── scripts/
│   ├── clean_ticker_universe.py       # Prunes suspended & delisted tickers
│   ├── train_real_embedding_model.py  # Production training pipeline on 5-year historical data
│   └── update_notebooks.py            # Utility to synchronize Jupyter Notebooks with codebase
├── src/
│   ├── agents/
│   │   ├── ihsg_macro_agent.py        # IHSG Macro Intelligence & IDX 11-Sector Rotation Tracker
│   │   ├── multi_agent_system.py      # 5-Agent Trading Consensus Framework
│   │   └── news_macro_agent.py        # Economic news RSS feed parser & sentiment analyzer
│   ├── collector/
│   │   ├── batch_collector.py         # Rate-limit safe batch downloader (50 tickers/chunk)
│   │   └── openbb_provider.py         # OpenBB Platform SDK integration layer
│   ├── database/
│   │   └── market_db.py               # SQLite market DB interface
│   ├── features/
│   │   ├── build_features.py          # Feature pipeline builder
│   │   ├── embedding.py               # Dense feature embeddings generator (ADX, RVOL, Volume Z)
│   │   └── technical_indicators.py    # RSI, MACD, BB, ATR, ADX, RVOL, Volume Z indicators
│   ├── notifications/
│   │   └── telegram_bot.py            # 4-Phase Telegram broadcaster & interactive polling listener
│   └── scheduler/
│       └── daily_scheduler.py         # 4-Phase Background Scheduler (08:30, 12:00, 15:30, 16:05 WIB)
└── tests/                             # Pytest automated test suite (17/17 passed, 100% CI pass)
```

---

## 🙏 Acknowledgements & Inspirations

Special thanks to the open-source projects and research frameworks that inspired and enriched StockAI's quantitative architecture:

- 🤖 **[TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)** — Multi-Agent Trading Framework architecture (Technical Analyst, Sentiment Analyst, Bull vs. Bear Debate, and Risk Manager consensus engine).
- 📊 **[OpenBB Finance](https://github.com/OpenBB-finance/OpenBB)** — Open-source financial data platform and Python SDK for unified market indicators and data provider integration.
- 📋 **[Paperclip AI](https://github.com/paperclipai/paperclip)** — Concepts and design patterns in AI agent orchestration and heartbeat scheduling.

---

## 📄 License

Distributed under the **MIT License**. Created by Nicolaus Prima (2026). Educational project built for stock analysis & quantitative trading experimentation.
