import time
import calendar
import pandas as pd
import yfinance as yf
from fastapi import APIRouter, HTTPException

router = APIRouter()

# In-memory TTL Cache untuk chart data
_chart_cache = {}
CACHE_TTL_INTRADAY = 60    # 1 menit
CACHE_TTL_DAILY = 300      # 5 menit
CACHE_MAX_ENTRIES = 500    # Batasi ukuran cache agar memori tidak bocor

@router.get("/chart/{ticker}")
def get_chart_data(ticker: str, days: int = 60):
    """
    Mengambil data historis untuk chart.
    - days=1  → intraday per 5 menit, time = Unix timestamp (int)
    - days>1  → harian, time = 'YYYY-MM-DD' (string)
    Format sesuai TradingView Lightweight Charts.
    """
    clean_ticker = ticker.upper().strip()
    cache_key = f"{clean_ticker}_{days}"
    now = time.time()
    ttl = CACHE_TTL_INTRADAY if days == 1 else CACHE_TTL_DAILY

    if cache_key in _chart_cache:
        cached_time, cached_result = _chart_cache[cache_key]
        if now - cached_time < ttl:
            return cached_result
        else:
            # Entri kedaluwarsa: hapus agar tidak menumpuk
            del _chart_cache[cache_key]

    try:
        if clean_ticker == "IHSG":
            yf_ticker = "^JKSE"
        else:
            yf_ticker = clean_ticker if ".JK" in clean_ticker or clean_ticker.startswith("^") else f"{clean_ticker}.JK"

        if days == 1:
            # Intraday: data per 5 menit hari ini
            df = yf.download(yf_ticker, period="1d", interval="5m", progress=False)
        else:
            period_str = f"{days}d"
            df = yf.download(yf_ticker, period=period_str, progress=False)

        if df.empty:
            raise HTTPException(status_code=404, detail=f"Data tidak ditemukan untuk ticker {ticker}")

        close_col = df['Close']
        if isinstance(close_col, pd.DataFrame):
            df_close = close_col.iloc[:, 0]
        else:
            df_close = close_col

        df_close = df_close.dropna()

        chart_data = []
        for dt, price in df_close.items():
            if days == 1:
                ts = int(calendar.timegm(dt.utctimetuple()))
                chart_data.append({"time": ts, "value": round(float(price), 2)})
            else:
                chart_data.append({"time": dt.strftime('%Y-%m-%d'), "value": round(float(price), 2)})

        result = {"status": "success", "data": chart_data, "intraday": days == 1}

        # Eviction: buang entri termua jika cache penuh
        if len(_chart_cache) >= CACHE_MAX_ENTRIES:
            oldest_key = min(_chart_cache, key=lambda k: _chart_cache[k][0])
            _chart_cache.pop(oldest_key, None)

        _chart_cache[cache_key] = (now, result)
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
