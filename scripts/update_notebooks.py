import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"
NOTEBOOKS_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------
# 1. GENERATE / UPDATE 02_Preprocessing.ipynb
# ---------------------------------------------------------
preprocessing_nb = {
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# 02. Preprocessing & Feature Embedding Extraction\n",
    "\n",
    "Notebook ini melakukan pembentukan **Target Profit +3.0%**, ekstraksi **Chart Pattern & Feature Embeddings** (RSI Norm, MACD Diff, SMA Ratios, ATR Volatility, Multi-period Return Velocity), serta pembuatan dataset `X_train.csv`, `X_test.csv`, `y_train.csv`, dan `y_test.csv` tanpa One-Hot Encoding Ticker kaku."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "import os\n",
    "import sys\n",
    "import pandas as pd\n",
    "import numpy as np\n",
    "import yfinance as yf\n",
    "from pathlib import Path\n",
    "\n",
    "# Set project root path\n",
    "PROJECT_ROOT = Path('.').resolve().parent\n",
    "if str(PROJECT_ROOT) not in sys.path:\n",
    "    sys.path.append(str(PROJECT_ROOT))\n",
    "\n",
    "from src.config import TICKERS, PROFIT_THRESHOLD\n",
    "from src.features.technical_indicators import add_technical_indicators\n",
    "from src.features.embedding import extract_chart_feature_embeddings\n",
    "\n",
    "print(f\"Total Tickers in Universe: {len(TICKERS)}\")\n",
    "print(f\"Target Profit Threshold: {PROFIT_THRESHOLD * 100:.1f}%\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Fetch IHSG Benchmark Returns\n",
    "try:\n",
    "    ihsg = yf.download('^JKSE', start='2020-01-01', progress=False)\n",
    "    ihsg_close = ihsg['Close'].iloc[:, 0] if isinstance(ihsg.columns, pd.MultiIndex) else ihsg['Close']\n",
    "    ihsg_returns = pd.DataFrame({'IHSG_Return': ihsg_close.pct_change()}, index=ihsg.index)\n",
    "    if ihsg_returns.index.tz is not None:\n",
    "        ihsg_returns.index = ihsg_returns.index.tz_localize(None)\n",
    "except Exception as e:\n",
    "    print(f\"Error fetching IHSG: {e}\")\n",
    "    ihsg_returns = pd.DataFrame()\n",
    "\n",
    "print(\"IHSG Data Ready.\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Download Historical Price Data & Build Features\n",
    "all_dfs = []\n",
    "sample_tickers = TICKERS[:50]\n",
    "\n",
    "for ticker in sample_tickers:\n",
    "    try:\n",
    "        df = yf.download(ticker, start='2020-01-01', progress=False)\n",
    "        if df.empty or len(df) < 100:\n",
    "            continue\n",
    "        if isinstance(df.columns, pd.MultiIndex):\n",
    "            df.columns = df.columns.droplevel('Ticker') if 'Ticker' in df.columns.names else df.columns.get_level_values(0)\n",
    "            \n",
    "        df = add_technical_indicators(df)\n",
    "        df['Return_1d'] = df['Close'].pct_change(1, fill_method=None)\n",
    "        df['Return_2d'] = df['Close'].pct_change(2, fill_method=None)\n",
    "        df['Return_3d'] = df['Close'].pct_change(3, fill_method=None)\n",
    "        df['Return_5d'] = df['Close'].pct_change(5, fill_method=None)\n",
    "        df['Day_of_Week'] = df.index.dayofweek\n",
    "        \n",
    "        if not ihsg_returns.empty:\n",
    "            if df.index.tz is not None:\n",
    "                df.index = df.index.tz_localize(None)\n",
    "            df = df.join(ihsg_returns, how='left')\n",
    "            df['IHSG_Return'] = df['IHSG_Return'].fillna(0)\n",
    "        else:\n",
    "            df['IHSG_Return'] = 0.0\n",
    "            \n",
    "        next_open = df['Open'].shift(-1)\n",
    "        next_high = df['High'].shift(-1)\n",
    "        df['Target'] = ((next_high - next_open) / next_open >= PROFIT_THRESHOLD).astype(int)\n",
    "        \n",
    "        df = df.iloc[:-1].copy()\n",
    "        df['Ticker'] = ticker\n",
    "        all_dfs.append(df)\n",
    "    except Exception:\n",
    "        continue\n",
    "\n",
    "full_df = pd.concat(all_dfs)\n",
    "full_df.dropna(subset=['Target', 'Close', 'Open', 'High', 'Low'], inplace=True)\n",
    "print(f\"Total Processed Dataset Rows: {len(full_df)}\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Extract Feature Embeddings\n",
    "embed_df = extract_chart_feature_embeddings(full_df)\n",
    "feature_cols = [\n",
    "    'RSI_14', 'MACD_Diff', 'SMA_20', 'SMA_50', 'ATR_14',\n",
    "    'Return_1d', 'Return_2d', 'Return_3d', 'Return_5d',\n",
    "    'Embed_RSI_Norm', 'Embed_MACD_Diff', 'Embed_SMA20_Ratio',\n",
    "    'Embed_SMA50_Ratio', 'Embed_Volatility_ATR', 'Embed_Return_1d',\n",
    "    'Embed_Return_2d', 'Embed_Return_3d', 'Embed_Return_5d',\n",
    "    'Embed_Log_Volume', 'Embed_IHSG_Return'\n",
    "]\n",
    "\n",
    "X = pd.concat([full_df, embed_df], axis=1)[feature_cols]\n",
    "y = full_df['Target']\n",
    "\n",
    "X.replace([np.inf, -np.inf], np.nan, inplace=True)\n",
    "X.fillna(0, inplace=True)\n",
    "\n",
    "# Split Train and Test Sets (80% Train, 20% Test Time-based)\n",
    "split_idx = int(len(X) * 0.8)\n",
    "X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]\n",
    "y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]\n",
    "\n",
    "processed_dir = PROJECT_ROOT / 'data' / 'processed'\n",
    "processed_dir.mkdir(parents=True, exist_ok=True)\n",
    "\n",
    "X_train.to_csv(processed_dir / 'X_train.csv')\n",
    "X_test.to_csv(processed_dir / 'X_test.csv')\n",
    "y_train.to_csv(processed_dir / 'y_train.csv')\n",
    "y_test.to_csv(processed_dir / 'y_test.csv')\n",
    "\n",
    "print(f\"Saved X_train: {X_train.shape}, X_test: {X_test.shape}\")"
   ]
  }
 ],
 "metadata": {
  "language_info": {
   "name": "python"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 2
}

with open(NOTEBOOKS_DIR / "02_Preprocessing.ipynb", "w", encoding="utf-8") as f:
    json.dump(preprocessing_nb, f, indent=1)

print("[SUCCESS] Updated 02_Preprocessing.ipynb")

# ---------------------------------------------------------
# 2. GENERATE / UPDATE 03_Modelling.ipynb
# ---------------------------------------------------------
modelling_nb = {
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# 03. Model Training & Evaluation (Feature Embedding + XGBoost)\n",
    "\n",
    "Notebook ini melatih model **XGBoost Classifier** dengan **Feature & Chart Embeddings**, menangani imbalansi data dengan `scale_pos_weight`, menguji performa klasifikasi (Precision, Recall, F1-Score, Confusion Matrix), dan menyimpan `best_xgboost_optuna.pkl` serta `standard_scaler.pkl`."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "import os\n",
    "import sys\n",
    "import pandas as pd\n",
    "import numpy as np\n",
    "import joblib\n",
    "from pathlib import Path\n",
    "from xgboost import XGBClassifier\n",
    "from sklearn.preprocessing import StandardScaler\n",
    "from sklearn.metrics import classification_report, confusion_matrix\n",
    "\n",
    "# Set project root path\n",
    "PROJECT_ROOT = Path('.').resolve().parent\n",
    "if str(PROJECT_ROOT) not in sys.path:\n",
    "    sys.path.append(str(PROJECT_ROOT))\n",
    "\n",
    "processed_dir = PROJECT_ROOT / 'data' / 'processed'\n",
    "X_train = pd.read_csv(processed_dir / 'X_train.csv', index_col=0)\n",
    "X_test = pd.read_csv(processed_dir / 'X_test.csv', index_col=0)\n",
    "y_train = pd.read_csv(processed_dir / 'y_train.csv', index_col=0)['Target']\n",
    "y_test = pd.read_csv(processed_dir / 'y_test.csv', index_col=0)['Target']\n",
    "\n",
    "print(f\"X_train shape: {X_train.shape}, X_test shape: {X_test.shape}\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Calculate Imbalance Ratio\n",
    "ratio = float(np.sum(y_train == 0)) / max(np.sum(y_train == 1), 1)\n",
    "print(f\"Imbalance Ratio (Scale Pos Weight): {ratio:.2f}\")\n",
    "\n",
    "# Standard Scaling\n",
    "scaler = StandardScaler()\n",
    "X_train_scaled = scaler.fit_transform(X_train)\n",
    "X_test_scaled = scaler.transform(X_test)\n",
    "\n",
    "X_train_scaled_df = pd.DataFrame(X_train_scaled, columns=X_train.columns)\n",
    "X_test_scaled_df = pd.DataFrame(X_test_scaled, columns=X_test.columns)"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Model Training with XGBoost Classifier\n",
    "model = XGBClassifier(\n",
    "    n_estimators=120,\n",
    "    max_depth=4,\n",
    "    learning_rate=0.03,\n",
    "    subsample=0.8,\n",
    "    colsample_bytree=0.8,\n",
    "    scale_pos_weight=min(ratio, 3.0),\n",
    "    random_state=42\n",
    ")\n",
    "\n",
    "print(\"Melatih model XGBoost Feature Embedding...\")\n",
    "model.fit(X_train_scaled_df, y_train)\n",
    "print(\"Pelatihan Selesai!\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Model Evaluation on Test Data\n",
    "y_pred = model.predict(X_test_scaled_df)\n",
    "y_proba = model.predict_proba(X_test_scaled_df)[:, 1]\n",
    "\n",
    "print(\"--- Classification Report (Test Data) ---\")\n",
    "print(classification_report(y_test, y_pred))\n",
    "\n",
    "print(\"--- Confusion Matrix ---\")\n",
    "print(confusion_matrix(y_test, y_pred))"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Save Trained Model & Scaler Artifacts\n",
    "models_dir = PROJECT_ROOT / 'models'\n",
    "models_dir.mkdir(parents=True, exist_ok=True)\n",
    "\n",
    "joblib.dump(model, models_dir / 'best_xgboost_optuna.pkl')\n",
    "joblib.dump(scaler, models_dir / 'standard_scaler.pkl')\n",
    "\n",
    "print(f\"Model berhasil disimpan di {models_dir / 'best_xgboost_optuna.pkl'}\")\n",
    "print(f\"Scaler berhasil disimpan di {models_dir / 'standard_scaler.pkl'}\")"
   ]
  }
 ],
 "metadata": {
  "language_info": {
   "name": "python"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 2
}

with open(NOTEBOOKS_DIR / "03_Modelling.ipynb", "w", encoding="utf-8") as f:
    json.dump(modelling_nb, f, indent=1)

print("[SUCCESS] Updated 03_Modelling.ipynb")
