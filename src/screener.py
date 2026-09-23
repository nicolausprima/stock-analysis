import logging
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from dashboard.backend.yf_client import download_with_timeout

# Setup Path agar bisa membaca src.config
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.config import TICKERS
from src.features.technical_indicators import add_technical_indicators

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_latest_data(ticker: str, ihsg_returns: pd.DataFrame) -> pd.DataFrame:
    """Download 100 hari terakhir dan hitung fitur untuk saham tertentu."""
    # Download 100 hari terakhir agar SMA_50 bisa dihitung
    df = download_with_timeout(ticker, period='100d', progress=False)
    if df.empty:
        return pd.DataFrame()
        
    # Handle multi-index yfinance 0.2.x+
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel('Ticker') if 'Ticker' in df.columns.names else df.columns.get_level_values(0)
    
    # 1. Indikator Teknikal
    df = add_technical_indicators(df)
    
    # 2. Fitur Baru: Lagged Returns (Sejarah masa lalu)
    df['Return_1d'] = df['Close'].pct_change(1, fill_method=None)
    df['Return_2d'] = df['Close'].pct_change(2, fill_method=None)
    df['Return_3d'] = df['Close'].pct_change(3, fill_method=None)
    df['Return_5d'] = df['Close'].pct_change(5, fill_method=None)
    
    # 3. Fitur Baru: Day of Week (0=Senin, 4=Jumat)
    df['Day_of_Week'] = df.index.dayofweek
    
    # 4. Fitur Baru: IHSG Return
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df = df.join(ihsg_returns, how='left')
    # Kalender libur beda: benchmark flat HANYA kolom IHSG, bukan indikator.
    if 'IHSG_Return' in df.columns:
        df['IHSG_Return'] = df['IHSG_Return'].fillna(0)
    else:
        df['IHSG_Return'] = 0.0
    
    # 5. Ticker identitas
    df['Ticker'] = ticker
    
    # Ambil HANYA baris terakhir (Data Hari Ini)
    latest_row = df.iloc[-1:].copy()
    
    return latest_row

def build_serve_matrix(combined_df: pd.DataFrame, embed_df: pd.DataFrame,
                      expected_cols) -> pd.DataFrame:
    """Bangun matriks serve sesuai urutan skema train (AI-01).

    - Kolom = expected_cols berurutan persis; tanpa kolom Tick_*.
    - NaN indikator (warm-up) DITOLAK via ValueError, bukan fill-zero:
      RSI=0/MACD=0 palsu lebih berbahaya daripada skip ticker.
    """
    expected_cols = list(expected_cols)
    if any(c.startswith("Tick_") for c in expected_cols):
        raise ValueError("Train schema must not contain Tick_* one-hot columns")
    missing = [c for c in expected_cols
               if c not in combined_df.columns and c not in embed_df.columns]
    if missing:
        raise ValueError(f"Serve data missing train columns: {missing}")
    X = pd.DataFrame(np.nan, index=combined_df.index,
                     columns=expected_cols, dtype=float)
    for col in expected_cols:
        if col in combined_df.columns:
            X[col] = combined_df[col].astype(float).values
        else:
            X[col] = embed_df[col].astype(float).values
    X.replace([np.inf, -np.inf], np.nan, inplace=True)
    bad = X.columns[X.isna().any()].tolist()
    if bad:
        raise ValueError(
            f"Warm-up/missing NaN in serve features {bad}: "
            "skip ticker ini, jangan fill-zero")
    return X

