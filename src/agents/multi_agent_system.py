import os
import json
import requests
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "http://127.0.0.1:20128/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

if "host.docker.internal" in OPENAI_API_BASE and not os.path.exists('/.dockerenv'):
    OPENAI_API_BASE = OPENAI_API_BASE.replace("host.docker.internal", "127.0.0.1")

class TechnicalAnalystAgent:
    """Agent specialized in price action, RSI, MACD, and trend analysis."""
    def analyze(self, data: Dict[str, Any]) -> str:
        rsi = data.get("rsi", 50.0)
        macd = data.get("macd_signal", "BULLISH")
        trend = data.get("trend", "UPTREND")
        target = data.get("target_price", 0)
        close = data.get("close_price", 0)
        upside = ((target - close) / close * 100) if close > 0 else 0
        
        return (
            f"Analisis Teknikal: Tren {trend} dengan RSI {rsi:.1f} ({'Oversold' if rsi < 35 else 'Overbought' if rsi > 70 else 'Netral/Ideal'}). "
            f"Sinyal MACD: {macd}. Potensi kenaikan teknikal mencapai +{upside:.1f}% menuju target Rp {target:.0f}."
        )

class SentimentAnalystAgent:
    """Agent specialized in news sentiment and catalyst impact."""
    def analyze(self, data: Dict[str, Any]) -> str:
        status = data.get("sentiment_status", "NETRAL")
        impact = data.get("sentiment_impact", "NETRAL")
        return (
            f"Analisis Sentimen: Sentimen pasar saat ini terpantau {status} dengan dampak {impact}. "
            f"Dukungan narasi publik memberi dorongan {'positif' if status == 'POSITIF' else 'terbatas'} bagi pergerakan harga saham."
        )

class BullBearDebateAgent:
    """Simulates a debate between Bull (upside factors) and Bear (risk factors)."""
    def debate(self, tech_summary: str, sent_summary: str, data: Dict[str, Any]) -> Dict[str, str]:
        prob = data.get("probability", 50.0)
        ticker = data.get("ticker", "SAHAM").replace(".JK", "")
        
        bull_case = (
            f"Pandangan Bullish (Pembeli): {ticker} memiliki probabilitas AI {prob:.1f}%. {tech_summary} "
            f"Volume transaksi dan indikator tren mendukung kelanjutan momentum kenaikan."
        )
        
        bear_case = (
            f"Pandangan Bearish (Penjual): Waspadai batas Stop Loss di Rp {data.get('stop_loss', 0):.0f}. "
            f"Jika IHSG mengalami konsolidasi atau aksi profit taking, saham berisiko terkoreksi jangka pendek."
        )
        
        return {"bull_case": bull_case, "bear_case": bear_case}

class RiskManagerAgent:
    """Evaluates risk/reward ratio and synthesizes final trading consensus."""
    def evaluate(self, debate: Dict[str, str], data: Dict[str, Any]) -> Dict[str, Any]:
        close = data.get("close_price", 1)
        target = data.get("target_price", 1)
        stop = data.get("stop_loss", 1)
        
        reward = max(0, target - close)
        risk = max(1, close - stop)
        rr_ratio = reward / risk if risk > 0 else 1.0
        
        verdict = "REKOMENDASI BELI (BUY)" if rr_ratio >= 1.5 and data.get("probability", 0) >= 55 else "PERTIMBANGKAN WAIT & SEE"
        
        return {
            "verdict": verdict,
            "risk_reward_ratio": round(rr_ratio, 2),
            "max_downside_pct": round(((close - stop) / close * 100), 2) if close > 0 else 0,
            "max_upside_pct": round(((target - close) / close * 100), 2) if close > 0 else 0
        }

class MultiAgentSystem:
    """
    Multi-Agent Trading Framework inspired by TauricResearch/TradingAgents.
    Orchestrates Technical, Sentiment, Debate, and Risk Manager Agents to output consensus.
    """
    def __init__(self):
        self.technical_agent = TechnicalAnalystAgent()
        self.sentiment_agent = SentimentAnalystAgent()
        self.debate_agent = BullBearDebateAgent()
        self.risk_manager = RiskManagerAgent()

    def generate_consensus(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Runs the 4-agent workflow locally or enhances with LLM synthesis if available."""
        tech_out = self.technical_agent.analyze(data)
        sent_out = self.sentiment_agent.analyze(data)
        debate_out = self.debate_agent.debate(tech_out, sent_out, data)
        risk_out = self.risk_manager.evaluate(debate_out, data)
        
        ticker = data.get("ticker", "SAHAM").replace(".JK", "")
        
        # Build unified synthesis text
        synthesis = (
            f"Konsensus Multi-Agent StockAI ({ticker}):\n"
            f"• [Technical Analyst]: {tech_out}\n"
            f"• [Sentiment Analyst]: {sent_out}\n"
            f"• [Bull Case]: {debate_out['bull_case']}\n"
            f"• [Bear Case]: {debate_out['bear_case']}\n"
            f"• [Risk Manager]: Verdict {risk_out['verdict']} dengan Risk/Reward Ratio {risk_out['risk_reward_ratio']}x."
        )
        
        # Optionally enhance via LLM if available
        llm_enhanced = self._call_llm_synthesis(ticker, data, debate_out, risk_out)
        if llm_enhanced:
            synthesis = llm_enhanced

        return {
            "ticker": ticker,
            "technical_view": tech_out,
            "sentiment_view": sent_out,
            "bull_case": debate_out["bull_case"],
            "bear_case": debate_out["bear_case"],
            "risk_verdict": risk_out["verdict"],
            "risk_reward_ratio": risk_out["risk_reward_ratio"],
            "consensus_summary": synthesis
        }

    def _call_llm_synthesis(self, ticker: str, data: Dict[str, Any], debate: Dict[str, str], risk: Dict[str, Any]) -> str:
        """Helper to invoke LLM proxy for polished natural language synthesis."""
        url = f"{OPENAI_API_BASE}/chat/completions"
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
        
        prompt = (
            f"Kamu adalah Manajer Konsensus Trading Multi-Agent saham BEI untuk {ticker}.\n"
            f"Gabungkan hasil perdebatan Bull vs Bear dan Manajer Risiko berikut menjadi ulasan opini 3 kalimat padat:\n"
            f"- Bull Case: {debate['bull_case']}\n"
            f"- Bear Case: {debate['bear_case']}\n"
            f"- Hasil Risk Manager: {risk['verdict']} (Risk/Reward {risk['risk_reward_ratio']}x).\n"
            f"Tulis dalam bahasa Indonesia profesional tanpa kata sambutan."
        )
        
        payload = {
            "model": "opencode/deepseek-v4-flash-free",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2
        }
        
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=10)
            if res.status_code == 200:
                body = res.json()
                content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
                if content:
                    return content.strip()
        except Exception:
            pass
        return None
