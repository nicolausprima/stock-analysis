import yfinance as yf
import re

# Kata kunci indikator sentimen negatif (Risiko Veto)
NEGATIVE_KEYWORDS = [
    r'\brugi\b', r'\bloss\b', r'\bkorupsi\b', r'\bfraud\b', r'\bgagal\b', r'\bdefault\b',
    r'\bsuspensi\b', r'\bsengketa\b', r'\bdenda\b', r'\blawsuit\b', r'\bkrisis\b',
    r'\bpenyidikan\b', r'\bbankruptcy\b', r'\bpailit\b', r'\bturun\b', r'\bslump\b', r'\bdrop\b'
]

# Kata kunci indikator sentimen positif (Score Booster)
POSITIVE_KEYWORDS = [
    r'\blaba\b', r'\bprofit\b', r'\bnaik\b', r'\bsurge\b', r'\bsurged\b', r'\bakuisisi\b',
    r'\bdividen\b', r'\bdividend\b', r'\bgrowth\b', r'\brecord\b', r'\bmerger\b',
    r'\bgain\b', r'\brebound\b', r'\bmelonjak\b', r'\btumbuh\b', r'\bkontrak\b', r'\bmoul\b'
]

def fetch_recent_headlines(ticker: str) -> list[str]:
    """Mengambil 3 judul berita harian terbaru untuk ticker dari Yahoo Finance."""
    yf_ticker_str = f"{ticker}.JK" if not ticker.endswith(".JK") else ticker
    try:
        yf_ticker = yf.Ticker(yf_ticker_str)
        news_data = yf_ticker.news or []
        headlines = []
        for item in news_data[:4]:
            title = item.get("title", "")
            summary = item.get("summary", "")
            if title:
                headlines.append(f"{title} {summary}")
        return headlines
    except Exception:
        return []

def evaluate_ticker_sentiment(ticker: str) -> dict:
    """Mengevaluasi sentimen berita harian untuk ticker."""
    headlines = fetch_recent_headlines(ticker)
    if not headlines:
        return {"status": "NETRAL", "score_delta": 0.0, "reason": "Tidak ada berita baru (Netral)"}

    combined_text = " ".join(headlines).lower()

    neg_matches = sum(1 for kw in NEGATIVE_KEYWORDS if re.search(kw, combined_text))
    pos_matches = sum(1 for kw in POSITIVE_KEYWORDS if re.search(kw, combined_text))

    if neg_matches > pos_matches and neg_matches >= 1:
        return {
            "status": "NEGATIF",
            "score_delta": -25.0, # Penalti Veto
            "impact": "RISK VETO (-25%)",
            "reason": f"Terdeteksi {neg_matches} isu/berita negatif (Veto Risiko)"
        }
    elif pos_matches > neg_matches and pos_matches >= 1:
        return {
            "status": "POSITIF",
            "score_delta": 3.0, # Bonus Booster
            "impact": "BOOSTER (+3%)",
            "reason": f"Terdeteksi {pos_matches} katalis berita positif (+3% Boost)"
        }
    else:
        return {
            "status": "NETRAL",
            "score_delta": 0.0,
            "impact": "NETRAL",
            "reason": "Sentimen berita seimbang / netral"
        }

def apply_asymmetric_sentiment_filter(candidates: list[dict]) -> list[dict]:
    """
    Menerapkan Asymmetric Risk Filter & Score Booster pada kandidat saham.
    - NEGATIF: Diberi penalti skor atau di-veto dari daftar utama.
    - POSITIF: Diberikan bonus skor probabilitas +3.0%.
    - NETRAL: Mempertahankan skor asli XGBoost.
    """
    filtered_results = []
    
    for item in candidates:
        ticker = item["ticker"]
        sentiment_eval = evaluate_ticker_sentiment(ticker)
        
        raw_prob = item["probability"]
        score_delta = sentiment_eval["score_delta"]
        
        # Hitung skor yang disesuaikan (adjusted probability)
        adjusted_prob = round(max(0.0, min(99.0, raw_prob + score_delta)), 1)
        
        item_copy = dict(item)
        item_copy["probability_raw"] = raw_prob
        item_copy["probability"] = adjusted_prob
        item_copy["sentiment_status"] = sentiment_eval["status"]
        item_copy["sentiment_impact"] = sentiment_eval.get("impact", "NETRAL")
        item_copy["sentiment_reason"] = sentiment_eval["reason"]
        
        filtered_results.append(item_copy)

    # Urutkan ulang kandidat berdasarkan skor probabilitas yang sudah disesuaikan
    filtered_results.sort(key=lambda x: x["probability"], reverse=True)
    return filtered_results
