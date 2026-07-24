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

def run_daily_after_market_job(skip_download=False, broadcast_telegram=True, save_to_json=True, save_to_db=True):
    """
    Rutin Scheduler Harian (16:05 WIB Setelah Pasar Tutup):
    1. Mengunduh data 700+ saham secara batch aman rate limit.
    2. Ekstraksi Feature Embedding & Indikator.
    3. Prediksi XGBoost + Asymmetric Sentiment Filter.
    4. Simpan ke database audit & cache JSON untuk UI instan (<5ms).

    Args:
        skip_download: Jika True, lewati download yfinance (pakai data DB yg ada).
        broadcast_telegram: Jika False, lewati pengiriman notifikasi Telegram.
        save_to_json: Jika False, lewati penulisan cache JSON (misal mode BSJP 15:30).
        save_to_db: Jika False, lewati simpan ke DB audit (misal mode BSJP 15:30).
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
    macro_eval = {"mode": "NORMAL", "macro_score": 0.0, "details": []}
    try:
        from src.agents.ihsg_macro_agent import IHSGMacroAgent
        macro_agent = IHSGMacroAgent()
        macro_eval = macro_agent.evaluate(skip_news=skip_download)
        print(f"[MACRO AGENT] Result: {macro_eval.get('mode_badge', 'NORMAL')} | Score: {macro_eval.get('macro_score', 0):+.1f}")
        for d in macro_eval.get('details', []):
            print(f"   {d}")
        
        if macro_eval.get('mode') == 'BLOCK':
            print(f"[MACRO GUARD] Market risk-off active ({macro_eval.get('mode_badge')}). Skip buy recommendations for today.")
            return {
                "status": "success",
                "data": [],
                "macro_mode": "BLOCK",
                "macro_eval": macro_eval,
                "message": f"IHSG Macro Guard Active: Downtrend/High Risk detected."
            }
    except Exception as e:
        print(f"[WARNING] Gagal mengevaluasi IHSG Macro Agent: {str(e)}")

    if not skip_download:
        try:
            ihsg = yf.download('^JKSE', period='100d', progress=False)
            if isinstance(ihsg.columns, pd.MultiIndex):
                ihsg_close = ihsg['Close'].iloc[:, 0]
            else:
                ihsg_close = ihsg['Close']
            ihsg_returns = pd.DataFrame({'IHSG_Return': ihsg_close.pct_change(1, fill_method=None)}, index=ihsg.index)
            if ihsg_returns.index.tz is not None:
                ihsg_returns.index = ihsg_returns.index.tz_localize(None)
        except Exception as e:
            print(f"[WARNING] Gagal download data IHSG returns: {str(e)}")

    all_latest = []
    
    for ticker in TICKERS:
        df = get_ticker_history_from_db(ticker, limit_days=100)
        if df.empty or len(df) < 20:
            continue
            
        # 🚫 SUSPEND & DELISTING GUARD
        # 1. Skip if 5-day trading volume is zero (Suspended by BEI)
        if 'Volume' in df.columns and len(df) >= 5 and df['Volume'].iloc[-5:].sum() == 0:
            continue
            
        # 2. Skip if price is completely frozen over 10 days (Zero Liquidity / Suspend)
        if 'Close' in df.columns and len(df) >= 10 and df['Close'].iloc[-10:].nunique() == 1 and df['Volume'].iloc[-10:].sum() == 0:
            continue
            
        # 3. Skip if last data timestamp is stale (> 7 calendar days old, e.g. Delisted)
        last_dt = pd.to_datetime(df.index[-1])
        now_dt = pd.Timestamp.now()
        if (now_dt - last_dt).days > 7:
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

    # 3. Jalankan audit sinyal trading hari ini (SEBELUM membuat/menyimpan sinyal esok hari)
    today_audit = {}
    recap = {}
    try:
        from dashboard.backend.routes.audit import run_audit, get_audit_recap, get_today_audit_summary
        run_audit()
        today_audit = get_today_audit_summary()
        recap = get_audit_recap()
    except Exception as ae:
        print(f"[AUDIT] Warning running pre-scan audit: {str(ae)}")

    # 4. Terapkan Asymmetric Risk Filter & Score Booster untuk sinyal esok hari
    filtered_candidates = apply_asymmetric_sentiment_filter(candidates)
    results = filtered_candidates[:10]

    # Simpan sinyal baru ke SQLite database audit & cache JSON
    if save_to_db:
        save_signals_to_db(results)

    payload = {
        "status": "success",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_scanned": len(combined_df),
        "macro_eval": macro_eval,
        "data": results
    }
    
    if save_to_json:
        with open(CACHE_FILE, 'w') as f:
            json.dump(payload, f, indent=2)

    # 5. Kirim siaran otomatis ke Telegram Bot (After-Market Audit & Sync)
    if broadcast_telegram:
        try:
            from src.notifications.telegram_bot import send_after_market_audit_broadcast
            send_after_market_audit_broadcast(recap, new_recommendations=results, today_audit=today_audit, macro_eval=macro_eval)
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

def run_midday_recap_job():
    """
    [FASE 2: 12:00 WIB - MIDDAY MARKET RECAP]
    Mengunduh data intraday Sesi 1 & mengirimkan update pasar sesi siang ke Telegram.
    """
    print("[SCHEDULER 12:00 WIB] Memulai pengiriman Midday Market Recap ke Telegram...")
    try:
        from src.notifications.telegram_bot import send_midday_recap_broadcast
        from dashboard.backend.routes.audit import get_today_audit_summary, run_audit
        run_audit()
        today_info = get_today_audit_summary()
        res = send_midday_recap_broadcast(today_info)
        print("[SUCCESS] [SCHEDULER 12:00 WIB] Midday Market Recap berhasil dikirim ke Telegram!")
        return res
    except Exception as e:
        print(f"[ERROR] [SCHEDULER 12:00 WIB] Gagal menjalankan Midday Recap: {str(e)}")
        return {"status": "error", "message": str(e)}

def run_bsjp_radar_job():
    """
    [FASE 3: 15:30 WIB - BSJP RADAR (BELI SORE JUAL PAGI)]
    Mengunduh data real-time 15:30 WIB, scan saham momentum sore, & kirim notifikasi BSJP ke Telegram.
    """
    print("[SCHEDULER 15:30 WIB] Memulai scan real-time BSJP Radar (Beli Sore Jual Pagi)...")
    try:
        res = run_daily_after_market_job(skip_download=False, broadcast_telegram=False, save_to_json=False, save_to_db=False)
        stocks = res.get("data", [])
        if stocks:
            from src.notifications.telegram_bot import send_bsjp_radar_broadcast
            b_res = send_bsjp_radar_broadcast(stocks)
            print("[SUCCESS] [SCHEDULER 15:30 WIB] BSJP Radar berhasil dikirim ke Telegram!")
            return b_res
    except Exception as e:
        print(f"[ERROR] [SCHEDULER 15:30 WIB] Gagal menjalankan BSJP Radar: {str(e)}")
    return {"status": "error", "message": "BSJP scan failed"}

def start_background_scheduler():
    """Menjalankan scheduler 4-fase di background thread (08:30, 12:00, 15:30, 16:05 WIB)."""
    if os.getenv("TESTING") == "true" or "pytest" in sys.modules:
        print("[INFO] Mode testing terdeteksi. Background scheduler dilewati.")
        return

    def loop():
        last_run = {}
        while True:
            today_str = time.strftime("%Y-%m-%d")
            now_time = time.strftime("%H:%M")

            schedules = {
                "08:30": run_morning_premarket_job,
                "12:00": run_midday_recap_job,
                "15:30": run_bsjp_radar_job,
                "16:05": run_daily_after_market_job
            }

            for sched_time, job_fn in schedules.items():
                if now_time == sched_time and last_run.get(sched_time) != today_str:
                    last_run[sched_time] = today_str
                    try:
                        job_fn()
                    except Exception as e:
                        print(f"[SCHEDULER] Error running {sched_time} job: {str(e)}")

            time.sleep(25)
            
    thread = threading.Thread(target=loop, daemon=True)
    thread.start()


