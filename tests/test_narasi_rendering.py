"""Regresi double-escaping narasi (audit 2026-10-30, D-05).

Kontrak: API mengembalikan plain text; klien yang meng-escape sekali saat
merender (textContent / esc()). Bila backend juga meng-escape, teks seperti
"RSI < 40" tampil sebagai "RSI &lt; 40" di layar.
"""
import os

os.environ.setdefault("TESTING", "true")

from fastapi.testclient import TestClient

from dashboard.backend.main import app

client = TestClient(app)

PAYLOAD = {
    "ticker": "BBCA.JK",
    "close_price": 9950,
    "target_price": 10250,
    "stop_loss": 9800,
    "rsi": 54.2,
    "macd_signal": "BULLISH",
    "trend": "UPTREND",
    "probability": 82.5,
}


class _FakeLlmResponse:
    status_code = 200
    text = 'data: {"choices":[{"delta":{"content":"RSI < 40 & tren naik > rata-rata"}}]}\n'


def test_narasi_returns_plain_text(monkeypatch):
    from dashboard.backend.routes import narasi as narasi_mod

    monkeypatch.setattr(narasi_mod.requests, "post", lambda *a, **k: _FakeLlmResponse())

    res = client.post("/api/narasi", json=PAYLOAD)
    assert res.status_code == 200
    body = res.json()
    assert body["source"] == "llm"
    assert "RSI < 40 & tren naik > rata-rata" in body["narasi"]
    assert "&lt;" not in body["narasi"]
    assert "&amp;" not in body["narasi"]


def test_multi_agent_consensus_returns_plain_text(monkeypatch):
    class _FakeMultiAgent:
        def __init__(self, *args, **kwargs):
            pass

        def generate_consensus(self, req, macro_info=None):
            return {
                "bull_case": "Momentum < kuat & sehat",
                "bear_case": "Risiko > 2%",
                "risk_verdict": "BELI",
                "risk_reward_ratio": 2.1,
            }

    monkeypatch.setattr("src.agents.multi_agent_v2.MultiAgentSystemV2", _FakeMultiAgent)

    res = client.post("/api/narasi/multi-agent", json=PAYLOAD)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["bull_case"] == "Momentum < kuat & sehat"
    assert data["risk_reward_ratio"] == 2.1
