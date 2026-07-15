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
from routes.predict import router as predict_router
from routes.chart import router as chart_router

app = FastAPI(title="AI Screener Backend")

# Include routers
app.include_router(predict_router, prefix="/api", tags=["Predict"])
app.include_router(chart_router, prefix="/api", tags=["Chart"])

# Serve static frontend
frontend_dir = PROJECT_ROOT / 'dashboard' / 'frontend'
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
