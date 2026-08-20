import pytest
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.sentiment.sentiment_engine import FinancialSentimentAnalyzer, get_sentiment_analyzer


def test_sentiment_analyzer_positive_headlines():
    analyzer = FinancialSentimentAnalyzer(db_path=":memory:")
    
    text = "Laba bersih BBCA melonjak 25% mencapai rekor tertinggi sepanjang sejarah"
    res = analyzer.score_text(text)
    
    assert res["score"] > 0.15
    assert res["label"] in ["POSITIF", "SANGAT POSITIF"]
    assert len(res["highlights"]) > 0


def test_sentiment_analyzer_negative_headlines():
    analyzer = FinancialSentimentAnalyzer(db_path=":memory:")
    
    text = "Emiten terancam pailit dan suspensi BEI akibat gagal bayar obligasi"
    res = analyzer.score_text(text)
    
    assert res["score"] < -0.2
    assert res["label"] in ["NEGATIF", "SANGAT NEGATIF"]
    assert any("Pailit" in h or "Suspensi" in h or "Gagal Bayar" in h for h in res["highlights"])


def test_sentiment_analyzer_ticker_asymmetric_filter():
    analyzer = FinancialSentimentAnalyzer(db_path=":memory:")
    
    # Positive case
    pos_headlines = [
        "BBRI membukukan laba bersih Rp 60 Triliun dan bagikan dividen jumbo",
        "Kinerja kredit UMKM tumbuh pesat mendukung ekspansi bisnis"
    ]
    pos_res = analyzer.analyze_ticker_headlines("BBRI.JK", pos_headlines)
    assert pos_res["sentiment_status"] == "POSITIF"
    assert pos_res["score_delta"] > 0
    assert "BOOSTER" in pos_res["sentiment_impact"]

    # Negative case (Risk Veto)
    neg_headlines = [
        "KPK melakukan penyidikan kasus dugaan korupsi dan fraud laporan keuangan",
        "Laba anjlok parah tertekan beban operasional"
    ]
    neg_res = analyzer.analyze_ticker_headlines("WSKT.JK", neg_headlines)
    assert neg_res["sentiment_status"] == "NEGATIF"
    assert neg_res["score_delta"] <= -20.0
    assert "RISK VETO" in neg_res["sentiment_impact"]


def test_sentiment_analyzer_empty_and_neutral():
    analyzer = FinancialSentimentAnalyzer(db_path=":memory:")
    
    empty_res = analyzer.analyze_ticker_headlines("TLKM.JK", [])
    assert empty_res["sentiment_status"] == "NETRAL"
    assert empty_res["score_delta"] == 0.0

    neutral_res = analyzer.score_text("Jadwal Rapat Umum Pemegang Saham Tahunan (RUPST) Perseroan")
    assert neutral_res["label"] == "NETRAL"
