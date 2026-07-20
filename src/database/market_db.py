import sqlite3
import pandas as pd
from pathlib import Path
import sys

# Absolute import resolution
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.config import DB_PATH

def init_market_db():
    """Menginisialisasi tabel SQLite untuk menyimpan data pasar harian 300+ saham."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_prices (
            ticker TEXT,
            date TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            PRIMARY KEY (ticker, date)
        )
    """)
    conn.commit()
    conn.close()

def save_daily_prices(combined_df: pd.DataFrame):
    """Menyimpan DataFrame harga harian ke database SQLite dengan transaksi cepat."""
    if combined_df.empty:
        return
    
    init_market_db()
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    records = []
    for idx, row in combined_df.iterrows():
        ticker = row.get("Ticker", "")
        date_str = str(idx).split(" ")[0]
        open_p = float(row.get("Open", 0.0))
        high_p = float(row.get("High", 0.0))
        low_p = float(row.get("Low", 0.0))
        close_p = float(row.get("Close", 0.0))
        vol = float(row.get("Volume", 0.0))
        
        if ticker and close_p > 0:
            records.append((ticker, date_str, open_p, high_p, low_p, close_p, vol))
            
    cursor.executemany("""
        INSERT OR REPLACE INTO daily_prices (ticker, date, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, records)
    
    conn.commit()
    conn.close()

def get_ticker_history_from_db(ticker: str, limit_days: int = 100) -> pd.DataFrame:
    """Mengambil riwayat data harga saham tertentu dari database SQLite."""
    conn = sqlite3.connect(str(DB_PATH))
    query = """
        SELECT date, open as Open, high as High, low as Low, close as Close, volume as Volume
        FROM daily_prices
        WHERE ticker = ?
        ORDER BY date DESC
        LIMIT ?
    """
    df = pd.read_sql_query(query, conn, params=(ticker, limit_days))
    conn.close()
    
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        df.sort_index(ascending=True, inplace=True)
    return df
