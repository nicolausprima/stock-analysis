# StockAI — AI-Powered Day Trading Screener (Indonesia Market) 🇮🇩

> **Disclaimer:** This project is built for **educational purposes only**. It does not constitute financial or professional investment advice. Always conduct your own research before making any trading decisions.

---

## 🚧 Current Status
**V2 (Technical Analysis + AI News Sentiment)**
This project analyzes stocks using a combination of price action (RSI, MACD, Volume) via XGBoost ML, AND fundamental catalysts using generative AI (DeepSeek-v4 via OpenCode).

---

## 📊 Demo

This web application analyzes **99 selected stocks** from the Indonesia Stock Exchange (IDX / BEI) every day. It uses an **XGBoost** machine learning model trained on 20+ technical indicators to recommend the **Top 10** stocks with the strongest buy signals for day trading, augmented with real-time AI news sentiment.

![StockAI Dashboard](dashboard/dashboard.png)

---

## ✨ Features

| Feature | Description |
|---|---|
| 🤖 **XGBoost Model** | Trained on 5 years of historical data using Optuna for hyperparameter tuning. |
| 📰 **AI News Sentiment** | Uses generative AI (OpenCode DeepSeek) to fetch and summarize daily news catalysts instantly (Positive/Negative/Neutral). |
| 📈 **20+ Indicators** | Calculates RSI, MACD, Bollinger Bands, OBV, ATR, VWAP, SMA, and Bandarmologi (accumulation). |
| 📊 **Interactive Charts** | IHSG & individual stock charts (1D Intraday / 60D Historical) powered by TradingView Lightweight Charts. |
| 🔄 **Real-time Data** | Fetches the latest live market data from Yahoo Finance upon every scan. |
| 🎨 **Liquid Glass UI** | A modern, frosted glassmorphism design system with smooth micro-animations. |
| 🐳 **Docker Ready** | Single-command deployment utilizing Docker & Docker Compose. |

---

## ⚙️ How It Works

The core philosophy of this screener revolves around spotting short-term momentum and oversold bounces. 

```text
1. Data Pipeline → 2. Feature Engineering → 3. ML Scoring → 4. AI Catalyst Check → 5. Recommendation
```

1. **Data Pipeline:** When you click "Scan", the backend fetches the latest price data for 99 top Indonesian stocks via the `yfinance` API.
2. **Feature Engineering:** The raw price/volume data is mathematically transformed into 20+ technical indicators (e.g., measuring momentum via RSI, trend via MACD, volatility via ATR).
3. **ML Scoring:** The XGBoost model (previously trained on historical patterns) evaluates these current technical features and assigns a "Buy Probability" score from 0 to 100%.
4. **AI Catalyst Check:** For the selected top stocks, users can click a button to trigger an LLM (running locally via 9router) that fetches live news from Yahoo Finance and outputs a sentiment summary.
5. **Recommendation:** The system filters out the noise and presents the top 10 stocks with the highest probability of an intraday upward move, including predefined profit targets (+1.5%) and stop losses (-1.5%).

---

## ⚖️ Pros and Cons

### ✅ Pros (Strengths)
- **Emotionless Trading:** Removes human bias and FOMO by relying strictly on mathematical probabilities.
- **Fundamental + Technical:** Merges the power of quantitative ML with qualitative LLM news analysis.
- **Time-Saving:** Scans 99 stocks in seconds, a task that would take a human hours to do manually.
- **Dynamic Adaptability:** The inclusion of the overall IHSG trend helps the model avoid buying during severe market crashes.

### ❌ Cons (Limitations)
- **Intraday Noise:** Short-term market movements in the Indonesian market can be highly volatile and manipulated by market makers (Bandar).
- **Yahoo Finance Delay:** Depending on the API, there might be a slight delay in price action compared to direct broker feeds.

---

## 🛠️ Tech Stack

- **Backend:** Python · FastAPI · yfinance · XGBoost · scikit-learn · pandas
- **AI Agent:** OpenCode (9router local proxy) · DeepSeek-v4
- **Frontend:** Vanilla HTML/CSS/JS · TradingView Lightweight Charts
- **Pipeline / Orchestration:** Apache Airflow (Template Ready)
- **Containerization:** Docker · Docker Compose

---

## 🚀 Step-by-Step Setup Guide

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running.
- Git installed on your machine.
- [OpenCode / 9router](https://opencode.ai/) installed and running locally for AI features.

### Installation Steps

**Step 1: Clone the repository**
```bash
git clone https://github.com/yourusername/stock-analysis.git
cd stock-analysis
```

**Step 2: Provide the Trained Model**
Since ML model files (`*.pkl`) are often too large for GitHub, they are ignored by `.gitignore`. You must place your trained models inside the `models/` folder:
- `models/best_xgboost_optuna.pkl`
- `models/standard_scaler.pkl`
*(Note: You can generate these by running the Jupyter notebooks or `src/train.py` locally).*

**Step 3: Setup Environment Variables**
Copy the `.env.example` file and configure your AI local proxy settings:
```bash
cp .env.example .env
```
Ensure your `OPENAI_API_KEY` matches the Remote API access key set in your 9router dashboard.

**Step 4: Run with Docker Compose**
Start the entire stack (FastAPI backend and HTML frontend) using Docker:
```bash
docker compose up --build -d
```

**Step 5: Access the Dashboard**
Open your web browser and navigate to:
```text
http://localhost:8000
```
Click the **"Pindai Pasar Sekarang"** (Scan Market) button to initiate the live AI analysis. To analyze news, ensure your 9router is running and click the **✨ Analisis Berita dengan AI** button on any stock card.

---

## 📁 Project Structure

```text
stock-analysis/
├── dashboard/
│   ├── backend/
│   │   ├── main.py              # FastAPI app & router registry
│   │   └── routes/              # Modular API endpoints (predict, chart, news_agent)
│   └── frontend/
│       ├── index.html           # Main UI
│       ├── css/style.css        # Liquid glass design system
│       └── js/app.js            # Chart rendering + API calls + AI integration
├── dags/
│   └── stock_pipeline_dag.py    # Airflow DAG template for automation
├── src/
│   ├── config.py                # List of 99 BEI stock tickers
│   ├── features.py              # Feature engineering (20+ indicators)
│   └── train.py                 # Training script for XGBoost + Optuna
├── models/                      # Trained models (*.pkl) — NOT tracked by Git
├── Dockerfile                   # Backend container definition
├── docker-compose.yml           # Multi-container orchestration
├── .env                         # API keys & Configuration (NOT tracked by Git)
├── .env.example                 # Example environment variables
└── requirements.txt             # Python dependencies
```

---

## 📝 License

Distributed under the MIT License. See `LICENSE` for more information.

---

*Market Data provided by [Yahoo Finance](https://finance.yahoo.com/). Interactive charts powered by [Lightweight Charts™](https://github.com/tradingview/lightweight-charts) by TradingView (Apache 2.0).*
