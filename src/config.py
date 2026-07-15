import os
from pathlib import Path

# --- DIRECTORY PATHS ---
# Root directory of the project
PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
PRICE_DATA_DIR = RAW_DATA_DIR / "price"

TICKER_LIST_FILE = DATA_DIR / "tickers.txt"

# Ensure directories exist
PRICE_DATA_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

# --- DAY TRADING PARAMETERS ---
# Profit threshold to classify a trade as 'Buy' (1)
# e.g., 0.015 means we expect a 1.5% return from Open to Close
PROFIT_THRESHOLD = 0.015

def get_tickers():
    """Read tickers from the tickers.txt file."""
    if not TICKER_LIST_FILE.exists():
        return []
    with open(TICKER_LIST_FILE, 'r') as f:
        tickers = [line.strip() for line in f if line.strip()]
    return tickers

# Global variable that can be imported
TICKERS = get_tickers()
