import os
import pytest
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.agents.news_macro_agent import NewsMacroAgent
from src.agents.ihsg_macro_agent import IHSGMacroAgent
from src.agents.multi_agent_system import MultiAgentSystem

def test_news_macro_agent_keyword_evaluation():
    agent = NewsMacroAgent()
    positive_headlines = [
        {"title": "Ekonomi Indonesia Tumbuh 5.1%, IHSG Menguat Kencang", "source": "Test"},
        {"title": "Rupiah Menguat Terhadap Dollar AS Hari Ini", "source": "Test"}
    ]
    eval_pos = agent._evaluate_with_keywords(positive_headlines)
    assert eval_pos["score"] > 0
    assert eval_pos["label"] == "POSITIF"

    negative_headlines = [
        {"title": "Inflasi Melonjak, Rupiah Melemah Tertekan Krisis Global", "source": "Test"},
        {"title": "Pasar Saham Anjlok Tersebab Resesi dan Defisit", "source": "Test"}
    ]
    eval_neg = agent._evaluate_with_keywords(negative_headlines)
    assert eval_neg["score"] < 0
    assert eval_neg["label"] == "NEGATIF"

def test_ihsg_macro_agent_evaluation():
    agent = IHSGMacroAgent()
    # Evaluate with skip_news=True to avoid network calls during fast unit test
    result = agent.evaluate(skip_news=True)
    assert result["status"] == "success"
    assert result["mode"] in ["NORMAL", "CAUTIOUS", "BLOCK"]
    assert "macro_score" in result
    assert isinstance(result["details"], list)

def test_multi_agent_with_macro_context():
    system = MultiAgentSystem()
    data = {
        "ticker": "BBCA.JK",
        "close_price": 6500,
        "target_price": 6700,
        "stop_loss": 6400,
        "rsi": 52.0,
        "macd_signal": "BULLISH",
        "trend": "UPTREND",
        "probability": 78.0
    }
    macro_info = {
        "mode": "CAUTIOUS",
        "macro_score": 0.5,
        "mode_badge": "🟡 MODE CAUTIOUS"
    }
    consensus = system.generate_consensus(data, macro_info=macro_info)
    assert consensus["ticker"] == "BBCA"
    assert "Macro Intelligence" in consensus["consensus_summary"] or "Konteks Makro" in consensus["consensus_summary"]
    assert "macro_view" in consensus
