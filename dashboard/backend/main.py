import os
import sys
import warnings
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Jalankan scheduler harian & telegram interactive command listener di background thread."""
    req_env = ["TELEGRAM_BOT_TOKEN", "OPENAI_API_BASE"]
    missing = [v for v in req_env if not os.getenv(v)]
    if missing:
        print(f"[WARNING] Environment variables belum diset: {missing}")

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
