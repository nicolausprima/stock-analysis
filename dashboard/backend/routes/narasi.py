import json
import os
import re

import requests
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, field_validator

from dashboard.backend.security import (
    require_api_key,
    sanitize_mapping,
    sanitize_text,
    validate_ticker,
)

DISCLAIMER_F4 = (
    "Konten ini riset kuantitatif untuk edukasi — BUKAN nasihat/rekomendasi investasi. "
    "Saham berisiko rugi. Kinerja masa lalu tidak menjamin hasil. "
    "Keputusan & risiko milik Anda (DYOR)."
)
RISK_SENTENCE = (
    "Ingat: setiap keputusan beli/jual mengandung risiko rugi dan "
    "kinerja masa lalu tidak menjamin hasil di masa depan."
)

_SAFE_STR_RE = re.compile(r"^[A-Za-z0-9 .+()%/-]{1,60}$")

load_dotenv()

router = APIRouter()

def format_idr(value: float) -> str:
    """Format angka gaya Indonesia (IDR): pemisah ribuan titik, mis. 10250 -> '10.250'.

    Menggantikan format spec ':,.0f' gaya US (koma) yang salah konteks untuk
    narasi BEI berbahasa Indonesia (Rp 10,250 -> Rp 10.250).
    """
    return f"{round(value):,}".replace(",", ".")

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

    @field_validator("ticker")
    @classmethod
    def _valid_ticker(cls, v: str) -> str:
        return validate_ticker(v)

    @field_validator("rsi")
    @classmethod
    def _clamp_rsi(cls, v: float) -> float:
        try:
            f = float(v)
        except (TypeError, ValueError):
            raise ValueError("RSI harus angka 0-100")
        if not 0 <= f <= 100:
            raise ValueError("RSI harus 0-100")
        return f

    @field_validator("probability")
    @classmethod
    def _clamp_prob(cls, v: float) -> float:
        try:
            f = float(v)
        except (TypeError, ValueError):
            raise ValueError("probability harus angka 0-1 atau 0-100")
        # Terima 0-1 (fraksi) atau 0-100 (persen), normalisasi ke persen.
        if 0 <= f <= 1:
            return f * 100
        if 0 <= f <= 100:
            return f
        raise ValueError("probability harus 0-1 atau 0-100")

    @field_validator("close_price", "target_price", "stop_loss")
    @classmethod
    def _positive_price(cls, v: float) -> float:
        if float(v) <= 0:
            raise ValueError("harga harus > 0")
        return float(v)

    @field_validator("macd_signal", "trend", "sentiment_status", "sentiment_impact")
    @classmethod
    def _safe_free_string(cls, v: str) -> str:
        s = (v or "")[:60]
        if not _SAFE_STR_RE.match(s):
            raise ValueError("field string mengandung karakter tidak diizinkan")
        return s

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
def generate_narrative(request: Request, req: NarasiRequest):
    """Menghasilkan ulasan opini analisis teknikal & sentimen berita terpadu menggunakan model AI.

    [AUTH] Endpoint ini memanggil proxy LLM (berbiaya) -> wajib API key jika diset.
    Response selalu transparan: {"source": "llm"|"fallback-quantitative", ...}
    """
    require_api_key(request)
    from dashboard.backend.rate_limit import LLM_SEMAPHORE
    if not LLM_SEMAPHORE.acquire(blocking=False):
        from fastapi import HTTPException as _H
        raise _H(status_code=429, detail="LLM sibuk (2 concurrent max). Coba lagi nanti.")
    url = f"{OPENAI_API_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    ticker_clean = validate_ticker(req.ticker).replace(".JK", "")
    
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

