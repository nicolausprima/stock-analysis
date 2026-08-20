import os
import sys
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

os.environ["TESTING"] = "true"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.config import CACHE_FILE, DATA_DIR
from dashboard.backend.main import app

client = TestClient(app)



@pytest.fixture(autouse=True)
def prepare_test_environment():
    """Memastikan folder data, DB schema, dan cache file rekomendasi selalu terisi dengan data valid sebelum testing."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    from dashboard.backend.routes.audit import init_db
    init_db()
    
    dummy_cache = {
        "status": "success",
        "timestamp": "2026-07-20 16:05:00",
        "total_scanned": 300,
        "data": [
            {
                "ticker": "BBCA.JK",
                "sector": "Finansial",
                "is_leading_sector": True,
                "probability": 78.5,
                "signal": 1,
                "close_price": 6475,
                "target_price": 6669,
                "stop_loss": 6378,
                "rsi": 55,
                "rsi_signal": "NETRAL",
                "macd_signal": "BULLISH",
                "trend": "UPTREND",
                "adx": 28.0,
                "rvol": 1.45,
                "risk_reward_ratio": 2.0,
                "kelly_allocation": 15.0,
                "reason": "MACD Golden Cross, Volume Melonjak 1.5x (RVOL Breakout)",
                "sentiment_status": "POSITIF",
                "sentiment_impact": "BOOSTER (+3%)"
            }
        ]
    }
    with open(CACHE_FILE, "w") as f:
        json.dump(dummy_cache, f, indent=2)


def test_api_recommendations_endpoint():
    response = client.get("/api/recommendations")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data.get("status") == "success"
    assert "data" in json_data
    assert len(json_data["data"]) > 0

def test_api_chart_endpoint():
    response = client.get("/api/chart/IHSG?days=1")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data.get("status") == "success"

def test_api_audit_recap_endpoint():
    response = client.get("/api/audit/recap")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data.get("status") == "success"
    assert "summary" in json_data
    assert "monthly_breakdown" in json_data
    assert "equity_curve" in json_data

def test_api_audit_track_record_endpoint():
    response = client.get("/api/audit/track-record")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data.get("status") == "success"
    assert "data" in json_data

def test_api_telegram_status_endpoint():
    response = client.get("/api/telegram/status")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data.get("status") == "success"
    assert "bot_username" in json_data

def test_api_telegram_status_does_not_leak_chat_id():
    response = client.get("/api/telegram/status")
    json_data = response.json()
    assert "chat_id" not in json_data

def test_api_sync_requires_api_key(monkeypatch):
    import dashboard.backend.security as security
    monkeypatch.setattr(security, "API_AUTH_TOKEN", "test-secret-key")

    # Tanpa key -> 401
    assert client.get("/api/sync").status_code == 401
    # Key salah -> 401
    assert client.get("/api/sync", headers={"X-API-Key": "wrong"}).status_code == 401
    # Key benar -> lolos ke handler (di-mock agar tidak menjalankan scheduler asli)
    import src.scheduler.daily_scheduler as scheduler
    monkeypatch.setattr(scheduler, "run_daily_after_market_job", lambda *a, **k: {"status": "success"})
    res = client.get("/api/sync", headers={"X-API-Key": "test-secret-key"})
    assert res.status_code == 200
    assert res.json().get("status") == "success"

def test_api_recommendations_force_requires_api_key(monkeypatch):
    import dashboard.backend.security as security
    monkeypatch.setattr(security, "API_AUTH_TOKEN", "test-secret-key")

    # Tanpa key -> 401
    assert client.get("/api/recommendations", params={"force": "true"}).status_code == 401
    # Key benar -> lolos (fallback response karena TESTING mode)
    res = client.get("/api/recommendations", params={"force": "true"}, headers={"X-API-Key": "test-secret-key"})
    assert res.status_code == 200

def test_api_telegram_broadcast_requires_api_key(monkeypatch):
    import dashboard.backend.security as security
    monkeypatch.setattr(security, "API_AUTH_TOKEN", "test-secret-key")

    assert client.post("/api/telegram/test", json={"message": "x"}).status_code == 401
    assert client.post("/api/telegram/broadcast-test").status_code == 401

def test_api_audit_run_and_seed_require_api_key(monkeypatch):
    import dashboard.backend.security as security
    monkeypatch.setattr(security, "API_AUTH_TOKEN", "test-secret-key")

    assert client.get("/api/audit/run").status_code == 401
    assert client.get("/api/audit/seed-simulation").status_code == 401
    # Key benar -> handler berjalan (aman: DB kosong/testing)
    res = client.get("/api/audit/run", headers={"X-API-Key": "test-secret-key"})
    assert res.status_code == 200

def test_api_chart_rejects_invalid_ticker():
    # Catatan: path traversal (../) dinormalisasi server -> 404, bukan sampai ke handler
    for bad in ["BBCA;DROP TABLE signals", "$$$", "a b c", "BBCA.JK.JK"]:
        response = client.get(f"/api/chart/{bad}")
        assert response.status_code == 400, f"ticker {bad!r} harus ditolak"

def test_api_news_rejects_invalid_ticker():
    response = client.post("/api/news", json={"ticker": "../../etc/passwd"})
    assert response.status_code == 400

def test_api_narasi_rejects_invalid_ticker():
    payload = {
        "ticker": "X'; DROP TABLE signals;--",
        "close_price": 1000, "target_price": 1030, "stop_loss": 985,
        "rsi": 50, "macd_signal": "BULLISH", "trend": "UPTREND", "probability": 70.0,
    }
    response = client.post("/api/narasi", json=payload)
    assert response.status_code == 400
