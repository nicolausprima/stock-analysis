import logging
import os
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "http://127.0.0.1:20128/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL_NAME = os.getenv("LLM_MODEL_NAME", "opencode/deepseek-v4-flash-free")

if "host.docker.internal" in OPENAI_API_BASE and not os.path.exists('/.dockerenv'):
    OPENAI_API_BASE = OPENAI_API_BASE.replace("host.docker.internal", "127.0.0.1")


def _is_llm_configured() -> bool:
    return bool(OPENAI_API_BASE and OPENAI_API_KEY)


def _call_llm(system: str, user: str, temperature: float = 0.2, timeout: int = 15) -> str:
    if not _is_llm_configured():
        return ""
    url = f"{OPENAI_API_BASE}/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "temperature": temperature
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=timeout)
        if res.status_code == 200:
            body = res.json()
            content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
            return (content or "").strip()
    except Exception as e:
        logger.debug(f"LLM call skipped: {e}")
    return ""


def _get_fundamental_context(ticker: str, max_age_days: int = 120) -> str:
    """Konteks fundamental point-in-time (AI-07): tolak snapshot basi/NULL.

    get_fundamental kembalikan None untuk field missing (bukan 0.0:
    PER=0 = sinyal cheap palsu). Snapshot lebih tua dari max_age_days
    dianggap basi -> lapor tidak tersedia.
    """
    try:
        from datetime import date

        from src.database.duckdb_fundamental import get_fundamental
        from src.features.fundamental_features import compute_valuation_score
        fund = get_fundamental(ticker)
        as_of = fund.get("as_of")
        if as_of:
            try:
                age = (date.today() - date.fromisoformat(str(as_of)[:10])).days
                if age > max_age_days:
                    return (f"Data fundamental {ticker} basi (as-of {as_of}, "
                            f"umur {age} hari): tidak dipakai untuk keputusan.")
            except ValueError:
                pass
        per, pbv = fund.get("per"), fund.get("pbv")
        if per is None and pbv is None:
            return "Data fundamental belum tersedia di cache lokal."
        val = compute_valuation_score(
            per if per is not None else float("nan"),
            pbv if pbv is not None else float("nan"),
            fund.get("roe"), fund.get("debt_to_equity")
        )
        notes = ", ".join(val.get("valuation_notes", [])) or "tanpa catatan khusus"
        per_s = f"{per:.1f}x" if per is not None else "n/a"
        pbv_s = f"{pbv:.2f}x" if pbv is not None else "n/a"
        roe = fund.get("roe")
        roe_s = f"{(roe * 100):.1f}%" if roe is not None else "n/a"
        dy = fund.get("dividend_yield")
        dy_s = f"{(dy * 100):.2f}%" if dy is not None else "n/a"
        return (
            f"PER {per_s}, PBV {pbv_s}, ROE {roe_s}, Div Yield {dy_s}. "
            f"Skor valuasi {val.get('valuation_score', 0):+.1f}. Catatan: {notes}."
        )
    except Exception:
        pass
    return "Data fundamental belum tersedia di cache lokal."


def _get_shap_context(ticker: str, features: dict[str, Any]) -> str:
    try:
        import pandas as pd

        from src.explainability.shap_explainer import (
            _get_feature_columns,
            explain_single_prediction,
        )
        cols = _get_feature_columns()
        clean_row = {}
        for c in cols:
            val = features.get(c)
            if val is None:
                if c == "RSI_14":
                    val = features.get("rsi")
                elif c == "SMA_20":
                    val = features.get("sma20") or features.get("sma_20")
                elif c == "SMA_50":
                    val = features.get("sma50") or features.get("sma_50")
                elif c == "ATR_14":
                    val = features.get("atr") or features.get("atr_14")
                elif c == "MACD_Diff":
                    val = features.get("macd_diff")
            # AI-06: missing -> NaN (explain_single_prediction menolak),
            # bukan 0.0 (RSI=0/MACD=0 palsu).
            try:
                clean_row[c] = float(val) if val is not None else float("nan")
            except (ValueError, TypeError):
                clean_row[c] = float("nan")

        df = pd.DataFrame([clean_row])
        shp = explain_single_prediction(ticker, df)
        parts = []
        for c in shp.get("top_contributors", [])[:3]:
            arah = "mendukung beli" if c["direction"] == "positive" else "menekan sinyal"
            parts.append(f"{c['feature']} {arah} (SHAP {c['shap_value']:+.3f})")
        if parts:
            return "Driver model utama: " + "; ".join(parts) + "."
    except Exception as e:
        logger.debug(f"SHAP context skipped: {e}")
    return ""


