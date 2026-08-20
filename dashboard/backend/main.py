import os
import sys
import time
import threading
import warnings
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Filter warning noise in logs
warnings.filterwarnings("ignore")

# Konfigurasi path untuk absolute import
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# Import routers
from dashboard.backend.routes.predict import router as predict_router
from dashboard.backend.routes.chart import router as chart_router
from dashboard.backend.routes.news_agent import router as news_router
from dashboard.backend.routes.audit import router as audit_router
from dashboard.backend.routes.narasi import router as narasi_router
from dashboard.backend.routes.telegram import router as telegram_router


# --- Rate limiting sederhana per-IP untuk semua endpoint /api (anti DoS) ---
RATE_LIMIT_PER_MINUTE = 120
RATE_BUCKET_MAX_IPS = 10000
_rate_buckets = {}
_rate_lock = threading.Lock()


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path.startswith("/api/"):
            ip = request.client.host if request.client else "unknown"
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
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Jalankan scheduler harian & telegram interactive command listener di background thread."""
    req_env = ["TELEGRAM_BOT_TOKEN", "OPENAI_API_BASE"]
    missing = [v for v in req_env if not os.getenv(v)]
    if missing:
        print(f"[WARNING] Environment variables belum diset: {missing}")

    if not os.getenv("API_AUTH_TOKEN"):
        print("[WARNING] API_AUTH_TOKEN belum diset. Endpoint sensitif (sync, telegram, audit write) TERBUKA tanpa autentikasi!")

    if os.getenv("TESTING") == "true" or "pytest" in sys.modules:
        print("[INFO] Mode testing terdeteksi. Background thread dilewati.")
    else:
        try:
            from src.scheduler.daily_scheduler import start_background_scheduler
            from src.notifications.telegram_bot import start_telegram_bot_listener
            start_background_scheduler()
            start_telegram_bot_listener()
            print("[SUCCESS] Scheduler harian & Telegram Interactive Listener berhasil diaktifkan.")
        except Exception as e:
            print(f"[ERROR] Gagal memulai background services: {str(e)}")
    yield


app = FastAPI(title="AI Screener Backend", lifespan=lifespan)
app.add_middleware(RateLimitMiddleware)

# Include routers
app.include_router(predict_router, prefix="/api", tags=["Predict"])
app.include_router(chart_router, prefix="/api", tags=["Chart"])
app.include_router(news_router, prefix="/api", tags=["News"])
app.include_router(audit_router, prefix="/api", tags=["Audit"])
app.include_router(narasi_router, prefix="/api", tags=["Narasi"])
app.include_router(telegram_router, prefix="/api", tags=["Telegram"])


# Serve static frontend
frontend_dir = PROJECT_ROOT / 'dashboard' / 'frontend'
if frontend_dir.exists():
    @app.get("/dashboard")
    async def serve_dashboard():
        return FileResponse(str(frontend_dir / "dashboard.html"))
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
