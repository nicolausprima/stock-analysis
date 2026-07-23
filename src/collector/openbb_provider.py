import sys
from pathlib import Path
import pandas as pd
import yfinance as yf
import logging

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

logger = logging.getLogger(__name__)

class OpenBBProvider:
    """
    OpenBB Data Provider wrapper for StockAI.
    Provides unified access to historical data, technical indicators, and market context.
    Falls back gracefully to yfinance / pandas if openbb package is not available.
    """
    def __init__(self):
        self.openbb_available = False
        try:
            from openbb import obb
            self.obb = obb
            self.openbb_available = True
            logger.info("OpenBB Platform SDK loaded successfully.")
        except ImportError:
            logger.info("OpenBB package not installed. Falling back to yfinance data provider.")

    def get_historical_data(self, ticker: str, period: str = "100d") -> pd.DataFrame:
        """
        Fetch historical daily price data for a given ticker.
        """
        if self.openbb_available:
            try:
                # OpenBB SDK call
                res = self.obb.equity.price.historical(symbol=ticker, provider="yfinance")
                df = res.to_df()
                if not df.empty:
                    return df
            except Exception as e:
                logger.warning(f"OpenBB fetch failed for {ticker}: {e}. Falling back to yfinance.")

        # Fallback to direct yfinance
        df_yf = yf.download(ticker, period=period, progress=False)
        if isinstance(df_yf.columns, pd.MultiIndex):
            df_yf.columns = df_yf.columns.get_level_values(0)
        return df_yf

    def get_technical_indicators(self, ticker: str, df: pd.DataFrame = None) -> dict:
        """
        Extract key technical indicators using OpenBB if available, or compute via pandas/ta.
        """
        if df is None or df.empty:
            df = self.get_historical_data(ticker)

        if df.empty:
            return {}

        close_prices = df['Close'].dropna()
        if len(close_prices) < 14:
            return {}

        current_close = float(close_prices.iloc[-1])
        
        # Simple calculations for RSI, SMA, Volatility
        delta = close_prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, 1e-9)
        rsi_series = 100 - (100 / (1 + rs))
        current_rsi = float(rsi_series.iloc[-1]) if not rsi_series.empty else 50.0

        sma_20 = float(close_prices.rolling(20).mean().iloc[-1]) if len(close_prices) >= 20 else current_close
        sma_50 = float(close_prices.rolling(50).mean().iloc[-1]) if len(close_prices) >= 50 else current_close

        volatility = float(close_prices.pct_change().std() * 100)

        return {
            "ticker": ticker,
            "current_close": current_close,
            "rsi_14": round(current_rsi, 2),
            "sma_20": round(sma_20, 2),
            "sma_50": round(sma_50, 2),
            "volatility_pct": round(volatility, 2),
            "openbb_used": self.openbb_available
        }
