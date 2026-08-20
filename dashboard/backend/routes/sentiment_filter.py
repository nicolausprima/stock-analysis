import re
import time
import yfinance as yf
from src.sentiment.sentiment_engine import get_sentiment_analyzer

# Cache headline per ticker (30 menit TTL) agar scan 700+ saham tidak
# membanjiri Yahoo Finance dengan ribuan request berulang.
_HEADLINE_CACHE = {}
_HEADLINE_CACHE_TTL = 1800      # 30 menit
_HEADLINE_CACHE_MAX = 1000      # batas entri untuk cegah kebocoran memori

_TICKER_SANITIZE_RE = re.compile(r"[^A-Z0-9]")


def _sanitize_ticker(ticker: str) -> str:
    """Normalisasi ticker untuk lookup yfinance (tanpa raise)."""
    return _TICKER_SANITIZE_RE.sub("", (ticker or "").upper())[:10]


def _get_cached_headlines(ticker: str):
    entry = _HEADLINE_CACHE.get(ticker)
    if entry and time.time() - entry[0] < _HEADLINE_CACHE_TTL:
        return entry[1]
    return None


def _set_cached_headlines(ticker: str, headlines: list):
    if len(_HEADLINE_CACHE) >= _HEADLINE_CACHE_MAX:
        oldest = min(_HEADLINE_CACHE, key=lambda k: _HEADLINE_CACHE[k][0])
        _HEADLINE_CACHE.pop(oldest, None)
    _HEADLINE_CACHE[ticker] = (time.time(), headlines)


def fetch_recent_headlines(ticker: str) -> list[str]:
    """Mengambil 3-4 judul berita harian terbaru untuk ticker dari Yahoo Finance (dengan cache 30 menit)."""
    clean_ticker = _sanitize_ticker(ticker)
    if not clean_ticker:
        return []

    cached = _get_cached_headlines(clean_ticker)
    if cached is not None:
        return cached

    yf_ticker_str = f"{clean_ticker}.JK" if not clean_ticker.endswith(".JK") else clean_ticker
    headlines = []
    try:
        yf_ticker = yf.Ticker(yf_ticker_str)
        news_data = getattr(yf_ticker, 'news', []) or []
        for item in news_data[:4]:
            title = item.get("title", "")
            summary = item.get("summary", "")
            if title:
                headlines.append(f"{title} {summary}".strip())
    except Exception:
        headlines = []

    _set_cached_headlines(clean_ticker, headlines)
    return headlines

def evaluate_ticker_sentiment(ticker: str) -> dict:
    """Mengevaluasi sentimen berita harian untuk ticker menggunakan FinancialSentimentAnalyzer engine."""
    clean_ticker = _sanitize_ticker(ticker)
    headlines = fetch_recent_headlines(clean_ticker)
    analyzer = get_sentiment_analyzer()
    res = analyzer.analyze_ticker_headlines(clean_ticker, headlines)

    return {
        "status": res["sentiment_status"],
        "score": res["sentiment_score"],
        "score_delta": res["score_delta"],
        "impact": res["sentiment_impact"],
        "reason": res["sentiment_reason"],
        "highlights": res["highlights"]
    }

def apply_asymmetric_sentiment_filter(candidates: list[dict]) -> list[dict]:
    """
    Menerapkan Asymmetric Risk Filter & Score Booster pada kandidat saham.
    - NEGATIF: Diberi penalti skor risiko / di-veto.
    - POSITIF: Diberikan bonus skor probabilitas (+1.5% s/d +4.5%).
    - NETRAL: Mempertahankan skor asli XGBoost.
    """
    filtered_results = []

    for item in candidates:
        ticker = item.get("ticker", "")
        sentiment_eval = evaluate_ticker_sentiment(ticker)

        raw_prob = float(item.get("probability", 50.0))
        score_delta = float(sentiment_eval.get("score_delta", 0.0))

        # Hitung skor yang disesuaikan (adjusted probability)
        adjusted_prob = round(max(0.0, min(99.0, raw_prob + score_delta)), 1)

        item_copy = dict(item)
        item_copy["probability_raw"] = raw_prob
        item_copy["probability"] = adjusted_prob
        item_copy["sentiment_status"] = sentiment_eval["status"]
        item_copy["sentiment_impact"] = sentiment_eval.get("impact", "NETRAL")
        item_copy["sentiment_reason"] = sentiment_eval["reason"]
        item_copy["sentiment_score"] = sentiment_eval.get("score", 0.0)
        item_copy["sentiment_highlights"] = sentiment_eval.get("highlights", [])

        filtered_results.append(item_copy)

    # Urutkan ulang kandidat berdasarkan skor probabilitas yang sudah disesuaikan
    filtered_results.sort(key=lambda x: x["probability"], reverse=True)
    return filtered_results