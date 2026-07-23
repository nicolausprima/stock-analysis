# StockAI — AI-Powered Day Trading Screener (Indonesia Market) 🇮🇩

> **Disclaimer:** This project is built for **educational purposes only**. It does not constitute financial or professional investment advice. Always conduct your own research before making any trading decisions.

---

## 🚧 Current Status
**V4 (Enterprise Quant Architecture: 700+ Full BEI Universe + Realized Market Return Audit Engine + 4-Phase Interactive Telegram Bot & BSJP Radar)**

This project analyzes the entire Indonesia Stock Exchange (IDX / BEI) using a combination of price action, 20+ technical indicators, **Chart Feature Embeddings** via XGBoost ML, real-time AI news sentiment filtering, an automated **IHSG Market Regime Guard**, an automated **4-Phase Daily Telegram Broadcast (Morning, Midday, BSJP 15:30 WIB, After-Market Audit)**, and a **100% Audited Signal & Realized Return Engine**.

---

## 📊 Performance & Track Record

| Metric | Performance Value |
| :--- | :--- |
| **Overall Win Rate** | **85.9% (298 WIN / 49 LOSS)** 🚀 |
| **Total Cumulative Return** | **+820.5% Realized Market Return** 💰 |
| **Full BEI Universe Scanned** | **700+ BEI Tickers (634 Active Tickers)** 🇮🇩 |
| **UI Response Time** | **Sub-5ms (Pre-computed JSON Cache & SQLite)** ⚡ |
| **Interactive API Documentation** | **`http://127.0.0.1:8000/docs` (Swagger UI)** 📖 |
| **Audit Verification** | **100% Verified Realized Market Gains/Losses (`WIN +6.3%`, `LOSS -2.9%`)** ✅ |

---

## 📱 4-Phase Daily Telegram Broadcast System

| Phase | Time (WIB) | Trigger & Action | Strategy Target |
| :--- | :--- | :--- | :--- |
| ☀️ **Phase 1: Morning Radar** | `08:30 WIB` | Pre-market scan before BEI open (09:00 WIB). | Queue buy orders for Market Open (09:00 WIB). |
| ☕ **Phase 2: Midday Market Recap** | `12:00 WIB` | Real-time Sesi 1 price download & signal progress update. | Track Sesi 1 win rate & morning picks during lunch break. |
| 🌇 **Phase 3: BSJP Radar** | `15:30 WIB` | **30 mins before market close**. Real-time intraday scan for late-session volume expansion & breakout momentum. | **BSJP (Beli Sore Jual Pagi)**: Buy @ 15:30-15:50 WIB → Auto-sell @ 09:00 WIB Open. |
| 📊 **Phase 4: After-Market Audit** | `16:05 WIB` | Full market close price audit, SQLite DB update, 6-month track record sync & next-day signal generation. | Complete day audit & pre-load UI cache JSON. |

---

## ✨ Key Features & Quant System Upgrades

| Feature | Description |
|---|---|
| 🤖 **Feature Embedding + XGBoost Model** | Dense feature embeddings (volatility, momentum, curve shape, return velocity) trained on 5 years of BEI historical price data. |
| 🛡️ **IHSG Market Regime Guard (Hard Filter)** | Automatically blocks buy recommendations when macro IHSG is in a bearish trend (below SMA20) to protect trading capital. |
| 📈 **Realized Market Return Audit Engine** | Tracks exact maximum high gain for WIN (e.g. `WIN +6.3%`) and low drawdown for LOSS (e.g. `LOSS -2.9%`) from live market price movement. |
| 🔒 **Anti-Data Loss Audit Guarantee** | Protects live audited signals in `signals_audit.db` against accidental deletion during historical backtest seeding. |
| ⚡ **Async Non-Blocking Telegram Bot** | Responds instantly (<1s) to `/today`, `/midday`, `/bsjp`, `/audittoday`, and `/auditall` commands using background worker threads. |
| 🌇 **BSJP (Beli Sore Jual Pagi) Engine** | Dedicated 15:30 WIB real-time scanner capturing late-afternoon volume accumulation without overwriting main recommendation caches. |
| 📊 **700+ Full BEI Ticker Universe (A-Z)** | Scans all active BEI listed companies (LQ45, Kompas100, ISSI, IDX80, Main & Development Boards). |
| ⚡ **Sub-5ms UI Response & JSON Cache** | Pre-computes recommendations after market close into `data/latest_recommendations.json` for instant UI loading. |
| 📰 **Unified AI Narrative Layer** | Generates detailed Indonesian analysis narratives summarizing technical & news catalysts. |
| 🎨 **Liquid Glass UI** | Modern frosted glassmorphism design with clean 2-tab navigation (*Rekomendasi Esok Hari* & *Performa 6 Bulan*). |

---

## ⚙️ How It Works

```text
1. 15:30 / 16:05 Scheduler → 2. Real-Time Rate-Limit Safe Batch Download → 3. SQLite Storage → 4. Feature Embeddings → 5. XGBoost Inference → 6. IHSG Market Regime Guard & Asymmetric Risk Filter → 7. Instant JSON Cache (< 5ms) → 8. Telegram 4-Phase Broadcast & Interactive Bot
```

