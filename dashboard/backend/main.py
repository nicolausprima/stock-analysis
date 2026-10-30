import os
import sys
import threading
import time
import warnings
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware

# Hanya redam warning noisy pihak ketiga; jangan sembunyikan warning data/model sendiri.
warnings.filterwarnings("ignore", category=FutureWarning, module=r"yfinance.*")
warnings.filterwarnings("ignore", category=UserWarning, module=r"urllib3.*")
warnings.filterwarnings("ignore", message=r".*XGBoost.*")

# Konfigurasi path untuk absolute import
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# Import routers
from dashboard.backend.routes.audit import router as audit_router
from dashboard.backend.routes.chart import router as chart_router
from dashboard.backend.routes.narasi import router as narasi_router
from dashboard.backend.routes.news_agent import router as news_router
from dashboard.backend.routes.predict import router as predict_router
from dashboard.backend.routes.telegram import router as telegram_router

# --- Rate limiting sederhana per-IP untuk semua endpoint /api (anti DoS) ---
RATE_LIMIT_PER_MINUTE = 120
RATE_BUCKET_MAX_IPS = 10000
_rate_buckets = {}
_rate_lock = threading.Lock()

# Di belakang reverse proxy (Render/nginx/Cloudflare) request.client.host adalah
# IP proxy, sehingga SEMUA pengguna berbagi satu bucket (audit 2026-10-30, B-03).
# Header klien hanya dipercaya bila TRUST_PROXY_HEADERS=true, atau otomatis saat
# terdeteksi berjalan di platform PaaS yang memang selalu menaruh proxy di depan.
_PAAS_MARKERS = ("RENDER", "RAILWAY_ENVIRONMENT", "FLY_APP_NAME", "HEROKU_APP_NAME")


def _trust_proxy_headers() -> bool:
    raw = os.getenv("TRUST_PROXY_HEADERS")
    if raw is not None:
        return raw.strip().lower() in ("1", "true", "yes", "on")
    return any(os.getenv(var) for var in _PAAS_MARKERS)


