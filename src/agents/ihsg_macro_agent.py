import logging
import pandas as pd
import yfinance as yf
from typing import Dict, Any
from src.agents.news_macro_agent import NewsMacroAgent

logger = logging.getLogger(__name__)

# Pemetaan 11 Sektor Utama Bursa Efek Indonesia (BEI)
IDX_SECTOR_MAP = {
    "Energi": ["ADRO", "PTBA", "MEDC", "AKRA", "PGAS", "ITMG", "INDY", "DOID", "ENRG", "BUMI", "ELSA", "MBMA"],
    "Finansial": ["BBCA", "BBRI", "BMRI", "BBNI", "BRIS", "BBTN", "BDMN", "BNGA", "MEGA", "ARTO", "BTPS"],
    "Bahan Baku": ["MDKA", "INCO", "ANTM", "TPIA", "BRPT", "INKP", "TKIM", "AMMN", "NCKL", "NSSS", "TINS"],
    "Infrastruktur": ["TLKM", "ISAT", "EXCL", "JSMR", "TOWR", "TBIG", "PGEO", "CENT", "BREN"],
    "Konsumer Primer": ["ICBP", "INDF", "UNVR", "MYOR", "CPIN", "JPFA", "KLBF", "AMRT", "CMRY", "GGRM", "HMSP"],
    "Konsumer Non-Primer": ["ASII", "ACES", "MAPI", "ERAA", "AUTO", "MAPA", "RALS"],
    "Kesehatan": ["KLBF", "MIKA", "HEAL", "SILO", "SIDO", "PRDA", "TSPC"],
    "Teknologi": ["GOTO", "BUKA", "EMTK", "MTDL", "WIFI", "DMMX"],
    "Properti & Real Estate": ["BSDE", "CTRA", "PWON", "SMRA", "ASRI", "DILD", "SSIA", "KIJA"],
    "Perindustrian": ["UNTR", "HEXA", "MARK", "IMAS"],
    "Transportasi & Logistik": ["SMDR", "TMAS", "BIRD", "GIAA", "ASSA"]
}

def get_ticker_sector(ticker: str) -> str:
    """Mengembalikan sektor BEI dari sebuah kode saham."""
    clean = ticker.upper().replace(".JK", "").strip()
    for sector, tickers in IDX_SECTOR_MAP.items():
        if clean in tickers:
            return sector
    return "Lainnya"

