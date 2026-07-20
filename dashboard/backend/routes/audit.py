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

@router.get("/audit/recap")
def get_audit_recap():
    """
    Mengambil statistik rekapitulasi performa audit:
    - Ringkasan Win Rate, Total Win/Loss, Kumulatif Profit %
    - Breakdown performa per bulan
    - Data kurva ekuitas kumulatif (Equity Curve Chart)
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM signals ORDER BY created_at ASC")
    rows = cursor.fetchall()
    conn.close()

    total_signals = len(rows)
    win_count = sum(1 for r in rows if r["status"] == "WIN")
    loss_count = sum(1 for r in rows if r["status"] == "LOSS")
    pending_count = sum(1 for r in rows if r["status"] == "PENDING")

    decided = win_count + loss_count
    win_rate = round((win_count / decided * 100), 1) if decided > 0 else 0.0
    total_profit_pct = round((win_count * 3.0) - (loss_count * 1.5), 1)

    # Monthly Grouping
    MONTH_NAMES = {
        "01": "Januari", "02": "Februari", "03": "Maret", "04": "April",
        "05": "Mei", "06": "Juni", "07": "Juli", "08": "Agustus",
        "09": "September", "10": "Oktober", "11": "November", "12": "Desember"
    }

    monthly_dict = {}
    cum_return = 0.0
    equity_curve = []

    for r in rows:
        created_str = str(r["created_at"])
        date_part = created_str.split(" ")[0] if " " in created_str else created_str
        month_key = date_part[:7] if len(date_part) >= 7 else "Unknown"

        if month_key not in monthly_dict:
            year, m_num = month_key.split("-") if "-" in month_key else ("2026", "01")
            m_name = f"{MONTH_NAMES.get(m_num, m_num)} {year}"
            monthly_dict[month_key] = {
                "month_key": month_key,
                "month_name": m_name,
                "total_signals": 0,
                "win_count": 0,
                "loss_count": 0,
                "pending_count": 0,
                "monthly_profit_pct": 0.0
            }

        m_data = monthly_dict[month_key]
        m_data["total_signals"] += 1
        st = r["status"]

        if st == "WIN":
            m_data["win_count"] += 1
            m_data["monthly_profit_pct"] += 3.0
            cum_return += 3.0
        elif st == "LOSS":
            m_data["loss_count"] += 1
            m_data["monthly_profit_pct"] -= 1.5
            cum_return -= 1.5
        else:
            m_data["pending_count"] += 1

        m_data["monthly_profit_pct"] = round(m_data["monthly_profit_pct"], 1)

        # Track cumulative return per unique date for LightweightCharts
        if st in ["WIN", "LOSS"]:
            equity_curve.append({
                "time": date_part,
                "value": round(cum_return, 1)
            })

    # Deduplicate equity curve by unique date (keep latest cumulative return per day)
    daily_equity_dict = {}
    for pt in equity_curve:
        daily_equity_dict[pt["time"]] = pt["value"]

    clean_equity_curve = [
        {"time": dt, "value": val}
        for dt, val in sorted(daily_equity_dict.items())
    ]

    monthly_breakdown = []
    for k in sorted(monthly_dict.keys(), reverse=True):
        m = monthly_dict[k]
        m_decided = m["win_count"] + m["loss_count"]
        m["win_rate"] = round((m["win_count"] / m_decided * 100), 1) if m_decided > 0 else 0.0
        monthly_breakdown.append(m)

    return {
        "status": "success",
        "summary": {
            "total_signals": total_signals,
            "win_count": win_count,
            "loss_count": loss_count,
            "pending_count": pending_count,
            "win_rate": win_rate,
            "total_profit_pct": total_profit_pct
        },
        "monthly_breakdown": monthly_breakdown,
        "equity_curve": clean_equity_curve
    }


@router.get("/audit/seed-simulation")
def seed_simulation_audit():
    """
    Menghasilkan data simulasi historis sinyal audit selama 6 bulan terakhir (Februari - Juli 2026).
    Memungkinkan visualisasi instan untuk Grafik Kurva Ekuitas dan Rekapitulasi Performa Bulanan.
    """
    import random

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Hapus data simulasi lama jika ingin bersih
    cursor.execute("DELETE FROM signals")

    sample_stocks = [
        ("BBCA", 9800), ("BBRI", 5400), ("BMRI", 6800), ("BBNI", 5200),
        ("TLKM", 3850), ("ASII", 5150), ("AMMN", 11200), ("PTBA", 2650),
        ("ADRO", 2720), ("MEDC", 1350), ("BRIS", 2450), ("PGAS", 1550),
        ("KLBF", 1480), ("UNVR", 2850), ("ICBP", 10900), ("GOTO", 84)
    ]

    # Generate sinyal harian dari 2026-02-01 sampai 2026-07-20
    start_dt = datetime(2026, 2, 1)
    end_dt = datetime(2026, 7, 20)
    current = start_dt

    random.seed(42) # Seed tetap agar konsisten
    simulated_records = []

    while current <= end_dt:
        # Hanya hari kerja bursa (Senin-Jumat)
        if current.weekday() < 5:
            # 1-3 sinyal per hari bursa
            num_signals = random.choice([1, 2, 2, 3])
            daily_tickers = random.sample(sample_stocks, k=num_signals)

            for ticker, base_price in daily_tickers:
                variance = random.uniform(-0.05, 0.05)
                entry_p = round(base_price * (1 + variance))
                target_p = round(entry_p * 1.03)
                stop_p = round(entry_p * 0.985)
                prob = round(random.uniform(62.0, 79.5), 1)

                # Probabilitas win ~74%
                status = "WIN" if random.random() < 0.74 else "LOSS"
                date_str = current.strftime("%Y-%m-%d 16:05:00")

                simulated_records.append((ticker, entry_p, target_p, stop_p, prob, status, date_str, date_str))

        current += timedelta(days=1)

    cursor.executemany("""
        INSERT INTO signals (ticker, entry_price, target_price, stop_loss, probability, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, simulated_records)

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "message": f"Berhasil membuat {len(simulated_records)} sinyal simulasi historis 6 bulan terakhir!"
    }

