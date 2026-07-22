import json
import os
import time
import pandas as pd
import numpy as np
import yfinance as yf
import joblib
from pathlib import Path
import sys
import threading


# Absolute import resolution
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.config import TICKERS, CACHE_FILE, PROJECT_ROOT
from src.collector.batch_collector import download_universe_in_batches
from src.database.market_db import get_ticker_history_from_db
from src.features.technical_indicators import add_technical_indicators
from src.features.embedding import extract_chart_feature_embeddings
from dashboard.backend.routes.features import derive_signals, generate_reason
from dashboard.backend.routes.sentiment_filter import apply_asymmetric_sentiment_filter
from dashboard.backend.routes.audit import save_signals_to_db

def run_daily_after_market_job(skip_download=False, broadcast_telegram=True):
    """
    Rutin Scheduler Harian (16:05 WIB Setelah Pasar Tutup):
    1. Mengunduh data 700+ saham secara batch aman rate limit.
    2. Ekstraksi Feature Embedding & Indikator.
    3. Prediksi XGBoost + Asymmetric Sentiment Filter.
    4. Simpan ke database audit & cache JSON untuk UI instan (<5ms).

    Args:
        skip_download: Jika True, lewati download yfinance (pakai data DB yg ada).
        broadcast_telegram: Jika False, lewati pengiriman notifikasi Telegram.
    """
    print("[SCHEDULER 16:05 WIB] Memulai proses rutin harian...")
    
    # 1. Muat Model & Scaler terlebih dahulu
    model_path = PROJECT_ROOT / 'models' / 'best_xgboost_optuna.pkl'
    scaler_path = PROJECT_ROOT / 'models' / 'standard_scaler.pkl'
    
    if not model_path.exists() or not scaler_path.exists():
        print("[WARNING] Model/Scaler belum ditemukan di folder models/.")
        return {"status": "error", "message": "Model not found"}
        
    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    expected_cols = list(scaler.feature_names_in_)

    # 2. Batch download data harian (lewati jika skip_download=True)
    if not skip_download:
        download_universe_in_batches()

    # Download data IHSG (lewati jika skip_download=True)
    ihsg_returns = pd.DataFrame()
    if not skip_download:
        try:
            ihsg = yf.download('^JKSE', period='100d', progress=False)
            if isinstance(ihsg.columns, pd.MultiIndex):
                ihsg_close = ihsg['Close'].iloc[:, 0]
            else:
                ihsg_close = ihsg['Close']
            ihsg_returns = pd.DataFrame({'IHSG_Return': ihsg_close.pct_change()}, index=ihsg.index)
            if ihsg_returns.index.tz is not None:
                ihsg_returns.index = ihsg_returns.index.tz_localize(None)
        except Exception:
            ihsg_returns = pd.DataFrame()

    all_latest = []
    
    for ticker in TICKERS:
        df = get_ticker_history_from_db(ticker, limit_days=100)
        if df.empty or len(df) < 20:
            continue
            
        last_close = float(df['Close'].dropna().iloc[-1]) if not df['Close'].dropna().empty else 0.0
        
        df = add_technical_indicators(df)
        df['Return_1d'] = df['Close'].pct_change(1, fill_method=None)
        df['Return_2d'] = df['Close'].pct_change(2, fill_method=None)
        df['Return_3d'] = df['Close'].pct_change(3, fill_method=None)
        df['Return_5d'] = df['Close'].pct_change(5, fill_method=None)
        df['Day_of_Week'] = df.index.dayofweek
        
        if not ihsg_returns.empty:
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            df = df.join(ihsg_returns, how='left')
            df['IHSG_Return'] = df['IHSG_Return'].fillna(0)
        else:
            df['IHSG_Return'] = 0.0
            
        df['Ticker'] = ticker
        df['_raw_close'] = last_close
        
        valid_rows = df[df['Close'].notna()]
        if not valid_rows.empty:
            all_latest.append(valid_rows.iloc[-1:].copy())

    if not all_latest:
        print("⚠️ Tidak ada data saham yang valid.")
        return {"status": "error", "message": "No valid stocks"}

    combined_df = pd.concat(all_latest)
    combined_df.replace([np.inf, -np.inf], np.nan, inplace=True)
    combined_df.fillna(0, inplace=True)

    # Ekstraksi Feature Embeddings
    embed_df = extract_chart_feature_embeddings(combined_df)
    
    # Matriks Fitur X
    X = pd.DataFrame(0.0, index=combined_df.index, columns=expected_cols)
    for col in expected_cols:
        if col in combined_df.columns:
            X[col] = combined_df[col].astype(float)
        elif col in embed_df.columns:
            X[col] = embed_df[col].astype(float)
            
    X.replace([np.inf, -np.inf], np.nan, inplace=True)
    X.fillna(0, inplace=True)

    X_scaled = scaler.transform(X)
    X_scaled_df = pd.DataFrame(X_scaled, index=X.index, columns=X.columns)

    predictions = model.predict(X_scaled_df)
    probabilities = model.predict_proba(X_scaled_df)[:, 1]

    combined_df['Signal'] = predictions
    combined_df['Probability'] = (probabilities * 100).round(1)

    candidate_df = combined_df[combined_df['Signal'] == 1].sort_values('Probability', ascending=False).head(15)
    if candidate_df.empty:
        candidate_df = combined_df.sort_values('Probability', ascending=False).head(15)

    candidates = []
    for _, row in candidate_df.iterrows():
        signals = derive_signals(row)
        candidates.append({
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

    # Terapkan Asymmetric Risk Filter & Score Booster
    filtered_candidates = apply_asymmetric_sentiment_filter(candidates)
    results = filtered_candidates[:10]

    # Simpan sinyal ke SQLite database audit
    save_signals_to_db(results)

    # Simpan hasil ke cache JSON untuk UI instan (< 5ms)
    payload = {
        "status": "success",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_scanned": len(combined_df),
        "data": results
    }
    
    with open(CACHE_FILE, 'w') as f:
        json.dump(payload, f, indent=2)

    # Kirim siaran otomatis ke Telegram Bot (After-Market Audit & Sync)
    # Hanya dikirim saat scheduled job sungguhan (bukan saat dipanggil dari UI)
    if broadcast_telegram:
        try:
            from dashboard.backend.routes.audit import run_audit, get_audit_recap
            run_audit()
            recap = get_audit_recap()
            from src.notifications.telegram_bot import send_after_market_audit_broadcast
            send_after_market_audit_broadcast(recap)
        except Exception as te:
            print(f"[TELEGRAM] Error sending scheduler broadcast: {str(te)}")
    else:
        print("[INFO] Telegram broadcast dilewati (dipanggil dari UI / skip_download mode).")

    print(f"[SUCCESS] [SCHEDULER 16:05 WIB] Selesai! Data disinkronkan, sinyal di-audit & Telegram Broadcast tersampaikan.")
    return payload

def run_morning_premarket_job():
    """
    [FASE 1: 08:30 WIB - PRE-MARKET RADAR]
    Membaca hasil scan kemarin dari cache JSON dan mengirim notifikasi
    rekomendasi beli ke Telegram 30 menit sebelum bursa BEI dibuka (09:00 WIB).
    """
    print("[SCHEDULER 08:30 WIB] Memulai pengiriman Morning Pre-Market Radar ke Telegram...")
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, 'r') as f:
                data = json.load(f)
            stocks = data.get("data", [])
            if stocks:
                from src.notifications.telegram_bot import send_morning_radar_broadcast
                res = send_morning_radar_broadcast(stocks)
                print("[SUCCESS] [SCHEDULER 08:30 WIB] Morning Radar berhasil dikirim ke Telegram!")
                return res
        except Exception as e:
            print(f"[ERROR] [SCHEDULER 08:30 WIB] Gagal membaca cache JSON: {str(e)}")

    print("[WARNING] [SCHEDULER 08:30 WIB] Cache JSON rekomendasi belum tersedia.")
    return {"status": "error", "message": "Cache not available"}

def start_background_scheduler():
    """Menjalankan scheduler di background thread (08:30 WIB & 16:05 WIB)."""
    if os.getenv("TESTING") == "true" or "pytest" in sys.modules:
        print("[INFO] Mode testing terdeteksi. Background scheduler dilewati.")
        return

    def loop():
        while True:
            current_time = time.strftime("%H:%M")
            # 1. Pagi (08:30 WIB): Pre-Market Radar Telegram Broadcast
            if current_time == "08:30":
                try:
                    run_morning_premarket_job()
                except Exception as e:
                    print(f"Error morning scheduler: {str(e)}")
                time.sleep(60)
            # 2. Sore (16:05 WIB): After-Market Sync, Audit & Telegram Broadcast
            elif current_time == "16:05":
                try:
                    run_daily_after_market_job()
                except Exception as e:
                    print(f"Error after-market scheduler: {str(e)}")
                time.sleep(60)
            time.sleep(30)
            
    thread = threading.Thread(target=loop, daemon=True)
    thread.start()


