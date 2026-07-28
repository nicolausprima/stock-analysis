"""
src/utils/paths.py
Centralized path resolution module for StockAI.
Imports project root and app paths safely across any execution context.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
PRICE_DATA_DIR = RAW_DATA_DIR / "price"

TICKER_LIST_FILE = DATA_DIR / "tickers.txt"
DB_PATH = DATA_DIR / "stock_market.db"
CACHE_FILE = DATA_DIR / "latest_recommendations.json"
