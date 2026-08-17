import sqlite3
import pandas as pd
from pathlib import Path
import sys

# Absolute import resolution
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.config import DB_PATH

def _ensure_valid_db(db_file: Path):
    """Pastikan file SQLite valid. Jika pointer LFS / corrupt, hapus agar re-created."""
    if db_file.exists():
        invalid = False
        try:
            with open(db_file, 'rb') as f:
                header = f.read(16)
                if header and not header.startswith(b'SQLite format 3'):
                    invalid = True
        except Exception:
            pass
        if invalid:
            try:
                db_file.unlink()
            except Exception:
                pass

def init_market_db():
    """Menginisialisasi tabel SQLite untuk menyimpan data pasar harian 700+ saham."""
    _ensure_valid_db(DB_PATH)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
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
    """Menyimpan DataFrame harga harian ke database SQLite dengan transaksi cepat (vectorized)."""
    if combined_df.empty:
        return
    
    init_market_db()
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    cursor = conn.cursor()
    
    df_reset = combined_df.reset_index()
    date_col = 'Date' if 'Date' in df_reset.columns else df_reset.columns[0]

    records = []
    for row in df_reset.to_dict('records'):
        ticker = str(row.get("Ticker", "")).strip()
        dt_val = row.get(date_col, "")
        if hasattr(dt_val, "strftime"):
            date_str = dt_val.strftime("%Y-%m-%d")
        else:
            date_str = str(dt_val).split("T")[0].split(" ")[0]

        open_p = float(row.get("Open", 0.0) or 0.0)
        high_p = float(row.get("High", 0.0) or 0.0)
        low_p = float(row.get("Low", 0.0) or 0.0)
        close_p = float(row.get("Close", 0.0) or 0.0)
        vol = float(row.get("Volume", 0.0) or 0.0)
        
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
    _ensure_valid_db(DB_PATH)
    init_market_db()
    try:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        query = """
            SELECT date, open as Open, high as High, low as Low, close as Close, volume as Volume
            FROM daily_prices
            WHERE ticker = ?
            ORDER BY date DESC
            LIMIT ?
        """
        df = pd.read_sql_query(query, conn, params=(ticker, limit_days))
        conn.close()
    except Exception:
        return pd.DataFrame()
    
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        df.sort_index(ascending=True, inplace=True)
    return df

def get_all_histories_from_db(limit_days: int = 100) -> dict:
    """Mengambil riwayat data harga seluruh 700+ ticker dari SQLite dalam 1 query tunggal (bulk fast read)."""
    _ensure_valid_db(DB_PATH)
    init_market_db()
    try:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        query = """
            SELECT ticker as Ticker, date, open as Open, high as High, low as Low, close as Close, volume as Volume
            FROM daily_prices
            ORDER BY date ASC
        """
        full_df = pd.read_sql_query(query, conn)
        conn.close()

        if full_df.empty:
            return {}

        result = {}
        for ticker_name, group in full_df.groupby("Ticker"):
            clean_t = str(ticker_name).strip()
            df = group.tail(limit_days).drop(columns=["Ticker"]).copy()
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            df.sort_index(inplace=True)
            result[clean_t] = df

        return result
    except Exception as e:
        print(f"[MARKET_DB] Error bulk reading database: {e}")
        return {}
