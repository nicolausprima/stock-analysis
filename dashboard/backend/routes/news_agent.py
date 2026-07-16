import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import yfinance as yf

router = APIRouter()

class NewsRequest(BaseModel):
    ticker: str

@router.post("/news")
def fetch_news(request: NewsRequest):
    ticker = request.ticker
    
    try:
        # Ambil berita menggunakan Yahoo Finance
        yf_ticker = yf.Ticker(f"{ticker}.JK" if not ticker.endswith(".JK") else ticker)
        news_data = yf_ticker.news
        raw_news = "\n".join([f"- {n.get('title')}: {n.get('summary', '')}" for n in news_data[:3]])
        
        if not raw_news.strip():
            raw_news = f"Tidak ada berita signifikan terbaru mengenai {ticker} di Yahoo Finance."
            
        return {
            "status": "success",
            "ticker": ticker,
            "raw_news": raw_news
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
