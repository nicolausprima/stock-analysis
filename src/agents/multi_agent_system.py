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

class MacroContextAgent:
    """Agent specialized in evaluating domestic and global macroeconomic regime."""
    def analyze(self, macro_data: Dict[str, Any]) -> str:
        mode = macro_data.get("mode", "NORMAL")
        score = macro_data.get("macro_score", 0.0)
        badge = macro_data.get("mode_badge", "MODE NORMAL")
        
        if mode == "BLOCK":
            return f"Analisis Makro: {badge} (Skor {score:+.1f}). Pasar dalam zona merah/downtrend tinggi. Risiko sistemik membatasi posisi beli."
        elif mode == "CAUTIOUS":
            return f"Analisis Makro: {badge} (Skor {score:+.1f}). Fluktuasi kurs/pasar global menuntut kewaspadaan ekstra. Filter diperketat."
        else:
            return f"Analisis Makro: {badge} (Skor {score:+.1f}). Lingkungan makro kondusif mendukung pergerakan IHSG dan saham domestik."

class BullBearDebateAgent:
    """Simulates a debate between Bull (upside factors) and Bear (risk factors)."""
    def debate(self, tech_summary: str, sent_summary: str, macro_summary: str, data: Dict[str, Any]) -> Dict[str, str]:
        prob = data.get("probability", 50.0)
        ticker = data.get("ticker", "SAHAM").replace(".JK", "")
        
        bull_case = (
            f"Pandangan Bullish (Pembeli): {ticker} memiliki probabilitas AI {prob:.1f}%. {tech_summary} "
            f"{macro_summary} Momentum accumulation mendukung kenaikan lanjutan."
        )
        
        bear_case = (
            f"Pandangan Bearish (Penjual): Waspadai batas Stop Loss di Rp {data.get('stop_loss', 0):.0f}. "
            f"Jika IHSG atau makro bergejolak, saham berisiko mengalami tekanan koreksi."
        )
        
        return {"bull_case": bull_case, "bear_case": bear_case}

class RiskManagerAgent:
    """Evaluates risk/reward ratio and synthesizes final trading consensus."""
    def evaluate(self, debate: Dict[str, str], data: Dict[str, Any], macro_mode: str = "NORMAL") -> Dict[str, Any]:
        close = data.get("close_price", 1)
        target = data.get("target_price", 1)
        stop = data.get("stop_loss", 1)
        prob = data.get("probability", 0)
        
        reward = max(0, target - close)
        risk = max(1, close - stop)
        rr_ratio = reward / risk if risk > 0 else 1.0
        
        min_prob = 80 if macro_mode == "CAUTIOUS" else 55
        
        if macro_mode == "BLOCK":
            verdict = "TAHAN POSISI (RISK-OFF / BLOCK)"
        elif rr_ratio >= 1.5 and prob >= min_prob:
            verdict = "REKOMENDASI BELI (BUY)"
        else:
            verdict = "PERTIMBANGKAN WAIT & SEE"
        
        return {
            "verdict": verdict,
            "risk_reward_ratio": round(rr_ratio, 2),
            "max_downside_pct": round(((close - stop) / close * 100), 2) if close > 0 else 0,
            "max_upside_pct": round(((target - close) / close * 100), 2) if close > 0 else 0
        }

class MultiAgentSystem:
    """
    Multi-Agent Trading Framework inspired by TauricResearch/TradingAgents.
    Orchestrates Technical, Sentiment, Macro, Debate, and Risk Manager Agents to output consensus.
    """
    def __init__(self):
        self.technical_agent = TechnicalAnalystAgent()
        self.sentiment_agent = SentimentAnalystAgent()
        self.macro_agent = MacroContextAgent()
        self.debate_agent = BullBearDebateAgent()
        self.risk_manager = RiskManagerAgent()

    def generate_consensus(self, data: Dict[str, Any], macro_info: Dict[str, Any] = None) -> Dict[str, Any]:
        """Runs the multi-agent consensus workflow."""
        macro_info = macro_info or {}
        macro_mode = macro_info.get("mode", "NORMAL")

        tech_out = self.technical_agent.analyze(data)
        sent_out = self.sentiment_agent.analyze(data)
        macro_out = self.macro_agent.analyze(macro_info)
        debate_out = self.debate_agent.debate(tech_out, sent_out, macro_out, data)
        risk_out = self.risk_manager.evaluate(debate_out, data, macro_mode=macro_mode)
        
        ticker = data.get("ticker", "SAHAM").replace(".JK", "")
        
        synthesis = (
            f"Konsensus Multi-Agent StockAI ({ticker}):\n"
            f"• [Technical Analyst]: {tech_out}\n"
            f"• [Macro Intelligence]: {macro_out}\n"
            f"• [Sentiment Analyst]: {sent_out}\n"
            f"• [Bull Case]: {debate_out['bull_case']}\n"
            f"• [Bear Case]: {debate_out['bear_case']}\n"
            f"• [Risk Manager]: Verdict {risk_out['verdict']} dengan Risk/Reward Ratio {risk_out['risk_reward_ratio']}x."
        )
        
        llm_enhanced = self._call_llm_synthesis(ticker, data, debate_out, risk_out, macro_out)
        if llm_enhanced:
            synthesis = llm_enhanced

        return {
            "ticker": ticker,
            "technical_view": tech_out,
            "sentiment_view": sent_out,
            "macro_view": macro_out,
            "bull_case": debate_out["bull_case"],
            "bear_case": debate_out["bear_case"],
            "risk_verdict": risk_out["verdict"],
            "risk_reward_ratio": risk_out["risk_reward_ratio"],
            "consensus_summary": synthesis
        }

    def _call_llm_synthesis(self, ticker: str, data: Dict[str, Any], debate: Dict[str, str], risk: Dict[str, Any], macro_view: str) -> str:
        """Helper to invoke LLM proxy for polished natural language synthesis."""
        url = f"{OPENAI_API_BASE}/chat/completions"
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
        
        prompt = (
            f"Kamu adalah Manajer Konsensus Trading Multi-Agent saham BEI untuk {ticker}.\n"
            f"Gabungkan perdebatan Bull vs Bear, Konteks Makro, dan Manajer Risiko berikut menjadi ulasan opini 3 kalimat padat:\n"
            f"- Konteks Makro: {macro_view}\n"
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
