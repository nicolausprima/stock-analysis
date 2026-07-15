from fastapi import APIRouter, HTTPException
import yfinance as yf
import pandas as pd
import calendar

router = APIRouter()

@router.get("/chart/{ticker}")
def get_chart_data(ticker: str, days: int = 60):
    """
    Mengambil data historis untuk chart.
    - days=1  → intraday per 5 menit, time = Unix timestamp (int)
    - days>1  → harian, time = 'YYYY-MM-DD' (string)
    Format sesuai TradingView Lightweight Charts.
    """
    try:
        if ticker.upper() == "IHSG":
            yf_ticker = "^JKSE"
        else:
            yf_ticker = ticker if ".JK" in ticker or ticker.startswith("^") else f"{ticker}.JK"

        if days == 1:
            # Intraday: data per 5 menit hari ini
            df = yf.download(yf_ticker, period="1d", interval="5m", progress=False)
        else:
            period_str = f"{days}d"
            df = yf.download(yf_ticker, period=period_str, progress=False)

        if df.empty:
            raise HTTPException(status_code=404, detail=f"Data tidak ditemukan untuk ticker {ticker}")

        if isinstance(df.columns, pd.MultiIndex):
            df_close = df['Close'].iloc[:, 0] if hasattr(df['Close'], 'iloc') else df['Close']
        else:
            df_close = df['Close']

        df_close = df_close.dropna()

        chart_data = []
        for dt, price in df_close.items():
            if days == 1:
                # Lightweight Charts intraday butuh Unix timestamp (seconds)
                # Konversi ke UTC timestamp
                ts = int(calendar.timegm(dt.utctimetuple()))
                chart_data.append({"time": ts, "value": round(float(price), 2)})
            else:
                chart_data.append({"time": dt.strftime('%Y-%m-%d'), "value": round(float(price), 2)})

        return {"status": "success", "data": chart_data, "intraday": days == 1}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
