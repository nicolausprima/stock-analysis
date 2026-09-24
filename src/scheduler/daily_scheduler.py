import json
import os
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from dashboard.backend.yf_client import download_with_timeout


def _get_wib_now():
    """Mengembalikan datetime saat ini dalam WIB (UTC+7) yang akurat di mana pun server di-deploy."""
    return datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=7)))


# Absolute import resolution
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from dashboard.backend.routes.audit import save_signals_to_db
from dashboard.backend.routes.features import derive_signals, generate_reason
from dashboard.backend.routes.sentiment_filter import apply_asymmetric_sentiment_filter
from src.collector.batch_collector import download_universe_in_batches
from src.config import CACHE_FILE, PROJECT_ROOT, TICKERS
from src.database.market_db import get_all_histories_from_db, get_ticker_history_from_db
from src.features.embedding import extract_chart_feature_embeddings
from src.features.technical_indicators import add_technical_indicators


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
        macro_eval = macro_agent.evaluate(skip_news=skip_download, skip_sectors=skip_download)
        mode_text = str(macro_eval.get('mode_badge', 'NORMAL')).encode('ascii', errors='replace').decode('ascii')
        print(f"[MACRO AGENT] Result: {mode_text} | Score: {macro_eval.get('macro_score', 0):+.1f}")
        for d in macro_eval.get('details', []):
            safe_d = str(d).encode('ascii', errors='replace').decode('ascii')
            print(f"   {safe_d}")
        
        if macro_eval.get('mode') == 'BLOCK':
            print(f"[MACRO GUARD] Market risk-off active ({mode_text}). Menerapkan filter ketat High Conviction (Prob >= 75%) & alokasi defensif.")
    except Exception as e:
        print(f"[WARNING] Gagal mengevaluasi IHSG Macro Agent: {e!s}")

    if not skip_download:
        try:
            ihsg = download_with_timeout('^JKSE', period='100d', progress=False)
            if isinstance(ihsg.columns, pd.MultiIndex):
                ihsg_close = ihsg['Close'].iloc[:, 0]
            else:
                ihsg_close = ihsg['Close']
            ihsg_returns = pd.DataFrame({'IHSG_Return': ihsg_close.pct_change(1, fill_method=None)}, index=ihsg.index)
            if ihsg_returns.index.tz is not None:
                ihsg_returns.index = ihsg_returns.index.tz_localize(None)
        except Exception as e:
            print(f"[WARNING] Gagal download data IHSG returns: {e!s}")

    all_latest = []
    
    # Fast 1-query bulk read from SQLite database
    history_dict = get_all_histories_from_db(limit_days=100)

    # Dapatkan tanggal data paling akhir di database sebagai referensi
    all_dates = [pd.to_datetime(df.index[-1]) for df in history_dict.values() if not df.empty]
    max_db_dt = max(all_dates) if all_dates else pd.Timestamp.now()
    ref_dt = max_db_dt

    for ticker in TICKERS:
        df = history_dict.get(ticker, pd.DataFrame())
        if df.empty or len(df) < 20:
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
        if (ref_dt - last_dt).days > 7:
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
            # Kalender libur beda: benchmark flat HANYA kolom IHSG (AI-06).
            if 'IHSG_Return' in df.columns:
                df['IHSG_Return'] = df['IHSG_Return'].fillna(0)
            else:
                df['IHSG_Return'] = 0.0
        else:
            df['IHSG_Return'] = 0.0

        df['Ticker'] = ticker
        df['_raw_close'] = last_close
        
        valid_rows = df[df['Close'].notna()]
        if not valid_rows.empty:
            all_latest.append(valid_rows.iloc[-1:].copy())

    if not all_latest:
        print("[WARNING] Tidak ada data saham yang valid.")
        return {"status": "error", "message": "No valid stocks"}

    combined_df = pd.concat(all_latest)
    combined_df.replace([np.inf, -np.inf], np.nan, inplace=True)
    # AI-06: TANPA fillna(0). Baris warm-up/missing ditolak per-ticker di
    # bawah (skip), bukan diisi nol (RSI=0 = sinyal oversold palsu).

    # Ekstraksi Feature Embeddings
    embed_df = extract_chart_feature_embeddings(combined_df)

    # Matriks Fitur X — skema + urutan = expected_cols (AI-01).
    # Ticker warm-up/missing (NaN) di-skip, bukan di-zero-fill.
    from src.screener import build_serve_matrix
    ok_idx = []
    for idx in combined_df.index:
        row = combined_df.loc[[idx]]
        emb = embed_df.loc[[idx]] if idx in embed_df.index else embed_df.iloc[0:0]
        try:
            build_serve_matrix(row, emb, expected_cols)
            ok_idx.append(idx)
        except ValueError:
            continue
    if not ok_idx:
        print("[WARNING] Semua ticker warm-up/missing: tidak ada prediksi.")
        return {"status": "error", "message": "All tickers in warm-up"}
    combined_df = combined_df.loc[ok_idx]
    embed_df = embed_df.loc[combined_df.index]
    X = build_serve_matrix(combined_df, embed_df, expected_cols)
    assert list(X.columns) == list(expected_cols), \
        f"Serve/train schema mismatch: serve={list(X.columns)} vs train={list(expected_cols)}"

    X_scaled = scaler.transform(X)
    X_scaled_df = pd.DataFrame(X_scaled, index=X.index, columns=X.columns)

    predictions = model.predict(X_scaled_df)
    probabilities = model.predict_proba(X_scaled_df)[:, 1]

    combined_df['Signal'] = predictions
    combined_df['Probability'] = (probabilities * 100).round(1)

    is_block_mode = macro_eval.get('mode') == 'BLOCK'
    min_prob = 75.0 if is_block_mode else 65.0

    # Prioritaskan sinyal beli konvinsi tinggi (Signal == 1 & Prob >= min_prob)
    high_conviction = combined_df[(combined_df['Signal'] == 1) & (combined_df['Probability'] >= min_prob)].sort_values('Probability', ascending=False)
    
    # Lengkapi hingga minimal 15 kandidat terbaik dari universe bursa untuk menjamin Top 10 penuh
    if len(high_conviction) < 15:
        secondary = combined_df[combined_df['Probability'] >= min_prob].sort_values('Probability', ascending=False)
        remaining = combined_df.sort_values('Probability', ascending=False)
        candidate_df = pd.concat([high_conviction, secondary, remaining]).drop_duplicates(subset=['Ticker']).head(15)
    else:
        candidate_df = high_conviction.head(15)
    hc_tickers = set(high_conviction['Ticker'].tolist())

    from src.agents.ihsg_macro_agent import get_ticker_sector
    leading_sectors = macro_eval.get("sector_rotation", {}).get("leading_sectors", [])

    candidates = []
    for _, row in candidate_df.iterrows():
        signals = derive_signals(row)
        sec = get_ticker_sector(row['Ticker'])
        is_leading = sec in leading_sectors
        # Prob mentah model (pra-booster) disimpan terpisah untuk audit jujur.
        raw_model_prob = round(float(row['Probability']), 1)
        # Sektor Booster: +2.0% probabilitas jika saham berada di sektor leading inflow
        boosted_prob = min(98.5, raw_model_prob + (2.0 if is_leading else 0.0))
        # Tandai apakah kandidat ini lolos high-conviction model murni
        # (Signal==1 & prob>=ambang) atau hanya pengisi fallback Top 10.
        is_hc = bool(row['Ticker'] in hc_tickers)

        # Jika BLOCK mode aktif, Kelly allocation dipotong 50% untuk manajemen risiko defensif
        base_kelly = signals.get('kelly_allocation', 10.0)
        adj_kelly = round(base_kelly * 0.5, 1) if is_block_mode else base_kelly

        base_reason = generate_reason(row)
        if is_block_mode:
            base_reason = f"[DEFENSIVE] IHSG Downtrend. High-conviction setup only. {base_reason}"

        candidates.append({
            "ticker": row['Ticker'],
            "sector": sec,
            "is_leading_sector": is_leading,
            "is_high_conviction": is_hc,
            "probability_raw": raw_model_prob,
            "probability": round(boosted_prob, 1),
            "signal": int(row.get('Signal', 0)),
            "close_price": signals['close_price'],
            "target_price": signals['target_price'],
            "stop_loss": signals['stop_loss'],
            "rsi": signals['rsi'],
            "rsi_signal": signals['rsi_signal'],
            "macd_signal": signals['macd_signal'],
            "trend": signals['trend'],
            "adx": signals.get('adx', 20),
            "rvol": signals.get('rvol', 1.0),
            "risk_reward_ratio": signals.get('risk_reward_ratio', 2.0),
            "kelly_allocation": adj_kelly,
            "reason": base_reason
        })

    # 3. Jalankan audit sinyal trading hari ini (SEBELUM membuat/menyimpan sinyal esok hari)
    today_audit = {}
    recap = {}
    try:
        from dashboard.backend.routes.audit import (
            get_audit_recap,
            get_today_audit_summary,
            run_audit,
        )
        run_audit()
        today_audit = get_today_audit_summary()
        recap = get_audit_recap()
    except Exception as ae:
        print(f"[AUDIT] Warning running pre-scan audit: {ae!s}")

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
        "macro_mode": macro_eval.get("mode", "NORMAL"),
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
            print(f"[TELEGRAM] Error sending scheduler broadcast: {te!s}")
    else:
        print("[INFO] Telegram broadcast dilewati (dipanggil dari UI / skip_download mode).")

    print("[SUCCESS] [SCHEDULER 16:05 WIB] Selesai! Data disinkronkan, sinyal di-audit & Telegram Broadcast tersampaikan.")
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
            print(f"[ERROR] [SCHEDULER 08:30 WIB] Gagal membaca cache JSON: {e!s}")

    print("[WARNING] [SCHEDULER 08:30 WIB] Cache JSON rekomendasi belum tersedia.")
    return {"status": "error", "message": "Cache not available"}