def main():
    logging.info("=== 🚀 LIVE STOCK SCREENER INITIALIZED ===")
    
    # Load Model & Scaler (Pastikan Anda menjalankannya dari root folder 'stock-analysis')
    model_path = Path('models/best_xgboost_optuna.pkl')
    scaler_path = Path('models/standard_scaler.pkl')
    
    if not model_path.exists() or not scaler_path.exists():
        logging.error(f"Model/Scaler tidak ditemukan di {model_path}!")
        logging.error("Pastikan Anda sudah menjalankan ulang 02_Preprocessing.ipynb dan 03_Modelling.ipynb")
        return
        
    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    
    # Fetch IHSG
    logging.info("Mengunduh data IHSG (^JKSE)...")
    ihsg = download_with_timeout('^JKSE', period='100d', progress=False)
    if isinstance(ihsg.columns, pd.MultiIndex):
        close_col = ('Close', '^JKSE') if ('Close', '^JKSE') in ihsg.columns else ihsg.columns[0]
        ihsg_close = ihsg[close_col]
    else:
        ihsg_close = ihsg['Close']
        
    ihsg_returns = pd.DataFrame(index=ihsg.index)
    ihsg_returns['IHSG_Return'] = ihsg_close.pct_change(fill_method=None)
    if ihsg_returns.index.tz is not None:
        ihsg_returns.index = ihsg_returns.index.tz_localize(None)
        
    all_latest = []
    
    logging.info(f"Mengunduh data hari ini untuk {len(TICKERS)} saham...")
    for ticker in TICKERS:
        df_latest = get_latest_data(ticker, ihsg_returns)
        if not df_latest.empty:
            all_latest.append(df_latest)
            
    if not all_latest:
        logging.error("Gagal mendapatkan data terkini.")
        return
        
    from dashboard.backend.routes.features import generate_reason
    from src.features.embedding import extract_chart_feature_embeddings

    combined_df = pd.concat(all_latest)

    # === PREPROCESSING (AI-01: parity ke skema train, embedding bukan Tick_) ===
    if hasattr(scaler, 'feature_names_in_'):
        expected_cols = list(scaler.feature_names_in_)
    else:
        raise RuntimeError(
            "Scaler tanpa feature_names_in_: retrain via notebook + "
            "build_features.write_model_card sebelum serve")
    if any(c.startswith("Tick_") for c in expected_cols):
        raise RuntimeError(
            "Artefak scaler masih skema Tick_* basi: retrain ke skema "
            "embedding lalu serve ulang")
    embed_df = extract_chart_feature_embeddings(combined_df)
    # Tolak warm-up NaN (AI-06): skip ticker, bukan fill-zero.
    ok_mask = []
    for idx in combined_df.index:
        row = combined_df.loc[[idx]]
        emb = embed_df.loc[[idx]] if idx in embed_df.index else embed_df.iloc[0:0]
        try:
            build_serve_matrix(row, emb, expected_cols)
            ok_mask.append(True)
        except ValueError as ve:
            logging.warning("Skip warm-up/missing %s: %s", idx, ve)
            ok_mask.append(False)
    combined_df = combined_df.loc[ok_mask]
    embed_df = embed_df.loc[combined_df.index]
    if combined_df.empty:
        logging.error("Semua ticker warm-up/missing: tidak ada prediksi.")
        return
    X = build_serve_matrix(combined_df, embed_df, expected_cols)
    assert list(X.columns) == list(expected_cols), \
        f"Serve/train schema mismatch: serve={list(X.columns)} vs train={list(expected_cols)}"
    
    # Scaling
    X_scaled = scaler.transform(X)
    X_scaled_df = pd.DataFrame(X_scaled, index=X.index, columns=X.columns)
    
    # === PREDICTION ===
    logging.info("Menganalisis pola dan menghitung probabilitas...")
    predictions = model.predict(X_scaled_df)
    probabilities = model.predict_proba(X_scaled_df)[:, 1] # Ambil probabilitas kelas 1 (Beli)
    
    # Masukkan hasil kembali ke dataframe agar mudah dibaca
    # Karena combined_df mungkin punya duplicate index (hari yang sama untuk banyak ticker), kita pakai array numpy
    combined_df['Signal'] = predictions
    combined_df['Probability'] = probabilities
    
    # === TAMPILKAN HASIL ===
    print("\n" + "="*55)
    print(" [REKOMENDASI SAHAM UNTUK DIBELI BESOK PAGI] ")
    print("="*55)
    
    # Filter hanya yang diprediksi Beli, urutkan dari probabilitas tertinggi, dan AMBIL TOP 10 SAJA
    buy_candidates = combined_df[combined_df['Signal'] == 1].sort_values('Probability', ascending=False).head(10)
    
    if buy_candidates.empty:
        print("\n [!] Sistem AI menyatakan: TIDAK ADA SAHAM YANG AMAN.")
        print("    Kondisi pasar sedang tidak kondusif, lebih baik pegang Cash.")
    else:
        for _, row in buy_candidates.iterrows():
            reason = generate_reason(row)
            print(f" [*] {row['Ticker']:<6} | Probabilitas: {row['Probability']*100:.1f}% | Alasan AI: {reason}")
            
    print("\n" + "-"*55)
    print(" PENGINGAT (RISK MANAGEMENT):")
    print(" 1. Beli di harga Open besok pagi.")
    print(" 2. Pasang Stop Loss (Jual Rugi) otomatis di -1.0% / -1.5%.")
    print(" 3. Take Profit jika sudah mencapai target +3.0% intraday (horizon model).")
    print("="*55 + "\n")

if __name__ == "__main__":
    main()