class FundamentalAnalystAgentV2:
    def analyze(self, ticker: str, data: dict[str, Any]) -> str:
        fund_ctx = _get_fundamental_context(ticker)
        if _is_llm_configured():
            out = _call_llm(
                "Kamu analis fundamental saham BEI. Jawab 2 kalimat padat Bahasa Indonesia.",
                f"Ticker {ticker}. Konteks: {fund_ctx} Beri opini valuasi dan kualitas bisnis."
            )
            if out:
                return f"Analisis Fundamental: {out}"
        return f"Analisis Fundamental: {fund_ctx}"


class TechnicalAnalystAgentV2:
    def analyze(self, data: dict[str, Any]) -> str:
        rsi = data.get("rsi", 50.0)
        macd = data.get("macd_signal", "BULLISH")
        trend = data.get("trend", "UPTREND")
        close = data.get("close_price", 0)
        target = data.get("target_price", 0)
        upside = ((target - close) / close * 100) if close > 0 else 0
        return (
            f"Analisis Teknikal: Tren {trend} dengan RSI {rsi:.1f}. "
            f"Sinyal MACD {macd}. Potensi teknikal +{upside:.1f}% ke Rp {target:.0f}."
        )


class SentimentAnalystAgentV2:
    def analyze(self, data: dict[str, Any]) -> str:
        status = data.get("sentiment_status", "NETRAL")
        impact = data.get("sentiment_impact", "NETRAL")
        highlights = data.get("sentiment_highlights", []) or []
        tail = f" Katalis: {', '.join(highlights[:2])}." if highlights else ""
        if _is_llm_configured() and highlights:
            out = _call_llm(
                "Kamu analis sentimen pasar saham Indonesia. Jawab 2 kalimat padat.",
                f"Status {status}, dampak {impact}. Headline: {'; '.join(highlights[:4])}"
            )
            if out:
                return f"Analisis Sentimen: {out}"
        return f"Analisis Sentimen: Status {status} dampak {impact}.{tail}"


class AdversarialDebateAgentV2:
    def debate(self, tech: str, fund: str, sent: str, macro: str, data: dict[str, Any], rounds: int = 2) -> dict[str, str]:
        ticker = data.get("ticker", "SAHAM").replace(".JK", "")
        prob = data.get("probability", 50.0)
        bull_ctx = f"{tech} {fund} {sent} {macro}"
        bear_ctx = f"Stop Rp {data.get('stop_loss', 0):.0f}, prob {prob:.1f}%."
        bull, bear = "", ""
        if _is_llm_configured():
            for r in range(rounds):
                b = _call_llm(
                    "Kamu pihak Bullish debat saham BEI. 2 kalimat argumen beli.",
                    f"Ronde {r+1} untuk {ticker}. Pro: {bull_ctx}. Kontra sebelumnya: {bear or '-'}."
                )
                if b:
                    bull = b
                br = _call_llm(
                    "Kamu pihak Bearish debat saham BEI. 2 kalimat argumen risiko.",
                    f"Ronde {r+1} untuk {ticker}. Risiko: {bear_ctx}. Pro sebelumnya: {bull or '-'}."
                )
                if br:
                    bear = br
        if not bull:
            bull = f"Bullish {ticker}: prob AI {prob:.1f}%. {tech} {macro} Momentum akumulasi mendukung lanjut naik."
        if not bear:
            bear = f"Bearish {ticker}: waspadai stop Rp {data.get('stop_loss', 0):.0f}. Koreksi jika makro goyah."
        return {"bull_case": bull, "bear_case": bear}