Berikan ulasan terpadu dalam 2-3 kalimat singkat berbahasa Indonesia yang sangat padat dan profesional. Sorot gabungan indikator teknikal dan dampak sentimen beritanya. {RISK_SENTENCE}
Jangan tambahkan kata pembuka atau penutup.
"""

    payload = {
        "model": "opencode/deepseek-v4-flash-free",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=120)
        if response.status_code == 200:
            narrative = sanitize_text(parse_and_clean_response(response.text))
            narrative = f"{narrative}\n\n{DISCLAIMER_F4}"
            return {"status": "success", "narasi": narrative, "source": "llm", "is_sample": False, "stale": False, "disclaimer": DISCLAIMER_F4}

        # Jika gagal (misal docker network mapping mismatch), coba fallback ke localhost url
        if "host.docker.internal" in OPENAI_API_BASE:
            fallback_url = url.replace("host.docker.internal", "127.0.0.1")
            response = requests.post(fallback_url, json=payload, headers=headers, timeout=120)
            if response.status_code == 200:
                narrative = sanitize_text(parse_and_clean_response(response.text))
                narrative = f"{narrative}\n\n{DISCLAIMER_F4}"
                return {"status": "success", "narasi": narrative, "source": "llm", "is_sample": False, "stale": False, "disclaimer": DISCLAIMER_F4}

        rsi_label = "Oversold" if req.rsi < 40 else ("Overbought" if req.rsi > 70 else "Netral")
        tp_pct = ((req.target_price - req.close_price) / req.close_price * 100) if req.close_price > 0 else 3.0
        sl_pct = ((req.stop_loss - req.close_price) / req.close_price * 100) if req.close_price > 0 else -1.5
        ticker_clean = validate_ticker(req.ticker).replace(".JK", "")
        fallback_narrative = (
            f"Saham {ticker_clean} menunjukkan momentum positif dengan RSI {req.rsi:.1f} ({rsi_label}) "
            f"dan indikator MACD {req.macd_signal} pada tren {req.trend}. "
            f"Target profit ditetapkan pada Rp {req.target_price:,.0f} (+{tp_pct:.1f}%) dan Stop Loss pada Rp {req.stop_loss:,.0f} ({sl_pct:.1f}%)."
            f"\n\n{DISCLAIMER_F4}"
        )
        return {"status": "success", "narasi": fallback_narrative, "source": "fallback-quantitative",
                "is_sample": False, "stale": False, "fallback_reason": "llm-proxy-unreachable", "disclaimer": DISCLAIMER_F4}

    except Exception:
        # Cobalah fallback ke localhost jika terjadi error koneksi
        if "host.docker.internal" in OPENAI_API_BASE:
            try:
                fallback_url = url.replace("host.docker.internal", "127.0.0.1")
                response = requests.post(fallback_url, json=payload, headers=headers, timeout=120)
                if response.status_code == 200:
                    narrative = sanitize_text(parse_and_clean_response(response.text))
                    return {"status": "success", "narasi": narrative, "source": "llm", "is_sample": False, "stale": False}
            except Exception:  # network/proxy down -> fallback narasi kuantitatif
                pass

        # Graceful fallback: Jika LLM proxy tidak dapat dijangkau (misal pada cloud deployment Render),
        # kembalikan narasi analisis kuantitatif terstruktur yang bersih tanpa error.
        rsi_label = "Oversold" if req.rsi < 40 else ("Overbought" if req.rsi > 70 else "Netral")
        tp_pct = ((req.target_price - req.close_price) / req.close_price * 100) if req.close_price > 0 else 3.0
        sl_pct = ((req.stop_loss - req.close_price) / req.close_price * 100) if req.close_price > 0 else -1.5
        ticker_clean = validate_ticker(req.ticker).replace(".JK", "")
        fallback_narrative = (
            f"Saham {ticker_clean} menunjukkan momentum positif dengan RSI {req.rsi:.1f} ({rsi_label}) "
            f"dan indikator MACD {req.macd_signal} pada tren {req.trend}. "
            f"Target profit ditetapkan pada Rp {req.target_price:,.0f} (+{tp_pct:.1f}%) dan Stop Loss pada Rp {req.stop_loss:,.0f} ({sl_pct:.1f}%)."
            f"\n\n{DISCLAIMER_F4}"
        )
        return {"status": "success", "narasi": fallback_narrative, "source": "fallback-quantitative",
                "is_sample": False, "stale": False, "fallback_reason": "llm-error", "disclaimer": DISCLAIMER_F4}
    finally:
        try:
            from dashboard.backend.rate_limit import LLM_SEMAPHORE as _sem
            _sem.release()
        except Exception:
            pass

@router.post("/narasi/multi-agent")
def generate_multi_agent_consensus(request: Request, req: NarasiRequest):
    """Menghasilkan konsensus analisis multi-agent (Technical, Sentiment, Macro, Bull vs Bear, Risk Manager).

    [AUTH] Endpoint ini memanggil proxy LLM (berbiaya) -> wajib API key jika diset.
    """
    require_api_key(request)
    try:
        req_dict = req.dict()
        req_dict["ticker"] = validate_ticker(req.ticker)
        from src.agents.multi_agent_v2 import MultiAgentSystemV2
        from src.config import CACHE_FILE
        macro_info = None
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, 'r') as f:
                    c_data = json.load(f)
                    macro_info = c_data.get("macro_eval")
            except Exception:
                pass
        agent_system = MultiAgentSystemV2()
        consensus = agent_system.generate_consensus(req_dict, macro_info=macro_info)
        # Output agent mengandung teks turunan headline berita (konten eksternal)
        # -> escape SEMUA field string sebelum dirender frontend.
        if isinstance(consensus, dict):
            str_fields = [k for k, v in consensus.items() if isinstance(v, str)]
            consensus = sanitize_mapping(consensus, str_fields)
        return {"status": "success", "data": consensus, "source": "multi-agent-v2"}
    except Exception as e:
        print(f"[NARASI] Gagal menjalankan sistem Multi-Agent: {e!s}")
        raise HTTPException(
            status_code=500,
            detail="Gagal menjalankan sistem Multi-Agent. Silakan coba lagi nanti."
        )

