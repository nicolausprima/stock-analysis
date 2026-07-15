from fastapi import APIRouter, HTTPException
import pandas as pd
import numpy as np
import yfinance as yf
import joblib
from pathlib import Path
import sys

# Konfigurasi path untuk absolute import
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.config import TICKERS
from src.features.technical_indicators import add_technical_indicators
from .features import generate_reason, derive_signals

router = APIRouter()

@router.get("/recommendations")
def get_recommendations():
    model_path = PROJECT_ROOT / 'models' / 'best_xgboost_optuna.pkl'
    scaler_path = PROJECT_ROOT / 'models' / 'standard_scaler.pkl'

    if not model_path.exists() or not scaler_path.exists():
        raise HTTPException(
            status_code=500, 
            detail="Model/Scaler tidak ditemukan. Harap latih model di Notebook terlebih dahulu."
        )

    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)

    # Deteksi kolom dinamis dari Scaler
    expected_cols = list(scaler.feature_names_in_)

    # Download IHSG
    ihsg = yf.download('^JKSE', period='100d', progress=False)
    if isinstance(ihsg.columns, pd.MultiIndex):
        ihsg_close = ihsg['Close'].iloc[:, 0] if hasattr(ihsg['Close'], 'iloc') else ihsg['Close']
    else:
        ihsg_close = ihsg['Close']
        
    ihsg_returns = pd.DataFrame({'IHSG_Return': ihsg_close.pct_change()}, index=ihsg.index)
    if ihsg_returns.index.tz is not None:
        ihsg_returns.index = ihsg_returns.index.tz_localize(None)

    all_latest = []
    valid_tickers = [t for t in TICKERS if f"Tick_{t}" in expected_cols]

    for ticker in valid_tickers:
        df = yf.download(ticker, period='100d', progress=False)
        if df.empty:
            continue
            
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel('Ticker') if 'Ticker' in df.columns.names else df.columns.get_level_values(0)

        # Simpan Close asli dari baris terakhir yang TIDAK NaN
        close_series = df['Close'].dropna()
        if close_series.empty:
            continue
            
        try:
            last_close = float(close_series.iloc[-1])
        except Exception:
            last_close = 0.0

        df = add_technical_indicators(df)
        df['Return_1d'] = df['Close'].pct_change(1, fill_method=None)
        df['Return_2d'] = df['Close'].pct_change(2, fill_method=None)
        df['Return_3d'] = df['Close'].pct_change(3, fill_method=None)
        df['Return_5d'] = df['Close'].pct_change(5, fill_method=None)
        df['Day_of_Week'] = df.index.dayofweek
        
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
            
        df = df.join(ihsg_returns, how='left')
        df['IHSG_Return'] = df['IHSG_Return'].fillna(0)
        df['Ticker'] = ticker
        df['_raw_close'] = last_close

        # Gunakan baris terakhir yang close-nya valid (bukan NaN)
        valid_rows = df[df['Close'].notna()]
        if valid_rows.empty:
            continue
        all_latest.append(valid_rows.iloc[-1:].copy())

    if not all_latest:
        raise HTTPException(status_code=500, detail="Gagal mendapatkan data terkini dari Yahoo Finance.")

    combined_df = pd.concat(all_latest)

    # Simpan kolom penting sebelum fillna
    for col in ['_raw_close', 'RSI_14', 'MACD_Diff', 'SMA_50']:
        combined_df[col] = combined_df[col].copy()

    combined_df.replace([np.inf, -np.inf], np.nan, inplace=True)
    combined_df.fillna(0, inplace=True)

    # Bangun X sesuai expected_cols
    X = pd.DataFrame(0.0, index=combined_df.index, columns=expected_cols)
    for col in expected_cols:
        if col in combined_df.columns and not col.startswith('Tick_'):
            X[col] = combined_df[col].astype(float)
            
    for i, row in combined_df.iterrows():
        tick_col = f"Tick_{row['Ticker']}"
        if tick_col in X.columns:
            X.loc[i, tick_col] = 1.0
            
    X.replace([np.inf, -np.inf], np.nan, inplace=True)
    X.fillna(0, inplace=True)

    X_scaled = scaler.transform(X)
    X_scaled_df = pd.DataFrame(X_scaled, index=X.index, columns=X.columns)

    predictions = model.predict(X_scaled_df)
    probabilities = model.predict_proba(X_scaled_df)[:, 1]

    combined_df['Signal'] = predictions
    combined_df['Probability'] = (probabilities * 100).round(1)

    # Prioritaskan Signal==1, fallback ke semua jika kosong
    buy_df = combined_df[combined_df['Signal'] == 1].sort_values('Probability', ascending=False).head(10)
    if buy_df.empty:
        buy_df = combined_df.sort_values('Probability', ascending=False).head(10)

    results = []
    for _, row in buy_df.iterrows():
        # Memanfaatkan fungsi derive_signals dari features.py
        signals = derive_signals(row)
        
        results.append({
            "ticker": row['Ticker'],
            "probability": float(row['Probability']),
            "signal": int(row.get('Signal', 0)),
            "close_price": signals['close_price'],
            "target_price": signals['target_price'],
            "stop_loss": signals['stop_loss'],
            "rsi": signals['rsi'],
            "rsi_signal": signals['rsi_signal'],
            "macd_signal": signals['macd_signal'],
            "trend": signals['trend'],
            "reason": generate_reason(row)
        })

    return {"status": "success", "data": results}
