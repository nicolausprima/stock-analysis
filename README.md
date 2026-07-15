# StockAI — AI-Powered Day Trading Screener (Indonesia Market) 🇮🇩

> **Disclaimer:** This project is built for **educational purposes only**. It does not constitute financial or professional investment advice. Always conduct your own research before making any trading decisions.

---

## 🚧 Work in Progress Notice
**Current Status:** V1 (Technical Analysis Only)
This project is currently actively being developed. The current iteration relies entirely on price action and technical indicators (RSI, MACD, Volume, etc.). 
**Future Roadmap:** We are currently working on integrating **Macroeconomic Data** (interest rates, inflation) and **News Sentiment Analysis** using NLP to improve the prediction accuracy.

---

## 📊 Demo

This web application analyzes **99 selected stocks** from the Indonesia Stock Exchange (IDX / BEI) every day. It uses an **XGBoost** machine learning model trained on 20+ technical indicators to recommend the **Top 10** stocks with the strongest buy signals for day trading.

![StockAI Dashboard](dashboard/frontend/dashboard-preview.png)

---

## ✨ Features

| Feature | Description |
|---|---|
| 🤖 **XGBoost Model** | Trained on 5 years of historical data using Optuna for hyperparameter tuning. |
| 📈 **20+ Indicators** | Calculates RSI, MACD, Bollinger Bands, OBV, ATR, VWAP, SMA, and Bandarmologi (accumulation). |
| 📊 **Interactive Charts** | IHSG & individual stock charts (1D Intraday / 60D Historical) powered by TradingView Lightweight Charts. |
| 🔄 **Real-time Data** | Fetches the latest live market data from Yahoo Finance upon every scan. |
| 🎨 **Liquid Glass UI** | A modern, frosted glassmorphism design system with smooth micro-animations. |
| 🐳 **Docker Ready** | Single-command deployment utilizing Docker & Docker Compose. |

---

## ⚙️ How It Works

The core philosophy of this screener revolves around spotting short-term momentum and oversold bounces. 

```text
1. Data Pipeline → 2. Feature Engineering → 3. ML Scoring → 4. Recommendation
```

1. **Data Pipeline:** When you click "Scan", the backend fetches the latest price data for 99 top Indonesian stocks via the `yfinance` API.
2. **Feature Engineering:** The raw price/volume data is mathematically transformed into 20+ technical indicators (e.g., measuring momentum via RSI, trend via MACD, volatility via ATR).
3. **ML Scoring:** The XGBoost model (previously trained on historical patterns) evaluates these current technical features and assigns a "Buy Probability" score from 0 to 100%.
4. **Recommendation:** The system filters out the noise and presents the top 10 stocks with the highest probability of an intraday upward move, including predefined profit targets (+1.5%) and stop losses (-1.5%).

---

## ⚖️ Pros and Cons

### ✅ Pros (Strengths)
- **Emotionless Trading:** Removes human bias and FOMO by relying strictly on mathematical probabilities.
- **Time-Saving:** Scans 99 stocks in seconds, a task that would take a human hours to do manually.
- **Dynamic Adaptability:** The inclusion of the overall IHSG trend helps the model avoid buying during severe market crashes.

### ❌ Cons (Limitations)
- **No Fundamental/News Awareness (Yet):** Currently blind to sudden news, earnings reports, or macroeconomic shifts (this is actively being worked on).
- **Intraday Noise:** Short-term market movements in the Indonesian market can be highly volatile and manipulated by market makers (Bandar), which technicals alone sometimes fail to capture.
- **Yahoo Finance Delay:** Depending on the API, there might be a slight delay in price action compared to direct broker feeds.

---

## 🛠️ Tech Stack

- **Backend:** Python · FastAPI · yfinance · XGBoost · scikit-learn · pandas
- **Frontend:** Vanilla HTML/CSS/JS · TradingView Lightweight Charts
- **Pipeline / Orchestration:** Apache Airflow (Template Ready)
- **Containerization:** Docker · Docker Compose

---

## 🚀 Step-by-Step Setup Guide

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running.
- Git installed on your machine.

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

**Step 3: Run with Docker Compose**
Start the entire stack (FastAPI backend and HTML frontend) using Docker:
```bash
docker compose up --build -d
```

**Step 4: Access the Dashboard**
Open your web browser and navigate to:
```text
http://localhost:8000
```
Click the **"Pindai Pasar Sekarang"** (Scan Market) button to initiate the live AI analysis. The process usually takes about 10-30 seconds depending on your connection to Yahoo Finance.

---

## 📁 Project Structure

```text
stock-analysis/
├── dashboard/
│   ├── backend/
│   │   ├── main.py              # FastAPI app & router registry
│   │   └── routes/              # Modular API endpoints
│   └── frontend/
│       ├── index.html           # Main UI
│       ├── css/style.css        # Liquid glass design system
│       └── js/app.js            # Chart rendering + API calls
├── dags/
│   └── stock_pipeline_dag.py    # Airflow DAG template for automation
├── src/
│   ├── config.py                # List of 99 BEI stock tickers
│   ├── features.py              # Feature engineering (20+ indicators)
│   └── train.py                 # Training script for XGBoost + Optuna
├── models/                      # Trained models (*.pkl) — NOT tracked by Git
├── Dockerfile                   # Backend container definition
├── docker-compose.yml           # Multi-container orchestration
└── requirements.txt             # Python dependencies
```

---

## 📝 License

Distributed under the MIT License. See `LICENSE` for more information.

---

*Market Data provided by [Yahoo Finance](https://finance.yahoo.com/). Interactive charts powered by [Lightweight Charts™](https://github.com/tradingview/lightweight-charts) by TradingView (Apache 2.0).*
