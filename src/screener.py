import os
import sys
import pandas as pd
import numpy as np
import yfinance as yf
import joblib
import logging
from pathlib import Path

# Setup Path agar bisa membaca src.config
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.config import TICKERS, PRICE_DATA_DIR, PROCESSED_DATA_DIR, PROFIT_THRESHOLD
from src.features.technical_indicators import add_technical_indicators

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_latest_data(ticker: str, ihsg_returns: pd.DataFrame) -> pd.DataFrame:
    """Download 100 hari terakhir dan hitung fitur untuk saham tertentu."""
    # Download 100 hari terakhir agar SMA_50 bisa dihitung
    df = yf.download(ticker, period='100d', progress=False)
    if df.empty:
        return pd.DataFrame()
        
    # Handle multi-index yfinance 0.2.x+
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel('Ticker') if 'Ticker' in df.columns.names else df.columns.get_level_values(0)
    
    # 1. Indikator Teknikal
    df = add_technical_indicators(df)
    
def generate_reason(row: pd.Series) -> str:
    """Menerjemahkan nilai teknikal ke dalam bahasa manusia."""
    reasons = []
    
    # RSI (Momentum)
    rsi = row.get('RSI_14', 50)
    if rsi < 30:
        reasons.append("Sangat Oversold (Obral Murah)")
    elif rsi < 45:
        reasons.append("Oversold (Koreksi Sehat)")
        
    # MACD (Trend)
    macd_diff = row.get('MACD_Diff', 0)
    if macd_diff > 0:
        reasons.append("MACD Menguat (Uptrend)")
        
    # SMA (Major Trend)
    if row.get('Close', 0) > row.get('SMA_50', 100000):
        reasons.append("Harga di atas MA-50")
        
    # IHSG
    if row.get('IHSG_Return', 0) > 0:
        reasons.append("IHSG Mendukung (Hijau)")
        
    if not reasons:
        reasons.append("Pola Volume & Momentum tersembunyi yang dikenali AI")
        
    return ", ".join(reasons)
    
    # 2. Fitur Baru: Lagged Returns (Sejarah masa lalu)
    df['Return_1d'] = df['Close'].pct_change(1)
    df['Return_2d'] = df['Close'].pct_change(2)
    df['Return_3d'] = df['Close'].pct_change(3)
    df['Return_5d'] = df['Close'].pct_change(5)
    
    # 3. Fitur Baru: Day of Week (0=Senin, 4=Jumat)
    df['Day_of_Week'] = df.index.dayofweek
    
    # 4. Fitur Baru: IHSG Return
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df = df.join(ihsg_returns, how='left')
    df['IHSG_Return'] = df['IHSG_Return'].fillna(0)
    
    # 5. Ticker identitas
    df['Ticker'] = ticker
    
    # Ambil HANYA baris terakhir (Data Hari Ini)
    latest_row = df.iloc[-1:].copy()
    
    return latest_row

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
    ihsg = yf.download('^JKSE', period='100d', progress=False)
    if isinstance(ihsg.columns, pd.MultiIndex):
        close_col = ('Close', '^JKSE') if ('Close', '^JKSE') in ihsg.columns else ihsg.columns[0]
        ihsg_close = ihsg[close_col]
    else:
        ihsg_close = ihsg['Close']
        
    ihsg_returns = pd.DataFrame(index=ihsg.index)
    ihsg_returns['IHSG_Return'] = ihsg_close.pct_change()
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
        
    combined_df = pd.concat(all_latest)
    
    # === PREPROCESSING (Pencocokan Kolom dengan X_train) ===
    # Daftar kolom fitur numerik (sesuai urutan persis saat training)
    numeric_cols = ['Close', 'High', 'Low', 'Open', 'Volume', 'OBV', 'ADI', 'VWAP', 'RSI_14', 'MACD', 'MACD_Signal', 'MACD_Diff', 'BB_High', 'BB_Low', 'BB_Mid', 'ATR_14', 'SMA_20', 'SMA_50', 'Return_1d', 'Return_2d', 'Return_3d', 'Return_5d', 'Day_of_Week', 'IHSG_Return']
    
    # Siapkan DataFrame akhir dengan urutan kolom numerik + One Hot Ticker
    final_cols = numeric_cols + [f"Tick_{t}" for t in sorted(TICKERS)]
    X = pd.DataFrame(0.0, index=combined_df.index, columns=final_cols)
    
    # Isi nilai numerik
    for col in numeric_cols:
        if col in combined_df.columns:
            X[col] = combined_df[col].astype(float)
            
    # Isi nilai One-Hot Ticker (1 untuk saham yang bersangkutan, 0 untuk yang lain)
    for i, row in combined_df.iterrows():
        tick_col = f"Tick_{row['Ticker']}"
        if tick_col in X.columns:
            X.loc[i, tick_col] = 1.0
            
    # Menghindari error apabila ada nilai kosong (inf/NaN) karena delay data Yahoo Finance
    X.replace([np.inf, -np.inf], np.nan, inplace=True)
    X.fillna(0, inplace=True) # Paksa isi 0 jika ada indikator gagal kalkulasi
    
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
    print(" 3. Take Profit jika sudah mencapai target +1.5% intraday.")
    print("="*55 + "\n")

if __name__ == "__main__":
    main()
