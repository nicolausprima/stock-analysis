from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from dashboard.backend.security import validate_ticker
from dashboard.backend.yf_client import get_ticker_news

router = APIRouter()

class NewsRequest(BaseModel):
    ticker: str

@router.post("/news")
def fetch_news(request: NewsRequest):
    ticker = validate_ticker(request.ticker)
    
    try:
        # Ambil berita menggunakan Yahoo Finance (timeout executor, anti-gantung)
        sym = f"{ticker}.JK" if not ticker.endswith(".JK") else ticker
        news_data = get_ticker_news(sym)
        raw_news = "\n".join([f"- {n.get('title')}: {n.get('summary', '')}" for n in news_data[:3]])
        
        if not raw_news.strip():
            raw_news = f"Tidak ada berita signifikan terbaru mengenai {ticker} di Yahoo Finance."
            
        return {
            "status": "success",
            "ticker": ticker,
            "raw_news": raw_news
        }
        
    except Exception as e:
        print(f"[NEWS] Error mengambil berita {ticker}: {e!s}")
        raise HTTPException(status_code=500, detail="Gagal mengambil berita. Silakan coba lagi nanti.")
