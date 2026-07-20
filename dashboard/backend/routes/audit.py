import os
import sqlite3
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import pandas as pd
import yfinance as yf
from pathlib import Path

# Konfigurasi path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DB_PATH = PROJECT_ROOT / "data" / "signals_audit.db"

# Pastikan folder data ada
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

router = APIRouter()

def init_db():
    """Menginisialisasi database SQLite dan membuat tabel signals jika belum ada."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            entry_price REAL,
            target_price REAL,
            stop_loss REAL,
            probability REAL,
            status TEXT DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

# Jalankan inisialisasi database saat module di-load
init_db()

class SignalInsert(BaseModel):
    ticker: str
    entry_price: float
    target_price: float
    stop_loss: float
    probability: float

def save_signals_to_db(signals: list[dict]):
    """Menyimpan list sinyal baru ke database. Menghindari duplikasi ticker pada hari kalender yang sama."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # Dapatkan tanggal hari ini (YYYY-MM-DD) di local time
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    for s in signals:
        ticker = s["ticker"]
        # Bersihkan format ticker (.JK)
        clean_ticker = ticker.replace(".JK", "")
        
        # Cek apakah sudah ada sinyal untuk ticker ini yang dibuat hari ini
        cursor.execute("""
            SELECT id FROM signals 
            WHERE ticker = ? AND strftime('%Y-%m-%d', created_at) = ?
        """, (clean_ticker, today_str))
        
        row = cursor.fetchone()
        if row is None:
            # Jika belum ada, lakukan insert
            cursor.execute("""
                INSERT INTO signals (ticker, entry_price, target_price, stop_loss, probability, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'PENDING', datetime('now', 'localtime'), datetime('now', 'localtime'))
            """, (clean_ticker, s["close_price"], s["target_price"], s["stop_loss"], s["probability"]))
            
    conn.commit()
    conn.close()

@router.get("/audit/track-record")
def get_track_record():
    """Mengambil riwayat semua sinyal yang tersimpan dari database."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM signals ORDER BY created_at DESC")
    rows = cursor.fetchall()
    
    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "ticker": r["ticker"],
            "entry_price": r["entry_price"],
            "target_price": r["target_price"],
            "stop_loss": r["stop_loss"],
            "probability": r["probability"],
            "status": r["status"],
            "created_at": r["created_at"]
        })
        
    conn.close()
    return {"status": "success", "data": result}

@router.get("/audit/run")
def run_audit():
    """Memeriksa status semua sinyal PENDING menggunakan data yfinance terbaru."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM signals WHERE status = 'PENDING'")
    pending_signals = cursor.fetchall()
    
    updated_count = 0
    
    for sig in pending_signals:
        sig_id = sig["id"]
        ticker = sig["ticker"]
        entry_price = sig["entry_price"]
        target_price = sig["target_price"]
        stop_loss = sig["stop_loss"]
        
        # Parse created_at
        try:
            created_dt = datetime.strptime(sig["created_at"], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            # Fallback jika format datetime berbeda
            created_dt = datetime.now() - timedelta(days=1)
            
        # Kita mulai check harga sejak H+1 dari tanggal pembuatan sinyal
        start_date = (created_dt + timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Tambahkan akhiran .JK jika belum ada untuk yfinance
        yf_ticker = f"{ticker}.JK" if not ticker.endswith(".JK") else ticker
        
        try:
            # Download data historis harian dari start_date sampai sekarang
            df = yf.download(yf_ticker, start=start_date, progress=False)
            
            if df.empty:
                continue
                
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel('Ticker') if 'Ticker' in df.columns.names else df.columns.get_level_values(0)
                
            # Loop melalui baris secara kronologis untuk mendeteksi mana yang kena duluan
            new_status = "PENDING"
            
            for date_idx, row in df.iterrows():
                high = float(row["High"])
                low = float(row["Low"])
                
                is_tp = high >= target_price
                is_sl = low <= stop_loss
                
                if is_tp and is_sl:
                    # Jika keduanya kena pada hari yang sama, anggap LOSS untuk keamanan risiko (conservative)
                    new_status = "LOSS"
                    break
                elif is_tp:
                    new_status = "WIN"
                    break
                elif is_sl:
                    new_status = "LOSS"
                    break
            
            if new_status != "PENDING":
                # Update status di database
                cursor.execute("""
                    UPDATE signals 
                    SET status = ?, updated_at = datetime('now', 'localtime') 
                    WHERE id = ?
                """, (new_status, sig_id))
                updated_count += 1
                
        except Exception as e:
            # Lewati jika terjadi error download per ticker
            print(f"Error auditing {ticker}: {str(e)}")
            continue
            
    conn.commit()
    conn.close()
    
    return {"status": "success", "updated_count": updated_count}
