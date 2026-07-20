import os
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

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

app = FastAPI(title="AI Screener Backend")

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
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

@app.on_event("startup")
def startup_event():
    """Jalankan scheduler harian 16:05 WIB di background thread."""
    if os.getenv("TESTING") == "true" or "pytest" in sys.modules:
        print("[INFO] Mode testing terdeteksi. Background scheduler dilewati.")
        return
    try:
        from src.scheduler.daily_scheduler import start_background_scheduler
        start_background_scheduler()
        print("[SUCCESS] Scheduler harian (16:05 WIB) berhasil diaktifkan di background thread.")
    except Exception as e:
        print(f"[ERROR] Gagal memulai scheduler: {str(e)}")

