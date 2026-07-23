import os
import pytest
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.collector.openbb_provider import OpenBBProvider
from src.agents.multi_agent_system import MultiAgentSystem

def test_openbb_provider_fallback():
    provider = OpenBBProvider()
    # Test getting indicators with dummy data or real fetch
    indicators = provider.get_technical_indicators("BBCA.JK")
    assert isinstance(indicators, dict)
    if indicators:
        assert "ticker" in indicators
        assert "rsi_14" in indicators
        assert "current_close" in indicators

def test_multi_agent_system():
    system = MultiAgentSystem()
    sample_data = {
        "ticker": "BBCA.JK",
        "close_price": 10000.0,
        "target_price": 10500.0,
        "stop_loss": 9700.0,
        "rsi": 55.0,
        "macd_signal": "BULLISH",
        "trend": "UPTREND",
        "probability": 68.5,
        "sentiment_status": "POSITIF",
        "sentiment_impact": "DORONGAN POSITIF"
    }
    
    result = system.generate_consensus(sample_data)
    assert result["ticker"] == "BBCA"
    assert "technical_view" in result
    assert "sentiment_view" in result
    assert "bull_case" in result
    assert "bear_case" in result
    assert "risk_verdict" in result
    assert "risk_reward_ratio" in result
    assert result["risk_reward_ratio"] > 0
