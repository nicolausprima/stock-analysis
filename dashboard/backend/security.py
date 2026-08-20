"""
dashboard/backend/security.py
API authentication (X-API-Key) & input validation helpers.
- API_AUTH_TOKEN  : jika diset, semua operasi sensitif (sync, force scan, telegram,
                    audit write) wajib membawa header `X-API-Key` yang cocok.
- validate_ticker : memfilter input user agar hanya simbol saham valid.
"""
import os
import re
import hmac
from fastapi import Request, HTTPException

API_AUTH_TOKEN = os.getenv("API_AUTH_TOKEN", "").strip()

# Format ticker BEI: 1-6 huruf/angka, opsional suffix .JK (contoh: BBCA, GOTO.JK)
TICKER_RE = re.compile(r"^[A-Z0-9]{1,6}(\.JK)?$")
# Chart juga mengizinkan IHSG (dipetakan ke ^JKSE) dan simbol indeks ^XXXX
CHART_TICKER_RE = re.compile(r"^(IHSG|\^[A-Z0-9]{1,5}|[A-Z0-9]{1,6}(\.JK)?)$")


def is_authorized(request: Request) -> bool:
    """True jika request membawa API key yang valid (atau auth tidak dikonfigurasi)."""
    if not API_AUTH_TOKEN:
        return True
    supplied = request.headers.get("X-API-Key", "")
    return hmac.compare_digest(supplied, API_AUTH_TOKEN)


def require_api_key(request: Request) -> None:
    """FastAPI dependency / guard untuk endpoint sensitif. Raise 401 jika key tidak valid."""
    if not is_authorized(request):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid API key. Sertakan header 'X-API-Key'.",
        )


def validate_ticker(ticker: str, allow_chart_specials: bool = False) -> str:
    """Validasi & normalisasi ticker. Raise 400 jika format tidak valid."""
    clean = (ticker or "").strip().upper()
    pattern = CHART_TICKER_RE if allow_chart_specials else TICKER_RE
    if not pattern.match(clean):
        raise HTTPException(
            status_code=400,
            detail=f"Format ticker tidak valid: '{ticker}'. Gunakan simbol BEI (mis. BBCA atau BBCA.JK).",
        )
    return clean