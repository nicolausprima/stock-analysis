"""
dashboard/backend/security.py
API authentication (X-API-Key), input validation & output sanitization helpers.
- API_AUTH_TOKEN  : jika diset, semua operasi sensitif (sync, force scan, telegram,
                    audit write) wajib membawa header `X-API-Key` yang cocok.
- validate_ticker : memfilter input user agar hanya simbol saham valid.
- sanitize_text   : escape HTML pada teks hasil LLM/konten eksternal sebelum
                    dikirim ke frontend (frontend me-render via innerHTML).
"""
import hmac
import html
import os
import re

from fastapi import HTTPException, Request


def get_api_auth_token() -> str:
    """Baca token per-request agar rotasi env tanpa restart ikut berlaku.

    Hormati override modul (dipakai test via monkeypatch) bila diset.
    """
    override = globals().get("API_AUTH_TOKEN", "")
    if override:
        return str(override).strip()
    return os.getenv("API_AUTH_TOKEN", "").strip()


def get_app_env() -> str:
    return os.getenv("APP_ENV", os.getenv("ENV", "development")).strip().lower()


# Alias lawas untuk kompatibilitas test (monkeypatch). Jangan dipakai untuk
# konfigurasi produksi — nilai nyata selalu dibaca via get_api_auth_token().
API_AUTH_TOKEN = ""


def is_production() -> bool:
    """True jika berjalan di environment production/cloud."""
    if get_app_env() in ("production", "prod", "staging"):
        return True
    # Deteksi platform PaaS umum: Render, Railway, Fly, Heroku, dll.
    for var in ("RENDER", "RAILWAY_ENVIRONMENT", "FLY_APP_NAME", "HEROKU_APP_NAME", "DYNO"):
        if os.getenv(var):
            return True
    return os.getenv("ENV", "").strip().lower() in ("production", "prod")


def ensure_auth_configured() -> None:
    """Fail-fast saat startup: production wajib punya API_AUTH_TOKEN.

    Raise RuntimeError jika production tanpa token, agar deployment tidak
    berjalan dalam kondisi fail-open.
    """
    if is_production() and not get_api_auth_token():
        raise RuntimeError(
            "API_AUTH_TOKEN belum diset di environment production. "
            "Set API_AUTH_TOKEN untuk mengunci endpoint sensitif, atau set APP_ENV=development untuk lokal."
        )

# Format ticker BEI: 1-6 huruf/angka, opsional suffix .JK (contoh: BBCA, GOTO.JK)
TICKER_RE = re.compile(r"^[A-Z0-9]{1,6}(\.JK)?$")
# Chart juga mengizinkan IHSG (dipetakan ke ^JKSE) dan simbol indeks ^XXXX
CHART_TICKER_RE = re.compile(r"^(IHSG|\^[A-Z0-9]{1,5}|[A-Z0-9]{1,6}(\.JK)?)$")


def is_authorized(request: Request) -> bool:
    """True jika request membawa API key yang valid.

    - Jika API_AUTH_TOKEN diset: wajib header X-API-Key cocok (compare_digest).
    - Jika token kosong dan BUKAN production: True (mode lokal/dev, backward-compat).
    - Jika token kosong dan production: False (fail-closed, tidak pernah terbuka).
    """
    token = get_api_auth_token()
    if not token:
        return not is_production()
    supplied = request.headers.get("X-API-Key", "")
    if not supplied:
        return False
    return hmac.compare_digest(supplied, token)


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


def sanitize_text(text: str, max_length: int = 4000) -> str:
    """Escape HTML entities pada teks tidak terpercaya (output LLM, headline berita).

    Frontend me-render field ini via innerHTML; escape memastikan tag/atribut
    berbahaya hanya tampil sebagai teks biasa, bukan dieksekusi browser.
    """
    if not isinstance(text, str):
        return ""
    return html.escape(text[:max_length])


def sanitize_mapping(data: dict, fields: list[str]) -> dict:
    """Return salinan dict dengan field terpilih yang sudah di-escape."""
    out = dict(data)
    for f in fields:
        if f in out and isinstance(out[f], str):
            out[f] = sanitize_text(out[f])
    return out