from fastapi import APIRouter, HTTPException
import json
from pathlib import Path
import sys

# Konfigurasi path untuk absolute import
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.config import CACHE_FILE

router = APIRouter()

@router.get("/recommendations")
def get_recommendations():
    """
    Mengembalikan rekomendasi Top 10 secara instan (< 5ms) dari cache JSON.
    Jika cache belum tersedia, jalankan pipeline scheduler secara otomatis.
    """
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, 'r') as f:
                data = json.load(f)
            return data
        except Exception as e:
            print(f"Gagal membaca cache JSON: {str(e)}")

    # Fallback jika cache belum tersedia
    try:
        from src.scheduler.daily_scheduler import run_daily_after_market_job
        res = run_daily_after_market_job()
        return res
    except Exception as err:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal memproses rekomendasi pasar: {str(err)}"
        )

@router.get("/sync")
def sync_market_data():
    """Endpoint manual untuk memaksa sinkronisasi batch data 300+ saham & kalkulasi rekomendasi baru."""
    try:
        from src.scheduler.daily_scheduler import run_daily_after_market_job
        res = run_daily_after_market_job()
        return {"status": "success", "message": "Sinkronisasi data 300+ saham selesai.", "data": res}
    except Exception as err:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal melakukan sinkronisasi data pasar: {str(err)}"
        )
