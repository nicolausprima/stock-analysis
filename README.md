# StockAI — AI-Powered Day Trading Screener (Indonesia Market) 🇮🇩

> **Disclaimer:** This project is built for **educational purposes only**. It does not constitute financial or professional investment advice. Always conduct your own research before making any trading decisions.

---

## 🚧 Current Status
**V3 (Enterprise Architecture: Chart Embeddings + XGBoost + 300+ BEI Universe + Auto-Audit Track Record)**

This project analyzes stocks using a combination of price action, technical indicators, **Chart Feature Embeddings** via XGBoost ML, real-time AI news sentiment filtering, and an automated **Win/Loss Track Record Audit Engine**.

---

## 📊 Demo

This web application analyzes **300+ liquid stocks** from the Indonesia Stock Exchange (IDX / BEI) every day. It uses an upgraded **XGBoost** model trained on 5 years of historical BEI price data (2020–2026) using **Feature Embeddings** to recommend the **Top 10** stocks with the strongest buy signals (+3.0% Target Profit / -1.5% Stop Loss), augmented with real-time AI news sentiment filtering and automated audit tracking.

![StockAI Dashboard](dashboard/dashboard.png)

---

## ✨ Features

| Feature | Description |
|---|---|
| 🤖 **Feature Embedding + XGBoost Model** | Replaces static One-Hot ticker encoding with dense feature embeddings (volatility, momentum, curve shape, return velocity). Generalizes to 300+ BEI stocks without needing retraining for new ticker names. |
| 📊 **300+ BEI Ticker Universe** | Scans over 300 active, liquid stocks from LQ45, Kompas100, ISSI, and IDX80. |
| 🎯 **Target Profit +3.0%** | Precise day trading risk management (+3.0% Take Profit / -1.5% Stop Loss). |
| 📜 **Automated Win/Loss Track Record Audit** | Tracks signal performance in SQLite (`signals_audit.db`) and audits daily high prices automatically (`WIN` / `LOSS` / `PENDING`). |
| ⚡ **Sub-5ms UI Response & JSON Cache** | Runs a background scheduler at **16:05 WIB** after market close to pre-compute recommendations for instant dashboard loads (< 5ms). |
| 🛡️ **Rate-Limit Safe Batch Downloader** | Fetches market data in 50-ticker chunks with 2-second sleep delays to prevent Yahoo Finance IP bans (100% free data pipeline). |
| 🛡️ **Asymmetric AI Sentiment Filter** | Applies strict VETO (downgrade high-risk negative news) and BOOSTER (+4% probability boost for positive catalysts) rules. |
| 📰 **Unified AI Narrative Layer** | Generates detailed Indonesian analysis narratives summarizing technical & news catalysts. |
| 📈 **20+ Indicators & Interactive Charts** | Calculates RSI, MACD, BB, OBV, ATR, VWAP, SMA, and renders TradingView Lightweight Charts. |
| 🎨 **Liquid Glass UI** | Modern frosted glassmorphism design with smooth micro-animations. |

---

## ⚙️ How It Works

```text
1. 16:05 WIB Scheduler → 2. Rate-Limit Safe Batch Download → 3. SQLite Storage → 4. Feature Embeddings → 5. XGBoost Inference → 6. Asymmetric Risk Filter → 7. Instant JSON Cache (< 5ms)
```

1. **Automated 16:05 WIB Scheduler:** Runs after BEI market close to process daily price data.
2. **Batch Downloader:** Fetches 300+ tickers in 50-stock chunks with 2-second sleep delays.
3. **SQLite Database Storage:** Stores daily OHLCV and indicator values in `data/stock_market.db`.
4. **Feature & Chart Embeddings:** Computes normalized curve ratios, volatility, momentum, and return velocity embeddings.
5. **XGBoost Inference:** Scores buy probabilities (calibrated between 55% - 81% based on 5 years of historical BEI training).
6. **Asymmetric Risk Filter:** Applies VETO rules for high-risk news and probability boosts for positive catalysts.
7. **Instant JSON Cache:** Saves final Top 10 recommendations to `data/latest_recommendations.json` for sub-5ms dashboard loading.

---

## 🛠️ Tech Stack

- **Backend:** Python · FastAPI · SQLite · yfinance · XGBoost · scikit-learn · pandas
- **AI Narrative / Sentiment:** OpenCode (9router local proxy) · DeepSeek-v4
- **Frontend:** Vanilla HTML/CSS/JS · TradingView Lightweight Charts
- **Storage & Caching:** SQLite (`stock_market.db` & `signals_audit.db`) · JSON Cache
- **Containerization:** Docker · Docker Compose

---

## 🚀 Setup & Execution Guide

### Prerequisites
- Python 3.10+ or [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [OpenCode / 9router](https://opencode.ai/) running locally on `127.0.0.1:20128`

### Quick Start (Local Python)

**Step 1: Install Dependencies**
```bash
pip install -r requirements.txt
```

**Step 2: Train Model & Generate Initial Cache**
```bash
python scripts/train_real_embedding_model.py
python -c "from src.scheduler.daily_scheduler import run_daily_after_market_job; run_daily_after_market_job()"
```

**Step 3: Launch FastAPI Backend Server**
```bash
python -m uvicorn dashboard.backend.main:app --host 127.0.0.1 --port 8000
```

**Step 4: Open Dashboard**
Navigate to `http://127.0.0.1:8000` in your web browser.

---

## 📁 Project Structure

```text
stock-analysis/
├── dashboard/
│   ├── backend/
│   │   ├── main.py                    # FastAPI application & startup event
│   │   └── routes/                    # Modular API endpoints (predict, chart, narasi, audit)
│   └── frontend/
│       ├── index.html                 # Liquid Glass UI layout
│       ├── css/style.css              # Design system & tokens
│       └── js/app.js                  # Frontend logic & chart integration
├── data/
│   ├── tickers.txt                    # List of 300+ BEI stock tickers
│   ├── stock_market.db                # SQLite database for daily OHLCV prices
│   ├── signals_audit.db               # SQLite database for Win/Loss audit tracking
│   └── latest_recommendations.json    # JSON cache for sub-5ms UI responses
├── notebooks/
│   ├── 01_EDA.ipynb                   # Exploratory Data Analysis
│   ├── 02_Preprocessing.ipynb         # Feature Embeddings & Target definition (+3.0%)
│   └── 03_Modelling.ipynb             # XGBoost model training & evaluation
├── scripts/
│   ├── train_real_embedding_model.py # Training script on 5-year BEI dataset
│   └── update_notebooks.py           # Programmatic notebook update tool
├── src/
│   ├── collector/batch_collector.py  # Rate-limit safe multi-ticker downloader
│   ├── database/market_db.py         # SQLite market data manager
│   ├── features/embedding.py         # Feature & Chart Pattern Embedding layer
│   ├── scheduler/daily_scheduler.py   # 16:05 WIB after-market routine
│   └── config.py                     # Configuration & parameters
├── models/                           # Saved XGBoost & Scaler models (*.pkl)
├── Dockerfile                         # Backend container definition
├── docker-compose.yml                 # Container orchestration
└── requirements.txt                   # Python dependencies
```

---

## 📝 License

Distributed under the MIT License. See `LICENSE` for more information.
