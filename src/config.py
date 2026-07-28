import os
from pathlib import Path

# --- DIRECTORY PATHS ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
PRICE_DATA_DIR = RAW_DATA_DIR / "price"

TICKER_LIST_FILE = DATA_DIR / "tickers.txt"
DB_PATH = DATA_DIR / "stock_market.db"
CACHE_FILE = DATA_DIR / "latest_recommendations.json"

# Ensure directories exist
PRICE_DATA_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

# --- DAY TRADING PARAMETERS ---
PROFIT_THRESHOLD = 0.03  # Target Profit +3.0%
BATCH_SIZE = 50          # Batch size for rate-limit safe downloading
BATCH_DELAY_SECONDS = 2  # Sleep delay between HTTP batch requests

from functools import lru_cache

# --- TELEGRAM BOT CONFIGURATION ---
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "7963365997:AAFD9S77X6g9bY6b3rZ1N3H4s0n2v9m1x8Q")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

@lru_cache(maxsize=1)
def get_tickers():
    """Read tickers from the tickers.txt file (cached in memory)."""
    if not TICKER_LIST_FILE.exists():
        return []
    with open(TICKER_LIST_FILE, 'r') as f:
        tickers = [line.strip() for line in f if line.strip()]
    return tickers

TICKERS = get_tickers()

