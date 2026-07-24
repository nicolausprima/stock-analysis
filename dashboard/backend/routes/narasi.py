import os
import json
import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

# Konfigurasi Omniroute
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "http://127.0.0.1:20128/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Jika berjalan di luar Docker (host OS), ganti host.docker.internal dengan 127.0.0.1
if "host.docker.internal" in OPENAI_API_BASE and not os.path.exists('/.dockerenv'):
    OPENAI_API_BASE = OPENAI_API_BASE.replace("host.docker.internal", "127.0.0.1")

class NarasiRequest(BaseModel):
    ticker: str
    close_price: float
    target_price: float
    stop_loss: float
    rsi: float
    macd_signal: str
    trend: str
    probability: float
    sentiment_status: str = "NETRAL"
    sentiment_impact: str = "NETRAL"

def parse_and_clean_response(text: str) -> str:
    """Parse SSE streaming response dari Omniroute (data: {...} chunks)."""
    content_parts = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data: ") and not line.startswith("data: [DONE]"):
            try:
                chunk = json.loads(line[6:])
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                if "content" in delta:
                    content_parts.append(delta["content"])
            except json.JSONDecodeError:
                continue
    return "".join(content_parts).strip()

@router.post("/narasi")
def generate_narrative(req: NarasiRequest):
    """Menghasilkan ulasan opini analisis teknikal & sentimen berita terpadu menggunakan model AI."""
    url = f"{OPENAI_API_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    ticker_clean = req.ticker.replace(".JK", "")
    
    prompt = f"""
Kamu adalah analis finansial pasar saham Indonesia (BEI).
Berikan analisis terpadu (teknikal & sentimen berita) mengapa saham {ticker_clean} masuk rekomendasi beli berdasarkan data:
- Harga Sekarang: Rp {req.close_price:.0f}
- Target: Rp {req.target_price:.0f}
- Stop Loss: Rp {req.stop_loss:.0f}
- RSI: {req.rsi:.1f}
- MACD: {req.macd_signal}
- Tren: {req.trend}
- Sentimen Berita: {req.sentiment_status} ({req.sentiment_impact})
- Skor Probabilitas AI Final: {req.probability:.1f}%

Berikan ulasan terpadu dalam 2-3 kalimat singkat berbahasa Indonesia yang sangat padat, profesional, dan meyakinkan. Sorot gabungan indikator teknikal dan dampak sentimen beritanya. Jangan tambahkan kata pembuka atau penutup.
"""

    payload = {
        "model": "opencode/deepseek-v4-flash-free",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=120)
        if response.status_code == 200:
            narrative = parse_and_clean_response(response.text)
            return {"status": "success", "narasi": narrative}
            
        # Jika gagal (misal docker network mapping mismatch), coba fallback ke localhost url
        if "host.docker.internal" in OPENAI_API_BASE:
            fallback_url = url.replace("host.docker.internal", "127.0.0.1")
            response = requests.post(fallback_url, json=payload, headers=headers, timeout=120)
            if response.status_code == 200:
                narrative = parse_and_clean_response(response.text)
                return {"status": "success", "narasi": narrative}
                
        raise HTTPException(
            status_code=500, 
            detail=f"Error dari API Omniroute (status {response.status_code})"
        )
        
    except Exception as e:
        # Cobalah fallback ke localhost jika terjadi error koneksi
        if "host.docker.internal" in OPENAI_API_BASE:
            try:
                fallback_url = url.replace("host.docker.internal", "127.0.0.1")
                response = requests.post(fallback_url, json=payload, headers=headers, timeout=120)
                if response.status_code == 200:
                    narrative = parse_and_clean_response(response.text)
                    return {"status": "success", "narasi": narrative}
            except:
                pass
        raise HTTPException(
            status_code=500, 
            detail=f"Gagal menghubungi model AI lokal: {str(e)}"
        )

@router.post("/narasi/multi-agent")
def generate_multi_agent_consensus(req: NarasiRequest):
    """Menghasilkan konsensus analisis multi-agent (Technical, Sentiment, Macro, Bull vs Bear, Risk Manager)."""
    try:
        from src.agents.multi_agent_system import MultiAgentSystem
        from src.config import CACHE_FILE
        macro_info = None
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, 'r') as f:
                    c_data = json.load(f)
                    macro_info = c_data.get("macro_eval")
            except Exception:
                pass
        agent_system = MultiAgentSystem()
        consensus = agent_system.generate_consensus(req.dict(), macro_info=macro_info)
        return {"status": "success", "data": consensus}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal menjalankan sistem Multi-Agent: {str(e)}"
        )

