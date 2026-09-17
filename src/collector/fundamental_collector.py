"""
Fundamental data collector.
Fetch PER, PBV, ROE etc using yfinance and store to DuckDB fundamental store.
"""
import yfinance as yf
from src.config import TICKERS
from src.database.duckdb_fundamental import save_fundamental

def run_fundamental_collection():
    print(f"[Fundamental] Memulai pengunduhan data fundamental {len(TICKERS)} saham...")
    for t in TICKERS:
        try:
            ticker = yf.Ticker(t)
            info = ticker.info
            
            data = {
                "per": info.get("trailingPE", 0.0),
                "pbv": info.get("priceToBook", 0.0),
                "roe": info.get("returnOnEquity", 0.0),
                "debt_to_equity": info.get("debtToEquity", 0.0),
                "market_cap": info.get("marketCap", 0.0),
                "dividend_yield": info.get("dividendYield", 0.0),
                "revenue_growth": info.get("revenueGrowth", 0.0)
            }
            save_fundamental(t, data)
            print(f"  [OK] Fundamental {t}")
        except Exception as e:
            print(f"  [ERROR] {t}: {e}")
    print("[Fundamental] Selesai.")

if __name__ == "__main__":
    run_fundamental_collection()