def client_ip(request) -> str:
    """Identitas klien untuk rate limit: IP nyata bila di belakang proxy tepercaya."""
    if _trust_proxy_headers():
        for header in ("cf-connecting-ip", "x-real-ip"):
            value = (request.headers.get(header) or "").strip()
            if value:
                return value
        forwarded = request.headers.get("x-forwarded-for") or ""
        hops = [part.strip() for part in forwarded.split(",") if part.strip()]
        if hops:
            # Hop terakhir ditambahkan proxy kita sendiri; entri di kirinya bisa
            # dipalsukan klien sehingga tidak dipakai sebagai kunci bucket.
            return hops[-1]
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path.startswith("/api/"):
            ip = client_ip(request)
            now = time.time()
            with _rate_lock:
                bucket = [t for t in _rate_buckets.get(ip, []) if now - t < 60]
                if len(bucket) >= RATE_LIMIT_PER_MINUTE:
                    return JSONResponse(
                        {"status": "error", "detail": "Rate limit exceeded. Coba lagi nanti."},
                        status_code=429,
                    )
                bucket.append(now)
                _rate_buckets[ip] = bucket
                if len(_rate_buckets) > RATE_BUCKET_MAX_IPS:
                    oldest_ips = sorted(_rate_buckets, key=lambda k: _rate_buckets[k][-1])[:len(_rate_buckets) // 2]
                    for old_ip in oldest_ips:
                        _rate_buckets.pop(old_ip, None)
            # Lapisan kedua: batas ketat untuk endpoint mahal (LLM/scan/broadcast).
            try:
                from dashboard.backend.rate_limit import check_expensive_limit
                query = str(request.url.query or "")
                allowed, retry = check_expensive_limit(ip, request.url.path, query)
                if not allowed:
                    return JSONResponse(
                        {"status": "error", "detail": f"Rate limit endpoint mahal. Coba lagi dalam {retry}s."},
                        status_code=429,
                        headers={"Retry-After": str(retry)},
                    )
            except Exception:
                pass
        return await call_next(request)


class CacheHeadersMiddleware(BaseHTTPMiddleware):
    """Kebijakan cache eksplisit per kelas path (audit 2026-10-30, C-04/C-05).

    Tanpa header ini browser memakai heuristic caching: HTML lama bisa dipakai
    berhari-hari sementara API sudah mengembalikan data baru. Aturannya:

    - ``/api/*``           -> ``no-store`` (data pasar berubah; jangan pernah
      disajikan dari cache tanpa validasi).
    - halaman HTML         -> ``no-cache, must-revalidate`` (selalu validasi,
      ETag membuat revalidasi murah 304).
    - CSS/JS               -> ``no-cache`` dan TANPA query ``?v=`` manual, jadi
      versi aset tidak bisa lagi tidak sinkron antar file.
    - gambar/font          -> ``public, max-age=86400``.
    """

    _IMMUTABLE_EXT = (".png", ".jpg", ".jpeg", ".svg", ".webp", ".ico", ".woff", ".woff2")

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if "cache-control" in response.headers:
            return response
        path = request.url.path or "/"
        if path.startswith("/api/") or path == "/api":
            response.headers["Cache-Control"] = "no-store"
        elif path.endswith(self._IMMUTABLE_EXT):
            response.headers["Cache-Control"] = "public, max-age=86400"
        elif path == "/" or path == "/dashboard" or path.endswith(("/", ".html")):
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        elif path.endswith((".css", ".js", ".json")):
            response.headers["Cache-Control"] = "no-cache"
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Tambahkan security headers ke semua response (halaman statis & API).

    Catatan CSP: 'unsafe-inline' untuk script/style masih diperlukan karena
    index.html & dashboard.html memakai blok <script>/<style> inline.
    """
    CSP_POLICY = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    )

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Content-Security-Policy", self.CSP_POLICY)
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan web API saja. Scheduler/Telegram worker dipisah via ENV opt-in.

    - Fail-fast auth: production tanpa API_AUTH_TOKEN -> RuntimeError (fail-closed).
    - Scheduler & Telegram listener TIDAK jalan otomatis di web process.
      Aktifkan eksplisit hanya di worker khusus:
        ENABLE_SCHEDULER=true  -> start_background_scheduler()
        ENABLE_TELEGRAM_LISTENER=true -> start_telegram_bot_listener()
      Ini mencegah multi-replica menjalankan job/polling berkali-kali.
    """
    from dashboard.backend.security import ensure_auth_configured

    try:
        ensure_auth_configured()
    except RuntimeError as e:
        print(f"[FATAL] {e}")
        raise

    req_env = ["TELEGRAM_BOT_TOKEN", "OPENAI_API_BASE"]
    missing = [v for v in req_env if not os.getenv(v)]
    if missing:
        print(f"[WARNING] Environment variables belum diset: {missing}")

    if not os.getenv("API_AUTH_TOKEN"):
        print("[WARNING] API_AUTH_TOKEN belum diset. Mode lokal/dev: endpoint sensitif TERBUKA. Jangan deploy publik tanpa token.")

    if os.getenv("TESTING") == "true" or "pytest" in sys.modules:
        print("[INFO] Mode testing terdeteksi. Background thread dilewati.")
    else:
        enable_sched = os.getenv("ENABLE_SCHEDULER", "false").strip().lower() == "true"
        enable_tg = os.getenv("ENABLE_TELEGRAM_LISTENER", "false").strip().lower() == "true"
        if enable_sched or enable_tg:
            try:
                if enable_sched:
                    from src.scheduler.daily_scheduler import start_background_scheduler
                    start_background_scheduler()
                    print("[SUCCESS] Scheduler harian diaktifkan (dedicated worker).")
                if enable_tg:
                    from src.notifications.telegram_bot import (
                        start_telegram_bot_listener,
                    )
                    start_telegram_bot_listener()
                    print("[SUCCESS] Telegram Interactive Listener diaktifkan (dedicated worker).")
            except Exception as e:
                print(f"[ERROR] Gagal memulai background services: {e!s}")
        else:
            print("[INFO] Background scheduler/telegram nonaktif di web process. Jalankan worker terpisah bila perlu.")
    yield


app = FastAPI(title="AI Screener Backend", lifespan=lifespan)
# Kompresi response besar (payload rekomendasi + chart) hemat bandwidth (audit B-09).
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(RateLimitMiddleware)
# Didaftarkan setelah rate limit -> menjadi middleware paling luar,
# sehingga header keamanan tetap menempel pada response 429 rate limiter.
app.add_middleware(SecurityHeadersMiddleware)
# Paling luar: header cache juga menempel pada response 429/500.
app.add_middleware(CacheHeadersMiddleware)

# Include routers
app.include_router(predict_router, prefix="/api", tags=["Predict"])
app.include_router(chart_router, prefix="/api", tags=["Chart"])
app.include_router(news_router, prefix="/api", tags=["News"])
app.include_router(audit_router, prefix="/api", tags=["Audit"])
app.include_router(narasi_router, prefix="/api", tags=["Narasi"])
app.include_router(telegram_router, prefix="/api", tags=["Telegram"])


@app.get("/healthz")
async def healthz():
    """Liveness murni: tidak menyentuh DB, model, atau jaringan (audit B-10)."""
    return {"status": "ok"}


# Serve static frontend
frontend_dir = PROJECT_ROOT / 'dashboard' / 'frontend'
if frontend_dir.exists():
    @app.get("/dashboard")
    async def serve_dashboard():
        return FileResponse(str(frontend_dir / "dashboard.html"))
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