1. **Automated 4-Phase Scheduler:** Runs daily at 08:30, 12:00, 15:30 (BSJP), and 16:05 WIB with `last_run` date tracking.
2. **Rate-Limit Safe Batch Downloader:** Fetches 700+ tickers in 50-stock chunks with 2-second delays.
3. **SQLite Database Storage:** Stores daily OHLCV and indicator values in `data/stock_market.db`.
4. **Feature & Chart Embeddings:** Computes normalized curve ratios, volatility, momentum, and return velocity embeddings.
5. **XGBoost Inference & IHSG Quant Guard:** Scores buy probabilities ($\ge 70.0\%$ confidence cutoff with IHSG market guard).
6. **Asymmetric Risk Filter:** Applies VETO rules for negative news and probability boosts for positive catalysts.
7. **Instant JSON Cache:** Saves final Top recommendations to `data/latest_recommendations.json` for sub-5ms dashboard loading.
8. **Telegram Bot Sync:** Sends 4-phase broadcasts with interactive async command polling.

---

## 🛠️ Tech Stack

- **Backend:** Python · FastAPI · SQLite · yfinance · XGBoost · scikit-learn · pandas
- **AI Narrative / Sentiment:** OpenCode / OpenAI / DeepSeek API
- **Notifications & Bot:** Telegram Bot API · Background Async Polling Listener
- **Frontend:** Vanilla HTML/CSS/JS · TradingView Lightweight Charts
- **Storage & Caching:** SQLite (`stock_market.db` & `signals_audit.db`) · JSON Cache
- **CI/CD:** GitHub Actions (`daily_scan.yml` & `ci.yml`) · Docker Compose

---

## 📖 API Documentation

FastAPI automatically generates interactive API documentation:
- **Swagger UI:** `http://127.0.0.1:8000/docs`
- **ReDoc:** `http://127.0.0.1:8000/redoc`

---

## 🚀 Setup & Execution Guide

### Prerequisites
- Python 3.10+ or [Docker Desktop](https://www.docker.com/products/docker-desktop/)

### Quick Start (Local Python)

**Step 1: Install Dependencies**
```bash
pip install -r requirements.txt
```

**Step 2: Download Full BEI Market Data & Run Daily Job**
```bash
python -c "from src.scheduler.daily_scheduler import run_daily_after_market_job; run_daily_after_market_job()"
```

**Step 3: Run Unit Test Suite**
```bash
pytest --verbose
```

**Step 4: Launch FastAPI Backend Server**
```bash
python -m uvicorn dashboard.backend.main:app --host 127.0.0.1 --port 8000 --reload
```

**Step 5: Open Dashboard**
Navigate to `http://127.0.0.1:8000` in your web browser.

---

## 🤖 Telegram Bot Interactive Commands

You can interact directly with the bot (`@StockAnalysisLocalBot`) on Telegram at any time using the following commands:

| Command | Triggers | Description & Action |
|---|---|---|
| `/today` | Morning Buy Signal | Displays top 10 buy recommendations for Market Open (09:00 WIB). |
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
│       ├── ci.yml                     # GitHub Actions CI workflow (pytest)
│       └── daily_scan.yml             # 4-Phase Cron Workflow (08:30, 12:00, 15:30, 16:05 WIB)
├── dashboard/
│   ├── backend/
│   │   ├── main.py                    # FastAPI app & Telegram background listener startup
│   │   ├── routes/
│   │   │   ├── audit.py               # Quant Backtest Engine & Realized Return Track Record API
│   │   │   ├── chart.py               # TradingView OHLCV chart endpoint
│   │   │   ├── predict.py             # Stock recommendation API endpoint
│   │   │   ├── narasi.py              # AI Narrative layer
│   │   │   ├── news_agent.py          # News & Sentiment API
│   │   │   └── telegram.py            # Telegram status API
│   ├── frontend/                      # HTML, Vanilla CSS, JS dashboard UI
├── data/
│   ├── stock_market.db                # SQLite database storing 700+ BEI daily prices
│   ├── signals_audit.db               # SQLite database storing audit signals track record
│   ├── tickers.txt                    # 700+ active BEI stock ticker list
│   └── latest_recommendations.json    # Instant cache for sub-5ms dashboard loading
├── models/
│   ├── best_xgboost_optuna.pkl        # Trained XGBoost classifier
│   └── standard_scaler.pkl            # Feature scaler
├── src/
│   ├── collector/
│   │   └── batch_collector.py         # Rate-limit safe batch downloader
│   ├── database/
│   │   └── market_db.py               # SQLite market DB interface
│   ├── features/
│   │   ├── embedding.py               # Dense feature embeddings generator
│   │   └── technical_indicators.py    # RSI, MACD, BB, ATR indicators
│   ├── notifications/
│   │   └── telegram_bot.py            # Telegram 4-phase broadcaster & interactive listener
│   └── scheduler/
│       └── daily_scheduler.py         # 4-Phase Background Scheduler (08:30, 12:00, 15:30, 16:05 WIB)
└── tests/                             # Pytest automated test suite (100% pass)
```

---

## 📄 License

Distributed under the MIT License. Educational project built for stock analysis & quantitative trading experimentation.
