import os

from src.utils.paths import (
    CACHE_FILE,
    DATA_DIR,
    DB_PATH,
    PRICE_DATA_DIR,
    PROCESSED_DATA_DIR,
    PROJECT_ROOT,
    RAW_DATA_DIR,
    TICKER_LIST_FILE,
)

__all__ = [
    "BATCH_DELAY_SECONDS",
    "BATCH_SIZE",
    "CACHE_FILE",
    "DATA_DIR",
    "DB_PATH",
    "PRICE_DATA_DIR",
    "PROCESSED_DATA_DIR",
    "PROFIT_THRESHOLD",
    "PROJECT_ROOT",
    "RAW_DATA_DIR",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "TICKERS",
    "TICKER_LIST_FILE",
    "get_allowed_chat_ids",
    "get_telegram_bot_token",
    "get_tickers",
    "reload_tickers",
]

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

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def get_telegram_bot_token() -> str:
    """Baca token per-call agar rotasi env tanpa restart ikut berlaku.

    Token TIDAK boleh di-log/di-print. Import modul ini hanya untuk
    backward-compat; kode baru wajib pakai helper ini.
    """
    return os.getenv("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN or "").strip()


def get_allowed_chat_ids() -> set[str]:
    """Allowlist chat Telegram: TELEGRAM_CHAT_ID + TELEGRAM_ALLOWED_CHAT_IDS (koma)."""
    ids: set[str] = set()
    for raw in (os.getenv("TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID or ""), os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "")):
        for part in str(raw or "").split(","):
            part = part.strip()
            if part:
                ids.add(part)
    return ids

@lru_cache(maxsize=1)
def get_tickers():
    """Read tickers from the tickers.txt file (cached in memory)."""
    if not TICKER_LIST_FILE.exists():
        return []
    with open(TICKER_LIST_FILE, 'r') as f:
        tickers = [line.strip() for line in f if line.strip()]
    return tickers

def reload_tickers():
    """Invalidate cache dan baca ulang tickers.txt (dipanggil setelah file di-update)."""
    get_tickers.cache_clear()
    return get_tickers()

TICKERS = get_tickers()

