import time
import pandas as pd
import yfinance as yf
from pathlib import Path
import sys

# Absolute import resolution
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.config import TICKERS, BATCH_SIZE, BATCH_DELAY_SECONDS
from src.database.market_db import save_daily_prices, init_market_db

def download_universe_in_batches(tickers_list=None, batch_size=BATCH_SIZE, delay_seconds=BATCH_DELAY_SECONDS):
    """
    Mengunduh data pasar 300+ saham BEI secara batch dengan jeda waktu (delay)
    agar 100% aman dari IP Ban / Rate Limit Yahoo Finance.
    """
    if tickers_list is None:
        tickers_list = TICKERS
        
    init_market_db()
    
    total_tickers = len(tickers_list)
    chunks = [tickers_list[i:i + batch_size] for i in range(0, total_tickers, batch_size)]
    
    print(f"[BATCH] Memulai pengunduhan {total_tickers} saham BEI ({len(chunks)} batch)...")
    
    processed_count = 0
    
    for idx, chunk in enumerate(chunks):
        ticker_str = " ".join(chunk)
        try:
            df_batch = yf.download(ticker_str, period="100d", progress=False, group_by="ticker", threads=True)
            
            records_to_save = []
            
            if len(chunk) == 1:
                t = chunk[0]
                if not df_batch.empty:
                    df_single = df_batch.copy()
                    df_single["Ticker"] = t
                    records_to_save.append(df_single)
            else:
                for t in chunk:
                    try:
                        if t in df_batch.columns.levels[0]:
                            df_single = df_batch[t].dropna(how="all").copy()
                            if not df_single.empty:
                                df_single["Ticker"] = t
                                records_to_save.append(df_single)
                    except Exception:
                        continue
                        
            if records_to_save:
                combined_batch = pd.concat(records_to_save)
                save_daily_prices(combined_batch)
                processed_count += len(records_to_save)
                
            print(f"  [OK] Batch {idx + 1}/{len(chunks)} ({len(chunk)} saham) tersimpan di SQLite DB.")
            
        except Exception as e:
            print(f"  [ERROR] Gagal pada Batch {idx + 1}: {str(e)}")
            
        # Sleep delay di antara batch requests
        if idx < len(chunks) - 1:
            time.sleep(delay_seconds)
            
    print(f"[SUCCESS] Selesai! Berhasil memproses {processed_count} saham di database lokal.")
    return processed_count

if __name__ == "__main__":
    download_universe_in_batches()
