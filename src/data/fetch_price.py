import os
import sys
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import logging
from pathlib import Path

# Add project root to sys.path to allow importing src.config
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from src.config import TICKERS, PRICE_DATA_DIR

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_price_for_ticker(ticker: str):
    file_path = PRICE_DATA_DIR / f"{ticker}.csv"
    
    # Define start date
    if file_path.exists():
        # Read existing data to find the last date
        try:
            existing_df = pd.read_csv(file_path, index_col='Date', parse_dates=True)
            if not existing_df.empty:
                # Fetch from the last available date minus 5 days (to catch any data corrections), then merge
                last_date = existing_df.index.max()
                start_date = (last_date - timedelta(days=5)).strftime('%Y-%m-%d')
                logging.info(f"[{ticker}] Found existing data up to {last_date.date()}. Fetching from {start_date}...")
            else:
                start_date = "2020-01-01"
                existing_df = None
        except Exception as e:
            logging.error(f"[{ticker}] Error reading existing file: {e}")
            start_date = "2020-01-01"
            existing_df = None
    else:
        logging.info(f"[{ticker}] No existing data. Fetching from 2020-01-01...")
        start_date = "2020-01-01"
        existing_df = None

    # Fetch data using yfinance
    try:
        df = yf.download(ticker, start=start_date, progress=False)
        
        if df.empty:
            logging.warning(f"[{ticker}] No data returned from yfinance.")
            return
            
        # yfinance sometimes returns MultiIndex columns, flatten it
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]
            
        df.index = pd.to_datetime(df.index)
        df.index.name = 'Date'
        
        # Merge with existing data
        if existing_df is not None:
            combined_df = pd.concat([existing_df, df])
            combined_df = combined_df[~combined_df.index.duplicated(keep='last')]
            combined_df.sort_index(inplace=True)
        else:
            combined_df = df
            
        # Save to csv
        combined_df.to_csv(file_path)
        logging.info(f"[{ticker}] Successfully saved {len(combined_df)} total rows to {file_path.name}")
        
    except Exception as e:
        logging.error(f"[{ticker}] Failed to fetch/save data: {e}")

def main():
    if not TICKERS:
        logging.error("No tickers found in configuration. Check tickers.txt")
        return
        
    logging.info(f"Starting batch incremental fetch for {len(TICKERS)} tickers...")
    for ticker in TICKERS:
        fetch_price_for_ticker(ticker)
    
    logging.info("Batch fetch completed.")

if __name__ == "__main__":
    main()
