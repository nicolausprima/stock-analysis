import requests
import json
import time
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def get_active_chat_id() -> str:
    """
    Mengambil TELEGRAM_CHAT_ID. Jika belum terisi di .env,
    secara otomatis mendeteksi chat_id dari /getUpdates Telegram API.
    """
    if TELEGRAM_CHAT_ID and len(TELEGRAM_CHAT_ID.strip()) > 0:
        return TELEGRAM_CHAT_ID.strip()

    # Coba auto-detect dari getUpdates
    if not TELEGRAM_BOT_TOKEN:
        return ""

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        res = requests.get(url, timeout=5).json()
        if res.get("ok") and res.get("result"):
            # Ambil update paling baru
            last_update = res["result"][-1]
            message = last_update.get("message") or last_update.get("channel_post")
            if message and "chat" in message:
                chat_id = str(message["chat"]["id"])
                # Simpan otomatis ke .env jika ditemukan
                _update_env_chat_id(chat_id)
                return chat_id
    except Exception as e:
        print(f"[TELEGRAM] Error auto-detecting chat_id: {str(e)}")

    return ""

def _update_env_chat_id(chat_id: str):
    """Menyimpan chat_id yang terdeteksi ke file .env."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return

    try:
        content = env_path.read_text(encoding="utf-8")
        if 'TELEGRAM_CHAT_ID=""' in content or 'TELEGRAM_CHAT_ID=' in content:
            lines = content.splitlines()
            new_lines = []
            for line in lines:
                if line.startswith("TELEGRAM_CHAT_ID="):
                    new_lines.append(f'TELEGRAM_CHAT_ID="{chat_id}"')
                else:
                    new_lines.append(line)
            env_path.write_text("\n".join(new_lines), encoding="utf-8")
            print(f"[TELEGRAM] Chat ID {chat_id} berhasil disimpan ke file .env!")
    except Exception as e:
        print(f"[TELEGRAM] Gagal menyimpan chat_id ke .env: {str(e)}")

def send_telegram_message(html_text: str, target_chat_id: str = None) -> dict:
    """
    Mengirim pesan HTML ke Telegram Bot.
    """
    token = TELEGRAM_BOT_TOKEN
    chat_id = target_chat_id or get_active_chat_id()

    if not token:
        return {"status": "error", "message": "Bot token belum terkonfigurasi."}

    if not chat_id:
        return {
            "status": "error", 
            "message": "Chat ID belum terdeteksi. Silakan kirim pesan ke @StockAnalysisLocalBot di Telegram terlebih dahulu!"
        }

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": html_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        res = requests.post(url, json=payload, timeout=8).json()
        if res.get("ok"):
            print(f"[TELEGRAM] Pesan berhasil terkirim ke Telegram (Chat ID: {chat_id})!")
            return {"status": "success", "message": "Pesan terkirim!"}
        else:
            print(f"[TELEGRAM] Gagal mengirim pesan: {res.get('description')}")
            return {"status": "error", "message": res.get("description", "Error Telegram API")}
    except Exception as e:
        print(f"[TELEGRAM] Exception: {str(e)}")
        return {"status": "error", "message": str(e)}

def format_idr(val: float) -> str:
    if not val or val <= 0:
        return "-"
    return f"Rp {val:,.0f}".replace(",", ".")

def send_daily_recommendations_broadcast(recommendations: list[dict]) -> dict:
    """
    Membuat format pesan siaran harian yang rapi dan membagikannya ke Telegram.
    """
    if not recommendations:
        return {"status": "error", "message": "Tidak ada sinyal rekomendasi."}

    today_str = time.strftime("%Y-%m-%d")
    time_str = time.strftime("%H:%M WIB")

    top_stocks = recommendations[:5]

    msg = f"<b>🚨 STOCKAI DAILY BUY SIGNALS 🇮🇩</b>\n"
    msg += f"<i>📅 {today_str} | ⏰ {time_str}</i>\n"
    msg += f"───────────────────────\n\n"
    msg += f"<b>🏆 TOP {len(top_stocks)} SAHAM PILIHAN UTAMA:</b>\n\n"

    for idx, s in enumerate(top_stocks, start=1):
        ticker_name = s['ticker'].replace('.JK', '')
        close_p = format_idr(s.get('close_price', 0))
        target_p = format_idr(s.get('target_price', 0))
        stop_p = format_idr(s.get('stop_loss', 0))
        score = s.get('probability', 0.0)
        reason = s.get('reason', 'Signal Bullish')
        impact = s.get('sentiment_impact', 'NETRAL')

        msg += f"<b>{idx}. 📈 {ticker_name}</b> ({s['ticker']})\n"
        msg += f"   • 💵 <b>Harga Open Esok:</b> {close_p}\n"
        msg += f"   • 🎯 <b>Target (+3.0%):</b> {target_p}\n"
        msg += f"   • 🛑 <b>Stop Loss (-1.5%):</b> {stop_p}\n"
        msg += f"   • 🤖 <b>AI Score:</b> <code>{score:.1f}%</code> | Sentimen: {impact}\n"
        msg += f"   • 💡 <i>{reason}</i>\n\n"

    msg += f"───────────────────────\n"
    msg += f"⚠️ <i>Disclaimer: Rekomendasi AI adalah alat bantu day trading. Selalu gunakan manajemen risiko disiplin (TP +3.0% / SL -1.5%).</i>"

    return send_telegram_message(msg)

if __name__ == "__main__":
    # Test pengiriman saat script dijalankan langsung
    print("Testing Telegram Bot Module...")
    c_id = get_active_chat_id()
    print(f"Detected Chat ID: {c_id}")
    if c_id:
        send_telegram_message("<b>🤖 StockAI Bot Ready!</b>\nNotifikasi otomatis harian telah aktif.")
