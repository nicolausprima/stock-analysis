from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.notifications.telegram_bot import (
    send_telegram_message, 
    get_active_chat_id, 
    send_daily_recommendations_broadcast
)

router = APIRouter()

class TestMessage(BaseModel):
    message: str = "Test notifikasi dari StockAI Screener!"

@router.get("/telegram/status")
def get_telegram_status():
    """Mengecek status koneksi Telegram Bot & Chat ID."""
    chat_id = get_active_chat_id()
    return {
        "status": "success",
        "bot_username": "@StockAnalysisLocalBot",
        "chat_id_detected": bool(chat_id),
        "chat_id": chat_id if chat_id else "Belum terdeteksi (Kirim /start ke bot di Telegram)"
    }

@router.post("/telegram/test")
def send_test_telegram_notification(payload: TestMessage):
    """Mengirim pesan notifikasi pengujian ke Telegram Bot."""
    msg = f"<b>🤖 StockAI Test Notification</b>\n\n{payload.message}"
    result = send_telegram_message(msg)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result

@router.post("/telegram/broadcast-test")
def broadcast_latest_recommendations_telegram():
    """Menguji siaran rekomendasi terbaru ke Telegram Bot."""
    import json
    from src.config import CACHE_FILE
    
    if not CACHE_FILE.exists():
        raise HTTPException(status_code=404, detail="Cache rekomendasi belum tersedia. Jalankan scan pasar terlebih dahulu.")
        
    with open(CACHE_FILE, 'r') as f:
        cache_data = json.load(f)
        
    stocks = cache_data.get("data", [])
    if not stocks:
        raise HTTPException(status_code=400, detail="Tidak ada data rekomendasi saham untuk di-broadcast.")
        
    res = send_daily_recommendations_broadcast(stocks)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
        
    return res