def run_midday_recap_job():
    """
    [FASE 2: 12:00 WIB - MIDDAY MARKET RECAP]
    Mengunduh data intraday Sesi 1 & mengirimkan update pasar sesi siang ke Telegram.
    """
    print("[SCHEDULER 12:00 WIB] Memulai pengiriman Midday Market Recap ke Telegram...")
    try:
        from dashboard.backend.routes.audit import get_today_audit_summary, run_audit
        from src.notifications.telegram_bot import send_midday_recap_broadcast
        run_audit()
        today_info = get_today_audit_summary()
        res = send_midday_recap_broadcast(today_info)
        print("[SUCCESS] [SCHEDULER 12:00 WIB] Midday Market Recap berhasil dikirim ke Telegram!")
        return res
    except Exception as e:
        print(f"[ERROR] [SCHEDULER 12:00 WIB] Gagal menjalankan Midday Recap: {e!s}")
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
        print(f"[ERROR] [SCHEDULER 15:30 WIB] Gagal menjalankan BSJP Radar: {e!s}")
    return {"status": "error", "message": "BSJP scan failed"}

def start_background_scheduler():
    """Menjalankan scheduler 4-fase di background thread (08:30, 12:00, 15:30, 16:05 WIB)."""
    if os.getenv("TESTING") == "true" or "pytest" in sys.modules:
        print("[INFO] Mode testing terdeteksi. Background scheduler dilewati.")
        return

    def loop():
        last_run = {}
        while True:
            wib_now = _get_wib_now()
            today_str = wib_now.strftime("%Y-%m-%d")
            now_time = wib_now.strftime("%H:%M")

            schedules = [
                ("08:30", "08:45", run_morning_premarket_job),
                ("12:00", "12:15", run_midday_recap_job),
                ("15:30", "15:45", run_bsjp_radar_job),
                ("16:05", "16:20", run_daily_after_market_job)
            ]

            for sched_time, end_window, job_fn in schedules:
                if (sched_time <= now_time <= end_window) and last_run.get(sched_time) != today_str:
                    last_run[sched_time] = today_str
                    try:
                        job_fn()
                    except Exception as e:
                        print(f"[SCHEDULER] Error running {sched_time} job: {e!s}")

            time.sleep(20)
            
    thread = threading.Thread(target=loop, daemon=True)
    thread.start()