class IHSGMacroAgent:
    """
    IHSG Macro Intelligence & Sector Rotation Agent.
    Evaluates global macro indicators, domestic currency, commodity movements,
    IHSG technical indicators, sector momentum rotation, and economic news sentiment.
    """

    def __init__(self):
        self.news_agent = NewsMacroAgent()

    def evaluate_sector_rotation(self) -> Dict[str, Any]:
        """Menghitung momentum rotasi 11 sektor BEI untuk menemukan Leading Sectors."""
        sector_scores = {}
        try:
            # Evaluasi momentum sektor berdasarkan pergerakan saham jangkar (anchor stocks)
            for sector, tickers in IDX_SECTOR_MAP.items():
                anchor = f"{tickers[0]}.JK"
                try:
                    df = yf.download(anchor, period="5d", progress=False)
                    if not df.empty and len(df) >= 2:
                        close_col = df['Close'].iloc[:, 0] if isinstance(df.columns, pd.MultiIndex) else df['Close']
                        p_now = float(close_col.iloc[-1])
                        p_prev = float(close_col.iloc[0])
                        ret_5d = ((p_now - p_prev) / p_prev) * 100
                        sector_scores[sector] = round(ret_5d, 2)
                    else:
                        sector_scores[sector] = 0.0
                except Exception:
                    sector_scores[sector] = 0.0
        except Exception as e:
            logger.warning(f"Error evaluating sector rotation: {e}")

        # Urutkan sektor dari momentum tertinggi ke terendah
        sorted_sectors = sorted(sector_scores.items(), key=lambda x: x[1], reverse=True)
        leading = [s[0] for s in sorted_sectors[:3]] if sorted_sectors else ["Finansial", "Energi", "Bahan Baku"]
        
        return {
            "leading_sectors": leading,
            "sector_rankings": dict(sorted_sectors)
        }

    def evaluate(self, skip_news: bool = False, skip_sectors: bool = False) -> Dict[str, Any]:
        """Perform comprehensive macro regime evaluation.
        
        Args:
            skip_news: Skip economic news sentiment analysis (faster).
            skip_sectors: Skip sector rotation analysis (faster, avoids 11 yfinance calls).
        """
        logger.info("[MACRO AGENT] Initiating global & domestic macro evaluation...")
        
        details = []
        score = 0.0

        # 1. USD/IDR Currency Check
        try:
            usd_idr = yf.download('USDIDR=X', period='5d', progress=False)
            if not usd_idr.empty and len(usd_idr) >= 2:
                close_col = usd_idr['Close'].iloc[:, 0] if isinstance(usd_idr.columns, pd.MultiIndex) else usd_idr['Close']
                last_rate = float(close_col.iloc[-1])
                prev_rate = float(close_col.iloc[-2])
                chg_pct = ((last_rate - prev_rate) / prev_rate) * 100

                if chg_pct > 0.2:
                    score -= 1.0
                    details.append(f"• USD/IDR: Rp {last_rate:,.0f} (+{chg_pct:.2f}% Melemah) ⚠️")
                elif chg_pct < -0.2:
                    score += 1.0
                    details.append(f"• USD/IDR: Rp {last_rate:,.0f} ({chg_pct:.2f}% Menguat) ✅")
                else:
                    details.append(f"• USD/IDR: Rp {last_rate:,.0f} (Stabil) ➖")
        except Exception as e:
            logger.warning(f"Failed to fetch USD/IDR data: {e}")

        # 2. DXY Dollar Index
        try:
            dxy = yf.download('DX-Y.NYB', period='5d', progress=False)
            if not dxy.empty and len(dxy) >= 2:
                close_col = dxy['Close'].iloc[:, 0] if isinstance(dxy.columns, pd.MultiIndex) else dxy['Close']
                last_dxy = float(close_col.iloc[-1])
                prev_dxy = float(close_col.iloc[-2])
                chg_dxy = ((last_dxy - prev_dxy) / prev_dxy) * 100

                if chg_dxy > 0.3:
                    score -= 1.0
                    details.append(f"• DXY (US Dollar): {last_dxy:.2f} (+{chg_dxy:.2f}%) ⚠️")
                elif chg_dxy < -0.3:
                    score += 1.0
                    details.append(f"• DXY (US Dollar): {last_dxy:.2f} ({chg_dxy:.2f}%) ✅")
        except Exception as e:
            logger.warning(f"Failed to fetch DXY data: {e}")

        # 3. Asian Markets (Nikkei, Hang Seng, STI)
        try:
            asia_tickers = ['^N225', '^HSI', '^STI']
            asia_data = yf.download(asia_tickers, period='5d', progress=False)
            if not asia_data.empty:
                asia_returns = []
                for tk in asia_tickers:
                    try:
                        col = asia_data['Close'][tk] if isinstance(asia_data.columns, pd.MultiIndex) else asia_data['Close']
                        if len(col.dropna()) >= 2:
                            r = ((float(col.dropna().iloc[-1]) - float(col.dropna().iloc[-2])) / float(col.dropna().iloc[-2])) * 100
                            asia_returns.append(r)
                    except Exception:
                        pass
                if asia_returns:
                    avg_asia = sum(asia_returns) / len(asia_returns)
                    if avg_asia >= 0.3:
                        score += 1.0
                        details.append(f"• Bursa Asia (Nikkei/HSI/STI): Rata-rata +{avg_asia:.2f}% ✅")
                    elif avg_asia <= -0.3:
                        score -= 1.0
                        details.append(f"• Bursa Asia (Nikkei/HSI/STI): Rata-rata {avg_asia:.2f}% ⚠️")
                    else:
                        details.append(f"• Bursa Asia (Nikkei/HSI/STI): Flat ({avg_asia:+.2f}%) ➖")
        except Exception as e:
            logger.warning(f"Failed to fetch Asian market data: {e}")

        # 4. US Markets (S&P 500 & NASDAQ)
        try:
            us_tickers = ['^GSPC', '^IXIC']
            us_data = yf.download(us_tickers, period='5d', progress=False)
            if not us_data.empty:
                us_returns = []
                for tk in us_tickers:
                    try:
                        col = us_data['Close'][tk] if isinstance(us_data.columns, pd.MultiIndex) else us_data['Close']
                        if len(col.dropna()) >= 2:
                            r = ((float(col.dropna().iloc[-1]) - float(col.dropna().iloc[-2])) / float(col.dropna().iloc[-2])) * 100
                            us_returns.append(r)
                    except Exception:
                        pass
                if us_returns:
                    avg_us = sum(us_returns) / len(us_returns)
                    if avg_us >= 0.3:
                        score += 1.0
                        details.append(f"• Bursa Wall St (S&P500/NASDAQ): Rata-rata +{avg_us:.2f}% ✅")
                    elif avg_us <= -0.3:
                        score -= 1.0
                        details.append(f"• Bursa Wall St (S&P500/NASDAQ): Rata-rata {avg_us:.2f}% ⚠️")
        except Exception as e:
            logger.warning(f"Failed to fetch US market data: {e}")

        # 5. IHSG Technical Index Guard (^JKSE)
        try:
            ihsg = yf.download('^JKSE', period='50d', progress=False)
            if not ihsg.empty and len(ihsg) >= 20:
                close_col = ihsg['Close'].iloc[:, 0] if isinstance(ihsg.columns, pd.MultiIndex) else ihsg['Close']
                last_price = float(close_col.iloc[-1])
                sma20 = float(close_col.rolling(20).mean().iloc[-1])

                if last_price < sma20:
                    score -= 1.5
                    details.append(f"• Teknikal IHSG: {last_price:.1f} < SMA20 {sma20:.1f} (Downtrend) ⚠️")
                else:
                    score += 1.0
                    details.append(f"• Teknikal IHSG: {last_price:.1f} > SMA20 {sma20:.1f} (Uptrend) ✅")
        except Exception as e:
            logger.warning(f"Failed to fetch IHSG technical data: {e}")

        # 6. Economic News Sentiment Agent
        news_sentiment = {"score": 0.0, "label": "NETRAL", "headlines": []}
        if not skip_news:
            try:
                headlines = self.news_agent.fetch_news_headlines(limit=7)
                news_eval = self.news_agent.evaluate_sentiment(headlines)
                news_sentiment = news_eval
                news_score = news_eval.get("score", 0.0)

                if news_score >= 0.2:
                    score += 1.0
                    details.append(f"• Sentimen Berita Makro: {news_eval.get('label', 'POSITIF')} (+{news_score:.2f}) ✅")
                elif news_score <= -0.2:
                    score -= 1.0
                    details.append(f"• Sentimen Berita Makro: {news_eval.get('label', 'NEGATIF')} ({news_score:.2f}) ⚠️")
                else:
                    details.append(f"• Sentimen Berita Makro: NETRAL (0.0) ➖")
            except Exception as e:
                logger.warning(f"Failed to evaluate news sentiment: {e}")

        # Determine Market Mode
        if score >= 2.0:
            mode = "NORMAL"
            mode_badge = "🟢 MODE NORMAL (Pasar Kondusif)"
            prob_threshold = 0.70
            stop_loss_pct = 0.015
        elif score <= -2.0:
            mode = "BLOCK"
            mode_badge = "🔴 MODE BLOCK (Pasar High Risk / Downtrend)"
            prob_threshold = 0.85
            stop_loss_pct = 0.010
        else:
            mode = "CAUTIOUS"
            mode_badge = "🟡 MODE CAUTIOUS (Waspada / Konsolidasi)"
            prob_threshold = 0.80
            stop_loss_pct = 0.010

        # 7. Sector Rotation Intelligence
        # Dilewati saat skip_sectors=True (mode cepat BSJP/fresh-scan) agar tidak menambah 11x download yfinance
        if skip_sectors:
            sector_rotation = {"leading_sectors": [], "sector_rankings": {}}
        else:
            sector_rotation = self.evaluate_sector_rotation()
        leading_sec = ", ".join(sector_rotation.get("leading_sectors", [])[:3])
        if leading_sec:
            details.append(f"• Sektor Terkuat (Inflow): {leading_sec} ⚡")

        return {
            "status": "success",
            "mode": mode,
            "mode_badge": mode_badge,
            "macro_score": round(score, 1),
            "prob_threshold": prob_threshold,
            "stop_loss_pct": stop_loss_pct,
            "details": details,
            "news_sentiment": news_sentiment,
            "sector_rotation": sector_rotation
        }
