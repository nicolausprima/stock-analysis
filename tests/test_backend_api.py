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
    """Memastikan folder data dan cache file rekomendasi selalu terisi dengan data valid sebelum testing."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    dummy_cache = {
        "status": "success",
        "timestamp": "2026-07-20 16:05:00",
        "total_scanned": 300,
        "data": [
            {
                "ticker": "BBCA.JK",
                "probability": 78.5,
                "signal": 1,
                "close_price": 9800,
                "target_price": 10094,
                "stop_loss": 9653,
                "rsi": 55,
                "rsi_signal": "NETRAL",
                "macd_signal": "BULLISH",
                "trend": "UPTREND",
                "reason": "MACD Golden Cross",
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
