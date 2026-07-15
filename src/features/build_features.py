import os
import sys
import pandas as pd
import logging
from pathlib import Path
import yfinance as yf

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from src.config import TICKERS, PRICE_DATA_DIR, PROCESSED_DATA_DIR, PROFIT_THRESHOLD
from src.features.technical_indicators import add_technical_indicators

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def build_features_for_ticker(ticker: str, ihsg_returns: pd.DataFrame) -> pd.DataFrame:
    file_path = PRICE_DATA_DIR / f"{ticker}.csv"
    if not file_path.exists():
        logging.warning(f"Data for {ticker} not found. Skipping.")
        return pd.DataFrame()
        
    df = pd.read_csv(file_path, index_col='Date', parse_dates=True)
    if df.empty:
        return pd.DataFrame()
        
    # 1. Tambahkan indikator teknikal & volume (LAMA)
    df = add_technical_indicators(df)
    
    # 2. FASE 3: Lagged Returns (Sejarah masa lalu)
    df['Return_1d'] = df['Close'].pct_change(1)
    df['Return_2d'] = df['Close'].pct_change(2)
    df['Return_3d'] = df['Close'].pct_change(3)
    df['Return_5d'] = df['Close'].pct_change(5)
    
    # 3. FASE 3: Day of Week (0=Senin, 4=Jumat)
    df['Day_of_Week'] = df.index.dayofweek
    
    # 4. FASE 3: IHSG Return
    # Pastikan zona waktu dihilangkan agar bisa di-join
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
        
    df = df.join(ihsg_returns, how='left')
    df['IHSG_Return'] = df['IHSG_Return'].fillna(0) # Jika hari libur beda, set 0
    
    # 5. Buat Target Label untuk Day Trading
    df['Next_Day_Open'] = df['Open'].shift(-1)
    df['Next_Day_Close'] = df['Close'].shift(-1)
    df['Next_Day_Return'] = (df['Next_Day_Close'] - df['Next_Day_Open']) / df['Next_Day_Open']
    
    df['Target'] = (df['Next_Day_Return'] >= PROFIT_THRESHOLD).astype(int)
    
    # 6. Ticker identitas
    df['Ticker'] = ticker
    
    # Drop rows dengan nilai NaN 
    features_to_check = [col for col in df.columns if col not in ['Next_Day_Open', 'Next_Day_Close', 'Next_Day_Return', 'Target']]
    df.dropna(subset=features_to_check, inplace=True)
    
    return df

def main():
    all_features = []
    
    logging.info("Fetching IHSG (^JKSE) data...")
    ihsg = yf.download('^JKSE', period='10y', progress=False)
    
    if isinstance(ihsg.columns, pd.MultiIndex):
        close_col = ('Close', '^JKSE') if ('Close', '^JKSE') in ihsg.columns else ihsg.columns[0]
        ihsg_close = ihsg[close_col]
    else:
        ihsg_close = ihsg['Close']
        
    ihsg_returns = pd.DataFrame(index=ihsg.index)
    ihsg_returns['IHSG_Return'] = ihsg_close.pct_change()
    
    if ihsg_returns.index.tz is not None:
        ihsg_returns.index = ihsg_returns.index.tz_localize(None)
    
    logging.info(f"Building features for {len(TICKERS)} tickers...")
    for ticker in TICKERS:
        df_features = build_features_for_ticker(ticker, ihsg_returns)
        if not df_features.empty:
            all_features.append(df_features)
            
    if not all_features:
        logging.error("No features built. Make sure data is fetched first.")
        return
        
    final_df = pd.concat(all_features)
    final_df.sort_index(inplace=True)
    
    output_path = PROCESSED_DATA_DIR / "feature_matrix.csv"
    final_df.to_csv(output_path)
    
    logging.info(f"Successfully saved feature matrix to {output_path}")
    logging.info(f"Total rows: {len(final_df)}, Total columns: {len(final_df.columns)}")
    
    valid_targets = final_df['Target'].dropna()
    label_dist = valid_targets.value_counts(normalize=True) * 100
    logging.info(f"Label Distribution (%):\n{label_dist}")

if __name__ == "__main__":
    main()
