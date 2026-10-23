"""
Unit tests for Conformal Prediction Gate.
"""

from src.features.conformal_gate import (
    ConformalPredictorGate,
    evaluate_conformal_candidate,
)


def test_conformal_gate_interval():
    gate = ConformalPredictorGate(alpha=0.10, default_quantile_radius=0.15)
    lower, upper, width = gate.predict_interval(0.80)
    assert round(lower, 2) == 0.65
    assert round(upper, 2) == 0.95
    assert round(width, 2) == 0.30


def test_conformal_gate_confident_buy():
    gate = ConformalPredictorGate(alpha=0.10, default_quantile_radius=0.12)
    res = gate.evaluate_signal(85.0, signal=1, min_lower_bound=50.0)
    assert res["verdict"] == "CONFIDENT_BUY"
    assert res["should_trade"] is True
    assert res["conformal_multiplier"] >= 1.0


def test_conformal_gate_abstain():
    gate = ConformalPredictorGate(alpha=0.10, default_quantile_radius=0.20)
    # Probabilitas 60% dengan radius 20% -> lower bound 40% < min 50% -> ABSTAIN
    res = gate.evaluate_signal(60.0, signal=1, min_lower_bound=50.0)
    assert res["verdict"] == "ABSTAIN"
    assert res["should_trade"] is False
    assert res["conformal_multiplier"] == 0.0


def test_evaluate_conformal_candidate():
    candidate = {
        "ticker": "BBCA.JK",
        "probability": 85.0,
        "signal": 1,
        "kelly_allocation": 15.0,
    }
    enriched = evaluate_conformal_candidate(candidate)
    assert "conformal_verdict" in enriched
    assert "conformal_lower" in enriched
    assert "conformal_upper" in enriched
    assert "adjusted_kelly_allocation" in enriched
