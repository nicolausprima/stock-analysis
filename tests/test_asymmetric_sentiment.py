import pytest
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from dashboard.backend.routes.sentiment_filter import apply_asymmetric_sentiment_filter

def test_asymmetric_sentiment_filter_structure():
    candidates = [
        {
            "ticker": "BBCA.JK",
            "probability": 70.0,
            "signal": 1,
            "close_price": 9800,
            "target_price": 10094,
            "stop_loss": 9653,
            "rsi": 55,
            "rsi_signal": "NETRAL",
            "macd_signal": "BULLISH",
            "trend": "UPTREND",
            "reason": "MACD Golden Cross"
        }
    ]
    
    results = apply_asymmetric_sentiment_filter(candidates)
    
    assert len(results) == 1
    assert "sentiment_status" in results[0]
    assert "sentiment_impact" in results[0]
    assert "probability_raw" in results[0]
    assert results[0]["sentiment_status"] in ["POSITIF", "NEGATIF", "NETRAL"]
