import os
import re
import time
import json
import hashlib
import logging
import sqlite3
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Financial Sentiment Lexicon with fine-grained weights (-3.0 to +3.0)
FINANCIAL_LEXICON = {
    # Strong Negative (-3.0)
    "pailit": -3.0, "kebangkrutan": -3.0, "bankruptcy": -3.0, "fraud": -3.0,
    "korupsi": -3.0, "gagal bayar": -3.0, "default": -3.0, "suspensi": -2.5,
    "delisting": -3.0, "penyidikan": -2.5, "tersangka": -2.5, "sanksi bei": -2.5,
    "denda": -2.0, "gugatan": -2.0, "lawsuit": -2.0, "sengketa": -2.0,

    # Moderate Negative (-1.5 to -2.0)
    "rugi bersih": -2.2, "rugi": -1.8, "loss": -1.8, "anjlok": -2.0, "terjun": -2.0,
    "slump": -1.8, "drop": -1.5, "merosot": -1.8, "melemah": -1.2, "turun": -1.0,
    "penurunan laba": -2.0, "kontraksi": -1.5, "defisit": -1.5, "resesi": -2.0,
    "inflasi tinggi": -1.5, "krisis": -2.2, "tekanan": -1.2, "capital outflow": -2.0,
    "net sell asing": -1.5, "pemotongan rating": -2.0, "downgrade": -2.0,

    # Strong Positive (+2.5 to +3.0)
    "rekor laba": 3.0, "laba melonjak": 3.0, "all-time high": 2.8, "ath": 2.5,
    "akuisisi strategis": 2.5, "dividen jumbo": 2.8, "buyback": 2.5,
    "tender offer": 2.5, "kontrak baru": 2.2, "mou bernilai": 2.2,

    # Moderate Positive (+1.0 to +2.0)
    "laba bersih naik": 2.2, "laba": 1.5, "profit": 1.5, "net income": 1.5,
    "surplus": 1.8, "tumbuh": 1.5, "growth": 1.5, "ekspansi": 1.8, "expansion": 1.8,
    "potong suku bunga": 2.0, "pemangkasan suku bunga": 2.0, "rate cut": 2.0,
    "bullish": 1.8, "rally": 1.8, "rebound": 1.6, "surge": 1.8, "melonjak": 1.8,
    "menguat": 1.3, "naik": 1.0, "gain": 1.2, "stabilitas": 1.2, "optimis": 1.3,
    "upgrade": 2.0, "rekomendasi beli": 2.0, "target harga naik": 2.0,
    "net buy asing": 1.8, "inflow": 1.5, "dividen": 1.5, "dividend": 1.5
}

# Modifiers (Amplifiers & Inverters)
INTENSIFIERS = {
    "sangat": 1.5, "amat": 1.5, "drastis": 1.6, "signifikan": 1.4,
    "tajam": 1.5, "masif": 1.6, "substansial": 1.4, "rekor": 1.6,
    "huge": 1.5, "sharp": 1.5, "massive": 1.6, "significant": 1.4
}

NEGATIONS = [
    "tidak", "bukan", "belum", "tanpa", "gagal", "not", "no", "never", "hardly"
]


