"""
DuckDB-backed market data store replacing SQLite for high-performance OLAP.
Optimized for 700+ ticker IDX universe with vectorized operations.
"""
import duckdb
import pandas as pd
import polars as pl
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.utils.paths import DATA_DIR

DUCKDB_PATH = DATA_DIR / "stock_market.duckdb"

_connection = None

def get_duckdb_connection() -> duckdb.DuckDBPyConnection:
    """Get or create persistent DuckDB connection with optimized settings."""
    global _connection
    if _connection is None:
        _connection = duckdb.connect(str(DUCKDB_PATH))
        _connection.execute("PRAGMA enable_progress_bar=false")
        _connection.execute("SET threads TO 4")
        _connection.execute("SET memory_limit = '2GB'")
        _init_schema()
    return _connection

def _init_schema():
    """Initialize DuckDB schema for daily prices and features."""
    conn = get_duckdb_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_prices (
            ticker VARCHAR,
            date DATE,
            open DOUBLE,
            high DOUBLE,
            low DOUBLE,
            close DOUBLE,
            volume DOUBLE,
            PRIMARY KEY (ticker, date)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_daily_prices_date ON daily_prices(date)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_daily_prices_ticker ON daily_prices(ticker)
    """)

def save_daily_prices_polars(df: pl.DataFrame):
    """Save daily prices from Polars DataFrame to DuckDB (vectorized bulk insert)."""
    if df.is_empty():
        return
    
    conn = get_duckdb_connection()
    
    df_write = df.with_columns([
        pl.col("date").cast(pl.Date),
        pl.col("ticker").cast(pl.Utf8).str.strip_chars()
    ]).filter(pl.col("close") > 0)
    
    if df_write.is_empty():
        return
    
    conn.register("temp_prices", df_write)
    conn.execute("""
        INSERT OR REPLACE INTO daily_prices (ticker, date, open, high, low, close, volume)
        SELECT ticker, date, open, high, low, close, volume FROM temp_prices
    """)
    conn.unregister("temp_prices")

def get_ticker_history_polars(ticker: str, limit_days: int = 100) -> pl.DataFrame:
    """Get ticker history from DuckDB as Polars DataFrame (vectorized)."""
    conn = get_duckdb_connection()
    query = """
        SELECT date, open, high, low, close, volume
        FROM daily_prices
        WHERE ticker = ?
        ORDER BY date DESC
        LIMIT ?
    """
    result = conn.execute(query, [ticker.upper(), limit_days]).pl()
    
    if not result.is_empty():
        result = result.sort("date")
    return result

def get_all_histories_polars(limit_days: int = 100) -> dict[str, pl.DataFrame]:
    """Get all ticker histories in one bulk query, return as dict of Polars DataFrames."""
    conn = get_duckdb_connection()
    query = """
        SELECT ticker, date, open, high, low, close, volume
        FROM daily_prices
        ORDER BY ticker, date ASC
    """
    full_df = conn.execute(query).pl()
    
    if full_df.is_empty():
        return {}
    
    result = {}
    for ticker_name, group in full_df.partition_by("ticker", as_dict=True).items():
        clean_t = str(ticker_name).strip()
        df = group.tail(limit_days).drop("ticker").sort("date")
        result[clean_t] = df
    
    return result

def get_universe_date_range() -> tuple:
    """Get min/max date in database."""
    conn = get_duckdb_connection()
    result = conn.execute("SELECT MIN(date), MAX(date) FROM daily_prices").fetchone()
    return result if result else (None, None)

def get_ticker_count() -> int:
    """Get count of unique tickers in database."""
    conn = get_duckdb_connection()
    result = conn.execute("SELECT COUNT(DISTINCT ticker) FROM daily_prices").fetchone()
    return result[0] if result else 0

def close_connection():
    """Close persistent connection."""
    global _connection
    if _connection:
        _connection.close()
        _connection = None


# --- Polars Feature Pipeline ---

def add_technical_indicators_polars(df: pl.DataFrame) -> pl.DataFrame:
    """
    Add technical indicators using Polars expressions (vectorized, no Python loops).
    """
    df = df.sort("date")
    
    # Ensure we have required columns
    required = ["open", "high", "low", "close", "volume"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
    
    return df.with_columns([
        # OBV
        pl.when(pl.col("close").diff() > 0)
        .then(pl.col("volume"))
        .when(pl.col("close").diff() < 0)
        .then(-pl.col("volume"))
        .otherwise(0)
        .cum_sum()
        .alias("OBV"),
        
        # Accumulation/Distribution Index
        (
            ((pl.col("close") - pl.col("low")) - (pl.col("high") - pl.col("close")))
            / (pl.col("high") - pl.col("low") + 1e-9)
            * pl.col("volume")
        ).cum_sum()
        .alias("ADI"),
        
        # VWAP (session VWAP - cumulative)
        (pl.col("close") * pl.col("volume")).cum_sum() / pl.col("volume").cum_sum()
        .alias("VWAP"),
        
        # RSI 14
        _rsi_polars(pl.col("close"), 14).alias("RSI_14"),
        
        # MACD
        * _macd_polars(pl.col("close")),
        
        # Bollinger Bands
        * _bollinger_polars(pl.col("close"), 20, 2),
        
        # ATR 14
        _atr_polars(pl.col("high"), pl.col("low"), pl.col("close"), 14).alias("ATR_14"),
        
        # ADX 14
        * _adx_polars(pl.col("high"), pl.col("low"), pl.col("close"), 14),
        
        # SMA
        pl.col("close").rolling_mean(20).alias("SMA_20"),
        pl.col("close").rolling_mean(50).alias("SMA_50"),
        
        # RVOL & Volume Z-Score
        (pl.col("volume") / pl.col("volume").rolling_mean(20).fill_null(1)).alias("RVOL"),
        (
            (pl.col("volume") - pl.col("volume").rolling_mean(20))
            / (pl.col("volume").rolling_std(20).fill_null(1) + 1e-9)
        ).alias("Volume_Z"),
        
        # Stochastic
        * _stochastic_polars(pl.col("high"), pl.col("low"), pl.col("close"), 14, 3),
        
        # MFI
        _mfi_polars(pl.col("high"), pl.col("low"), pl.col("close"), pl.col("volume"), 14).alias("MFI_14"),
        
        # EMA
        pl.col("close").ewm_mean(span=12, adjust=False).alias("EMA_12"),
        pl.col("close").ewm_mean(span=26, adjust=False).alias("EMA_26"),
        
        # Williams %R
        _williams_r_polars(pl.col("high"), pl.col("low"), pl.col("close"), 14).alias("Williams_R"),
        
        # CCI
        _cci_polars(pl.col("high"), pl.col("low"), pl.col("close"), 20).alias("CCI_20"),
    ]).fill_null(0)

# --- Helper functions for Polars expressions ---

def _rsi_polars(close: pl.Expr, window: int = 14) -> pl.Expr:
    delta = close.diff()
    gain = pl.when(delta > 0).then(delta).otherwise(0)
    loss = pl.when(delta < 0).then(-delta).otherwise(0)
    avg_gain = gain.rolling_mean(window)
    avg_loss = loss.rolling_mean(window)
    rs = avg_gain / (avg_loss + 1e-9)
    return 100 - (100 / (1 + rs))

def _macd_polars(close: pl.Expr) -> tuple:
    ema12 = close.ewm_mean(span=12, adjust=False)
    ema26 = close.ewm_mean(span=26, adjust=False)
    macd = ema12 - ema26
    signal = macd.ewm_mean(span=9, adjust=False)
    diff = macd - signal
    return macd.alias("MACD"), signal.alias("MACD_Signal"), diff.alias("MACD_Diff")

def _bollinger_polars(close: pl.Expr, window: int = 20, std_dev: float = 2) -> tuple:
    mid = close.rolling_mean(window)
    std = close.rolling_std(window)
    high = mid + std_dev * std
    low = mid - std_dev * std
    return high.alias("BB_High"), low.alias("BB_Low"), mid.alias("BB_Mid")

def _atr_polars(high: pl.Expr, low: pl.Expr, close: pl.Expr, window: int = 14) -> pl.Expr:
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pl.max_horizontal(tr1, tr2, tr3)
    return tr.rolling_mean(window)

def _adx_polars(high: pl.Expr, low: pl.Expr, close: pl.Expr, window: int = 14) -> tuple:
    # Simplified ADX - using +DI/-DI
    up_move = high.diff()
    down_move = -low.diff()
    
    plus_dm = pl.when((up_move > down_move) & (up_move > 0)).then(up_move).otherwise(0)
    minus_dm = pl.when((down_move > up_move) & (down_move > 0)).then(down_move).otherwise(0)
    
    atr = _atr_polars(high, low, close, window)
    
    plus_di = 100 * (plus_dm.rolling_mean(window) / (atr + 1e-9))
    minus_di = 100 * (minus_dm.rolling_mean(window) / (atr + 1e-9))
    
    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di + 1e-9))
    adx = dx.rolling_mean(window)
    
    return (
        adx.fill_null(20).alias("ADX_14"),
        plus_di.fill_null(20).alias("ADX_Pos"),
        minus_di.fill_null(20).alias("ADX_Neg"),
    )

def _stochastic_polars(high: pl.Expr, low: pl.Expr, close: pl.Expr, window: int = 14, smooth: int = 3) -> tuple:
    lowest_low = low.rolling_min(window)
    highest_high = high.rolling_max(window)
    k = 100 * ((close - lowest_low) / (highest_high - lowest_low + 1e-9))
    d = k.rolling_mean(smooth)
    return k.fill_null(50).alias("Stoch_K"), d.fill_null(50).alias("Stoch_D")

def _mfi_polars(high: pl.Expr, low: pl.Expr, close: pl.Expr, volume: pl.Expr, window: int = 14) -> pl.Expr:
    typical_price = (high + low + close) / 3
    money_flow = typical_price * volume
    
    tp_diff = typical_price.diff()
    pos_flow = pl.when(tp_diff > 0).then(money_flow).otherwise(0)
    neg_flow = pl.when(tp_diff < 0).then(money_flow).otherwise(0)
    
    pos_mf = pos_flow.rolling_sum(window)
    neg_mf = neg_flow.rolling_sum(window)
    
    mfi = 100 - (100 / (1 + pos_mf / (neg_mf + 1e-9)))
    return mfi.fill_null(50)

def _williams_r_polars(high: pl.Expr, low: pl.Expr, close: pl.Expr, window: int = 14) -> pl.Expr:
    highest_high = high.rolling_max(window)
    lowest_low = low.rolling_min(window)
    return -100 * ((highest_high - close) / (highest_high - lowest_low + 1e-9)).fill_null(-50)

def _cci_polars(high: pl.Expr, low: pl.Expr, close: pl.Expr, window: int = 20) -> pl.Expr:
    typical_price = (high + low + close) / 3
    sma_tp = typical_price.rolling_mean(window)
    mean_dev = (typical_price - sma_tp).abs().rolling_mean(window)
    return ((typical_price - sma_tp) / (0.015 * mean_dev + 1e-9)).fill_null(0)