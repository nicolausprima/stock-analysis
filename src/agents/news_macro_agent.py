import os
import json
import logging
import requests
import feedparser
from typing import Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "http://127.0.0.1:20128/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

if "host.docker.internal" in OPENAI_API_BASE and not os.path.exists('/.dockerenv'):
    OPENAI_API_BASE = OPENAI_API_BASE.replace("host.docker.internal", "127.0.0.1")

POSITIVE_KEYWORDS = [
    "naik", "menguat", "surplus", "tumbuh", "ekspansi", "potong suku bunga",
    "pemangkasan suku bunga", "bullish", "rally", "rebound", "gains", "surge",
    "stabilitas", "optimis", "mendorong", "laba"
]

NEGATIVE_KEYWORDS = [
    "turun", "melemah", "defisit", "kontraksi",
    "kenaikan suku bunga", "bearish", "slump", "fall", "drop", "resesi",
    "inflasi", "gejolak", "krisis", "tekanan", "rugi", "ketegangan"
]

class NewsMacroAgent:
    """
    Economic News Sentiment Agent.
    Fetches latest macroeconomic news from Google News RSS & Yahoo Finance,
    and analyzes market sentiment using LLM or keyword fallback.
    """
    
    def __init__(self):
        self.rss_urls = [
            "https://news.google.com/rss/search?q=IHSG+OR+ekonomi+indonesia+OR+BI+Rate+OR+Rupiah&hl=id&gl=ID&ceid=ID:id",
            "https://news.google.com/rss/search?q=Federal+Reserve+OR+US+Dollar+OR+global+market&hl=en-US&gl=US&ceid=US:en"
        ]

    def fetch_news_headlines(self, limit: int = 10) -> List[Dict[str, str]]:
        """Fetch news headlines from RSS feeds and yfinance."""
        headlines = []
        
        # 1. Fetch RSS Feeds
        for url in self.rss_urls:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:limit]:
                    title = getattr(entry, 'title', '').strip()
                    if title and not any(h['title'] == title for h in headlines):
                        headlines.append({
                            "title": title,
                            "source": getattr(entry, 'source', {}).get('title', 'RSS Feed'),
                            "link": getattr(entry, 'link', '')
                        })
            except Exception as e:
                logger.warning(f"Failed to fetch RSS news from {url}: {e}")

        # 2. Try yfinance news for IHSG ^JKSE
        try:
            import yfinance as yf
            ticker = yf.Ticker("^JKSE")
            yf_news = getattr(ticker, 'news', []) or []
            for item in yf_news[:5]:
                title = item.get('title', '').strip()
                if title and not any(h['title'] == title for h in headlines):
                    headlines.append({
                        "title": title,
                        "source": item.get('publisher', 'Yahoo Finance'),
                        "link": item.get('link', '')
                    })
        except Exception as e:
            logger.warning(f"Failed to fetch yfinance IHSG news: {e}")

        return headlines[:limit]

    def evaluate_sentiment(self, headlines: List[Dict[str, str]]) -> Dict[str, Any]:
        """Evaluate overall sentiment from headlines."""
        if not headlines:
            return {
                "score": 0.0,
                "label": "NETRAL",
                "reason": "Tidak ada berita makro yang berhasil diunduh.",
                "headlines": []
            }

        # Try LLM evaluation first
        llm_res = self._evaluate_with_llm(headlines)
        if llm_res:
            return llm_res

        # Fallback to keyword matching
        return self._evaluate_with_keywords(headlines)

    def _evaluate_with_keywords(self, headlines: List[Dict[str, str]]) -> Dict[str, Any]:
        """Rule-based keyword sentiment evaluation fallback."""
        total_score = 0.0
        analyzed_headlines = []

        for item in headlines:
            text = item["title"].lower()
            pos_hits = sum(1 for kw in POSITIVE_KEYWORDS if kw in text)
            neg_hits = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text)

            if pos_hits > neg_hits:
                item_sent = 1.0
                sent_label = "POSITIF ✅"
            elif neg_hits > pos_hits:
                item_sent = -1.0
                sent_label = "NEGATIF ⚠️"
            else:
                item_sent = 0.0
                sent_label = "NETRAL ➖"

            total_score += item_sent
            analyzed_headlines.append({
                "title": item["title"],
                "source": item.get("source", "News"),
                "sentiment": sent_label
            })

        avg_score = total_score / len(headlines) if headlines else 0.0
        
        if avg_score >= 0.2:
            overall_label = "POSITIF"
        elif avg_score <= -0.2:
            overall_label = "NEGATIF"
        else:
            overall_label = "NETRAL"

        return {
            "score": round(max(-1.0, min(1.0, avg_score)), 2),
            "label": overall_label,
            "reason": f"Analisis sentimen berbasis kata kunci dari {len(headlines)} berita makro.",
            "headlines": analyzed_headlines[:5]
        }

    def _evaluate_with_llm(self, headlines: List[Dict[str, str]]) -> Dict[str, Any]:
        """LLM-based macroeconomic news sentiment scoring."""
        url = f"{OPENAI_API_BASE}/chat/completions"
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}

        titles_text = "\n".join([f"- {h['title']}" for h in headlines[:7]])
        prompt = (
            "Kamu adalah Agen Sentimen Berita Makroekonomi Indonesia.\n"
            "Analisis kumpulan headline berita berikut dan berikan penilaian sentimen untuk pasar saham Indonesia (IHSG):\n"
            f"{titles_text}\n\n"
            "Format balasan HARUS JSON persis seperti berikut:\n"
            '{\n  "score": 0.5,\n  "label": "POSITIF",\n  "summary": "Ringkasan 1 kalimat sentimen berita."\n}\n'
            "Keterangan score: -1.0 (sangat negatif) sampai +1.0 (sangat positif)."
        )

        payload = {
            "model": "opencode/deepseek-v4-flash-free",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1
        }

        try:
            res = requests.post(url, json=payload, headers=headers, timeout=8)
            if res.status_code == 200:
                content = res.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                if "{" in content and "}" in content:
                    json_str = content[content.find("{"):content.rfind("}")+1]
                    data = json.loads(json_str)
                    score = float(data.get("score", 0.0))
                    label = str(data.get("label", "NETRAL")).upper()
                    summary = str(data.get("summary", ""))

                    analyzed_headlines = [
                        {"title": h["title"], "source": h.get("source", "News"), "sentiment": label}
                        for h in headlines[:5]
                    ]

                    return {
                        "score": round(max(-1.0, min(1.0, score)), 2),
                        "label": label if label in ["POSITIF", "NEGATIF", "NETRAL"] else "NETRAL",
                        "reason": summary or f"Analisis AI dari {len(headlines)} berita makroekonomi.",
                        "headlines": analyzed_headlines
                    }
        except Exception as e:
            logger.debug(f"LLM news evaluation skipped: {e}")
            
        return None
