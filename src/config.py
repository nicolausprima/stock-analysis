import os
from src.utils.paths import (
    PROJECT_ROOT, DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR,
    PRICE_DATA_DIR, TICKER_LIST_FILE, DB_PATH, CACHE_FILE
)

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