class FinancialSentimentAnalyzer:
    """
    High-Performance Multi-Tier Financial Sentiment Engine for Indonesian & Global Markets.
    - Tier 1: Local FinBERT / Transformer inference if installed.
    - Tier 2: Comprehensive Indonesian Financial Lexicon + contextual parsing.
    - Tier 3: SQLite cache for lightning-fast sub-millisecond repeated lookups.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        self._hf_pipeline = None
        self._hf_checked = False
        self._init_cache_table()

    def _get_db_connection(self):
        """Helper to get SQLite connection for caching."""
        if not self.db_path:
            try:
                from src.config import DB_PATH
                self.db_path = str(DB_PATH)
            except Exception:
                self.db_path = "stock_market.db"
        try:
            conn = sqlite3.connect(self.db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL;")
            return conn
        except Exception:
            return None

    def _init_cache_table(self):
        """Create sentiment cache table if it doesn't exist."""
        conn = self._get_db_connection()
        if conn:
            try:
                with conn:
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS news_sentiment_cache (
                            headline_hash TEXT PRIMARY KEY,
                            headline TEXT,
                            score REAL,
                            label TEXT,
                            highlights TEXT,
                            created_at INTEGER
                        )
                    """)
            except Exception as e:
                logger.debug(f"Cache table init error: {e}")
            finally:
                conn.close()

    def _load_hf_model_if_available(self):
        """Optional: loads lightweight FinBERT only if pre-cached locally or explicitly enabled."""
        if self._hf_checked:
            return self._hf_pipeline
        self._hf_checked = True
        
        # Only attempt loading if explicit environment variable is enabled
        if os.getenv("USE_TRANSFORMERS_SENTIMENT", "0") != "1":
            self._hf_pipeline = None
            return None

        try:
            import transformers
            from transformers import pipeline
            self._hf_pipeline = pipeline(
                "sentiment-analysis",
                model="ProsusAI/finbert",
                tokenizer="ProsusAI/finbert",
                model_kwargs={"local_files_only": True},
                device=-1  # CPU mode
            )
            logger.info("FinBERT Transformer model initialized successfully from local cache.")
        except Exception:
            self._hf_pipeline = None
            logger.debug("Transformers FinBERT not cached locally; using native Financial Lexicon engine.")
        return self._hf_pipeline

    def score_text(self, text: str) -> Dict[str, Any]:
        """
        Analyze a single headline or paragraph.
        Returns:
            {
                "score": float (-1.0 to +1.0),
                "label": str ("SANGAT POSITIF", "POSITIF", "NETRAL", "NEGATIF", "SANGAT NEGATIF"),
                "confidence": float (0.0 to 1.0),
                "highlights": list of detected signals
            }
        """
        if not text or not text.strip():
            return {"score": 0.0, "label": "NETRAL", "confidence": 0.0, "highlights": []}

        clean_text = text.strip()
        headline_hash = hashlib.sha256(clean_text.lower().encode("utf-8")).hexdigest()

        # Check Cache
        cached = self._get_cached_sentiment(headline_hash)
        if cached:
            return cached

        # Check HuggingFace FinBERT first if available
        hf_pipe = self._load_hf_model_if_available()
        if hf_pipe:
            try:
                res = hf_pipe(clean_text[:512])[0]
                hf_label = res["label"].lower()
                hf_conf = float(res["score"])
                if "positive" in hf_label:
                    score = hf_conf * 0.8
                elif "negative" in hf_label:
                    score = -hf_conf * 0.8
                else:
                    score = 0.0
                label = self._score_to_label(score)
                result = {
                    "score": round(score, 3),
                    "label": label,
                    "confidence": round(hf_conf, 2),
                    "highlights": [f"FinBERT: {res['label']} ({hf_conf:.1%})"]
                }
                self._save_cached_sentiment(headline_hash, clean_text, result)
                return result
            except Exception as e:
                logger.debug(f"FinBERT inference exception: {e}")

        # High-Accuracy Financial Lexicon + Context Parsing
        result = self._score_with_financial_lexicon(clean_text)
        self._save_cached_sentiment(headline_hash, clean_text, result)
        return result

    def _score_with_financial_lexicon(self, text: str) -> Dict[str, Any]:
        """Context-aware financial phrase and keyword analyzer."""
        lower = text.lower()
        words = re.findall(r'\b[\w-]+\b', lower)
        
        total_score = 0.0
        matched_catalysts = []
        
        # 1. Match multi-word phrases first
        checked_phrases = set()
        for phrase, weight in sorted(FINANCIAL_LEXICON.items(), key=lambda x: -len(x[0])):
            if " " in phrase and phrase in lower:
                # Check for negation in 4 words preceding phrase
                negated = False
                phrase_idx = lower.find(phrase)
                prefix = lower[max(0, phrase_idx - 30):phrase_idx]
                if any(neg in prefix for neg in NEGATIONS):
                    negated = True

                final_weight = -weight * 0.7 if negated else weight
                total_score += final_weight
                matched_catalysts.append(f"{phrase.title()} ({'+' if final_weight > 0 else ''}{final_weight:.1f})")
                checked_phrases.add(phrase)

        # 2. Match single words with modifiers
        for i, word in enumerate(words):
            if word in FINANCIAL_LEXICON and not any(word in p for p in checked_phrases):
                weight = FINANCIAL_LEXICON[word]
                
                # Check preceding modifier
                multiplier = 1.0
                if i > 0 and words[i-1] in INTENSIFIERS:
                    multiplier = INTENSIFIERS[words[i-1]]
                elif i > 1 and words[i-2] in INTENSIFIERS:
                    multiplier = INTENSIFIERS[words[i-2]]

                # Check preceding negation
                negated = False
                if i > 0 and words[i-1] in NEGATIONS:
                    negated = True
                elif i > 1 and words[i-2] in NEGATIONS:
                    negated = True

                final_weight = (-weight * 0.7 if negated else weight) * multiplier
                total_score += final_weight
                matched_catalysts.append(f"{word.title()} ({'+' if final_weight > 0 else ''}{final_weight:.1f})")

        # Normalize score to [-1.0, 1.0]
        if not matched_catalysts:
            norm_score = 0.0
            confidence = 0.5
        else:
            norm_score = max(-1.0, min(1.0, total_score / 3.5))
            confidence = min(0.95, 0.5 + (len(matched_catalysts) * 0.15))

        label = self._score_to_label(norm_score)

        return {
            "score": round(norm_score, 3),
            "label": label,
            "confidence": round(confidence, 2),
            "highlights": matched_catalysts[:4]
        }

    def _score_to_label(self, score: float) -> str:
        if score >= 0.5:
            return "SANGAT POSITIF"
        elif score >= 0.15:
            return "POSITIF"
        elif score <= -0.5:
            return "SANGAT NEGATIF"
        elif score <= -0.15:
            return "NEGATIF"
        else:
            return "NETRAL"

    def analyze_ticker_headlines(self, ticker: str, headlines: List[str]) -> Dict[str, Any]:
        """
        Evaluate collective news sentiment for an equity ticker.
        Applies asymmetric risk weighting (negative news penalizes more severely than positive boosts).
        """
        clean_ticker = ticker.replace(".JK", "").upper()
        if not headlines:
            return {
                "ticker": clean_ticker,
                "sentiment_status": "NETRAL",
                "sentiment_score": 0.0,
                "score_delta": 0.0,
                "sentiment_impact": "NETRAL",
                "sentiment_reason": "Tidak ada berita baru (Netral)",
                "highlights": [],
                "news_count": 0
            }

        scores = []
        all_highlights = []

        for h in headlines:
            res = self.score_text(h)
            scores.append(res["score"])
            if res.get("highlights"):
                all_highlights.extend(res["highlights"])

        avg_score = sum(scores) / len(scores) if scores else 0.0
        min_score = min(scores) if scores else 0.0

        # Asymmetric Risk Filtering Logic:
        # If any single headline is catastrophic (<= -0.55), trigger Risk Veto
        if min_score <= -0.55 or avg_score <= -0.35:
            sentiment_status = "NEGATIF"
            score_delta = -25.0
            impact = "RISK VETO (-25%)"
            reason = f"Terdeteksi risiko negatif: {', '.join(all_highlights[:2]) if all_highlights else 'Isu/Berita Penurunan'}"
        elif avg_score >= 0.15:
            sentiment_status = "POSITIF"
            boost = round(min(4.5, max(1.5, avg_score * 5.0)), 1)
            score_delta = boost
            impact = f"BOOSTER (+{boost}%)"
            reason = f"Katalis positif aktif: {', '.join(all_highlights[:2]) if all_highlights else 'Pertumbuhan / Penguatan'}"
        else:
            sentiment_status = "NETRAL"
            score_delta = 0.0
            impact = "NETRAL"
            reason = "Sentimen berita seimbang / minim katalis baru"

        return {
            "ticker": clean_ticker,
            "sentiment_status": sentiment_status,
            "sentiment_score": round(avg_score, 3),
            "score_delta": score_delta,
            "sentiment_impact": impact,
            "sentiment_reason": reason,
            "highlights": sorted(set(all_highlights))[:5],
            "news_count": len(headlines)
        }

    def _get_cached_sentiment(self, headline_hash: str) -> Optional[Dict[str, Any]]:
        conn = self._get_db_connection()
        if not conn:
            return None
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT score, label, highlights, created_at FROM news_sentiment_cache WHERE headline_hash = ?", (headline_hash,))
            row = cursor.fetchone()
            if row:
                if time.time() - row[3] < 86400:
                    highlights = json.loads(row[2]) if row[2] else []
                    return {
                        "score": float(row[0]),
                        "label": str(row[1]),
                        "confidence": 0.85,
                        "highlights": highlights
                    }
        except Exception:
            pass
        finally:
            conn.close()
        return None

    def _save_cached_sentiment(self, headline_hash: str, headline: str, result: Dict[str, Any]):
        conn = self._get_db_connection()
        if not conn:
            return
        try:
            with conn:
                conn.execute("""
                    INSERT OR REPLACE INTO news_sentiment_cache (headline_hash, headline, score, label, highlights, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    headline_hash,
                    headline[:300],
                    result["score"],
                    result["label"],
                    json.dumps(result.get("highlights", [])),
                    int(time.time())
                ))
        except Exception:
            pass
        finally:
            conn.close()


# Default singleton instance
_default_analyzer = None

def get_sentiment_analyzer() -> FinancialSentimentAnalyzer:
    global _default_analyzer
    if _default_analyzer is None:
        _default_analyzer = FinancialSentimentAnalyzer()
    return _default_analyzer