class RiskManagerAgentV2:
    def evaluate(self, debate: dict[str, str], data: dict[str, Any], macro_mode: str = "NORMAL") -> dict[str, Any]:
        close = data.get("close_price", 1)
        target = data.get("target_price", 1)
        stop = data.get("stop_loss", 1)
        prob = data.get("probability", 0)
        reward = max(0, target - close)
        risk = max(1, close - stop)
        rr = reward / risk if risk > 0 else 1.0
        min_prob = 80 if macro_mode == "CAUTIOUS" else 55
        if macro_mode == "BLOCK":
            verdict = "TAHAN POSISI (RISK-OFF / BLOCK)"
        elif rr >= 1.5 and prob >= min_prob:
            verdict = "REKOMENDASI BELI (BUY)"
        else:
            verdict = "PERTIMBANGKAN WAIT & SEE"
        return {
            "verdict": verdict,
            "risk_reward_ratio": round(rr, 2),
            "max_downside_pct": round(((close - stop) / close * 100), 2) if close > 0 else 0,
            "max_upside_pct": round(((target - close) / close * 100), 2) if close > 0 else 0
        }


class MultiAgentSystemV2:
    def __init__(self):
        self.technical = TechnicalAnalystAgentV2()
        self.fundamental = FundamentalAnalystAgentV2()
        self.sentiment = SentimentAnalystAgentV2()
        self.debate = AdversarialDebateAgentV2()
        self.risk = RiskManagerAgentV2()

    def generate_consensus(self, data: dict[str, Any], macro_info: dict[str, Any] | None = None) -> dict[str, Any]:
        macro_info = macro_info or {}
        macro_mode = macro_info.get("mode", "NORMAL")
        ticker = data.get("ticker", "SAHAM").replace(".JK", "")
        tech_out = self.technical.analyze(data)
        fund_out = self.fundamental.analyze(ticker, data)
        sent_out = self.sentiment.analyze(data)
        macro_out = str(macro_info.get("mode_badge", macro_mode))
        debate_out = self.debate.debate(tech_out, fund_out, sent_out, macro_out, data)
        risk_out = self.risk.evaluate(debate_out, data, macro_mode=macro_mode)
        shap_ctx = _get_shap_context(ticker, data)
        synthesis = (
            f"Konsensus Multi-Agent V2 ({ticker}):\n"
            f"- [Teknikal]: {tech_out}\n"
            f"- [Fundamental]: {fund_out}\n"
            f"- [Sentimen]: {sent_out}\n"
            f"- [Makro]: {macro_out}\n"
            f"- [Bull]: {debate_out['bull_case']}\n"
            f"- [Bear]: {debate_out['bear_case']}\n"
            f"- [Risk]: {risk_out['verdict']} RR {risk_out['risk_reward_ratio']}x."
        )
        if shap_ctx:
            synthesis += f"\n- [Explainability]: {shap_ctx}"
        llm_final = ""
        if _is_llm_configured():
            llm_final = _call_llm(
                "Kamu manajer konsensus trading saham BEI. Tulis 3 kalimat Bahasa Indonesia profesional, tanpa sapaan.",
                f"Bull: {debate_out['bull_case']}\nBear: {debate_out['bear_case']}\n"
                f"Risk: {risk_out['verdict']} RR {risk_out['risk_reward_ratio']}x.\nFundamental: {fund_out}"
            )
        if llm_final:
            synthesis = llm_final
        return {
            "ticker": ticker,
            "technical_view": tech_out,
            "fundamental_view": fund_out,
            "sentiment_view": sent_out,
            "macro_view": macro_out,
            "bull_case": debate_out["bull_case"],
            "bear_case": debate_out["bear_case"],
            "risk_verdict": risk_out["verdict"],
            "risk_reward_ratio": risk_out["risk_reward_ratio"],
            "consensus_summary": synthesis,
            "llm_enabled": _is_llm_configured(),
            "engine": "multi-agent-v2"
        }
