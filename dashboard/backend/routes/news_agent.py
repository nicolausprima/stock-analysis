import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import yfinance as yf

from dashboard.backend.security import validate_ticker

router = APIRouter()

class NewsRequest(BaseModel):
    ticker: str

@router.post("/news")
def fetch_news(request: NewsRequest):
    ticker = validate_ticker(request.ticker)
    
    try:
        # Ambil berita menggunakan Yahoo Finance
        yf_ticker = yf.Ticker(f"{ticker}.JK" if not ticker.endswith(".JK") else ticker)
        news_data = yf_ticker.news or []
        raw_news = "\n".join([f"- {n.get('title')}: {n.get('summary', '')}" for n in news_data[:3]])
        
        if not raw_news.strip():
            raw_news = f"Tidak ada berita signifikan terbaru mengenai {ticker} di Yahoo Finance."
            
        return {
            "status": "success",
            "ticker": ticker,
            "raw_news": raw_news
        }
        
    except Exception as e:
        print(f"[NEWS] Error mengambil berita {ticker}: {str(e)}")
        raise HTTPException(status_code=500, detail="Gagal mengambil berita. Silakan coba lagi nanti.")
