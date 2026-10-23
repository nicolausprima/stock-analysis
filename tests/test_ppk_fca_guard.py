"""
Unit tests for PPK & FCA Hazard Guard.
"""

import pandas as pd

from src.guards.ppk_fca_guard import evaluate_ticker_hazard, filter_safe_universe


def test_hazard_guard_safe_stock():
    # Saham normal harga di atas 52 dan volume likuid
    df = pd.DataFrame({
        "Close": [5000, 5050, 5100],
        "Volume": [100000, 150000, 200000]
    })
    fund = {"total_equity": 50_000_000_000, "der": 0.8}
    res = evaluate_ticker_hazard("BBCA", df_price=df, fundamental=fund)
    assert res["verdict"] == "SAFE"
    assert not res["is_blocked"]
    assert res["hazard_score"] == 0


def test_hazard_guard_critical_low_price():
    # Saham harga Rp 50 (gocap) rawan masuk FCA Rp 1
    df = pd.DataFrame({
        "Close": [50, 50, 50],
        "Volume": [1000, 2000, 3000]
    })
    res = evaluate_ticker_hazard("GOCP", df_price=df)
    assert res["verdict"] == "CRITICAL_BLOCKED"
    assert res["is_blocked"]
    assert any("FCA" in r for r in res["reasons"])


def test_hazard_guard_negative_equity():
    # Saham dengan modal negatif (Kriteria 5 PPK)
    fund = {"total_equity": -10_000_000, "der": -2.5}
    res = evaluate_ticker_hazard("RUGI", fundamental=fund)
    assert res["verdict"] == "CRITICAL_BLOCKED"
    assert res["is_blocked"]
    assert any("Ekuitas negatif" in r for r in res["reasons"])


def test_hazard_guard_notation_flags():
    # Saham bertanda notasi khusus X
    res = evaluate_ticker_hazard("MONI", notasi_khusus=["X", "E"])
    assert res["verdict"] == "CRITICAL_BLOCKED"
    assert res["is_blocked"]
    assert any("Notasi Khusus" in r for r in res["reasons"])


def test_filter_safe_universe():
    tickers = ["BBCA", "GOCP"]
    # Filter safe universe harus menyaring saham bermasalah
    safe = filter_safe_universe(tickers)
    assert "BBCA" in safe
