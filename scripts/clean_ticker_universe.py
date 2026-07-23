import sys
import pandas as pd
import yfinance as yf
from pathlib import Path

# Absolute import resolution
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.config import TICKER_LIST_FILE, get_tickers

def clean_and_sync_ticker_universe():
    """
    Memverifikasi seluruh ticker di data/tickers.txt, mendeteksi saham delisting
    atau suspend permanen, dan memperbarui tickers.txt hanya dengan saham aktif.
    """
    tickers = get_tickers()
    if not tickers:
        print("⚠️ File tickers.txt kosong atau tidak ditemukan.")
        return

    print(f"[CLEANUP] Memulai verifikasi keaktifan {len(tickers)} saham BEI...")

    # Unduh harga 5 hari terakhir secara cepat
    batch_size = 50
    active_tickers = []
    delisted_or_suspended = []

    for i in range(0, len(tickers), batch_size):
        chunk = tickers[i:i + batch_size]
        chunk_str = " ".join(chunk)
        try:
            df = yf.download(chunk_str, period="5d", progress=False, group_by="ticker", threads=True)
            for t in chunk:
                try:
                    if len(chunk) == 1:
                        stock_df = df
                    else:
                        stock_df = df[t] if t in df.columns.levels[0] else pd.DataFrame()

                    if stock_df.empty or stock_df['Close'].dropna().empty:
                        delisted_or_suspended.append((t, "Delisted / No Data"))
                    elif 'Volume' in stock_df.columns and stock_df['Volume'].sum() == 0:
                        delisted_or_suspended.append((t, "Suspended (Zero Volume)"))
                    else:
                        active_tickers.append(t)
                except Exception:
                    delisted_or_suspended.append((t, "Download Error"))
        except Exception as e:
            print(f"⚠️ Error batch {i}: {str(e)}")

    print(f"\n[HASIL CLEANUP]")
    print(f"✅ Saham Aktif Ditahankan: {len(active_tickers)}")
    print(f"🚫 Saham Suspended / Delisted Dieliminasi: {len(delisted_or_suspended)}")

    if delisted_or_suspended:
        print("\nContoh Saham Tereliminasi:")
        for t, reason in delisted_or_suspended[:10]:
            print(f"  - {t}: {reason}")

    # Simpan kembali hanya ticker aktif
    if active_tickers:
        with open(TICKER_LIST_FILE, 'w') as f:
            for t in sorted(active_tickers):
                f.write(f"{t}\n")
        print(f"\n✅ File {TICKER_LIST_FILE.name} berhasil diperbarui dengan {len(active_tickers)} saham aktif!")

if __name__ == "__main__":
    clean_and_sync_ticker_universe()
