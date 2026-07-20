import requests
import json
import time
import os
import threading
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
            last_update = res["result"][-1]
            message = last_update.get("message") or last_update.get("channel_post")
            if message and "chat" in message:
                chat_id = str(message["chat"]["id"])
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

def send_morning_radar_broadcast(recommendations: list[dict]) -> dict:
    """
    [FASE 1: 08:30 WIB - PRE-MARKET RADAR]
    Mengirimkan daftar rekomendasi saham siap beli sebelum bursa BEI dibuka (09:00 WIB).
    """
    if not recommendations:
        return {"status": "error", "message": "Tidak ada sinyal rekomendasi pagi ini."}

    today_str = time.strftime("%Y-%m-%d")

    top_stocks = recommendations[:5]

    msg = f"<b>☀️ STOCKAI MORNING PRE-MARKET RADAR 🇮🇩</b>\n"
    msg += f"<i>📅 {today_str} | ⏰ 08:30 WIB (Pasar Buka 09:00 WIB)</i>\n"
    msg += f"───────────────────────\n\n"
    msg += f"<b>🎯 REKOMENDASI SAHAM SIAP BELI HARI INI:</b>\n\n"

    for idx, s in enumerate(top_stocks, start=1):
        ticker_name = s['ticker'].replace('.JK', '')
        close_p = format_idr(s.get('close_price', 0))
        target_p = format_idr(s.get('target_price', 0))
        stop_p = format_idr(s.get('stop_loss', 0))
        score = s.get('probability', 0.0)
        reason = s.get('reason', 'Sinyal Momentum Bullish')

        msg += f"<b>{idx}. 📈 {ticker_name}</b> ({s['ticker']})\n"
        msg += f"   • 💵 <b>Target Entry (Open):</b> {close_p}\n"
        msg += f"   • 🎯 <b>Target Profit (+3.0%):</b> {target_p}\n"
        msg += f"   • 🛑 <b>Stop Loss (-1.5%):</b> {stop_p}\n"
        msg += f"   • 🤖 <b>AI Score:</b> <code>{score:.1f}%</code>\n"
        msg += f"   • 💡 <i>{reason}</i>\n\n"

    msg += f"───────────────────────\n"
    msg += f"💡 <i>Tips: Pasang Automatic Order TP (+3.0%) dan SL (-1.5%) di aplikasi sekuritas Anda sebelum jam 09:00 WIB!</i>"

    return send_telegram_message(msg)

def send_after_market_audit_broadcast(recap_data: dict) -> dict:
    """
    [FASE 2: 16:05 WIB - AFTER-MARKET AUDIT & RECAP]
    Mengirimkan ringkasan audit hasil trading KHUSUS HARI INI + Total Track Record.
    """
    summary = recap_data.get("summary", {})
    win_rate_total = summary.get("win_rate", 0.0)
    win_count_total = summary.get("win_count", 0)
    loss_count_total = summary.get("loss_count", 0)
    total_profit = summary.get("total_profit_pct", 0.0)
    total_signals = summary.get("total_signals", 0)

    today_str = time.strftime("%Y-%m-%d")

    # Ambil rincian sinyal khusus hari ini dari API audit
    today_info = {}
    try:
        from dashboard.backend.routes.audit import get_today_audit_summary
        today_info = get_today_audit_summary()
    except Exception as e:
        print(f"[TELEGRAM] Error fetching today audit summary: {str(e)}")

    msg = f"<b>📊 STOCKAI AFTER-MARKET AUDIT & SYNC 🇮🇩</b>\n"
    msg += f"<i>📅 {today_str} | ⏰ 16:05 WIB (Pasar Tutup)</i>\n"
    msg += f"───────────────────────\n\n"

    # --- SECTION 1: KHUSUS HARI INI ---
    if today_info and today_info.get("signals"):
        t_win = today_info.get("win_count", 0)
        t_loss = today_info.get("loss_count", 0)
        t_pending = today_info.get("pending_count", 0)
        t_win_rate = today_info.get("win_rate", 0.0)
        t_gain = today_info.get("total_gain", 0.0)
        t_date = today_info.get("date", today_str)

        msg += f"<b>🔥 HASIL AUDIT TRADING HARI INI ({t_date}):</b>\n"
        msg += f"• 📊 <b>Hasil Sinyal:</b> {t_win} WIN ✅ / {t_loss} LOSS ❌"
        if t_pending > 0:
            msg += f" / {t_pending} PENDING ⏳"
        msg += f"\n• 🎯 <b>Win Rate Hari Ini:</b> <code>{t_win_rate:.1f}%</code>\n"
        msg += f"• 📈 <b>Gain Harian:</b> <code>{'+' if t_gain >= 0 else ''}{t_gain:.1f}%</code>\n\n"

        msg += f"<b>📜 DETAIL SAHAM HARI INI:</b>\n"
        for idx, s in enumerate(today_info["signals"][:10], start=1):
            st = s["status"]
            badge = "WIN ✅" if st == "WIN" else ("LOSS ❌" if st == "LOSS" else "PENDING ⏳")
            entry_p = format_idr(s["entry_price"])
            target_p = format_idr(s["target_price"])
            msg += f"{idx}. <b>{s['ticker']}</b>: {badge} (Entry {entry_p} → TP {target_p})\n"
        msg += f"\n"

    # --- SECTION 2: TOTAL TRACK RECORD AKUMULASI ---
    msg += f"───────────────────────\n"
    msg += f"<b>🏆 TOTAL TRACK RECORD AKUMULASI:</b>\n"
    msg += f"• 🎯 <b>Win Rate Total:</b> <code>{win_rate_total:.1f}%</code>\n"
    msg += f"• 📊 <b>Total Hasil:</b> {win_count_total} WIN ✅ / {loss_count_total} LOSS ❌\n"
    msg += f"• 📈 <b>Total Estimasi Profit:</b> <code>{'+' if total_profit >= 0 else ''}{total_profit:.1f}%</code> ({total_signals} Sinyal)\n\n"
    
    msg += f"───────────────────────\n"
    msg += f"🚀 <i>Data 300+ saham BEI terbaru telah diunduh dari Yahoo Finance & dianalisis untuk rekomendasi esok hari!</i>"

    return send_telegram_message(msg)

def start_telegram_bot_listener():
    """
    Menjalankan background thread polling yang secara kontinu mendengarkan
    dan merespon pesan/perintah interaktif (/today, /audit, /start) dari Telegram.
    """
    if os.getenv("TESTING") == "true" or "pytest" in sys.modules:
        return

    def listener_loop():
        token = TELEGRAM_BOT_TOKEN
        if not token:
            print("[TELEGRAM] Token belum dikonfigurasi, polling listener dilewati.")
            return

        print("[TELEGRAM] Background interactive listener aktif & siap menerima perintah (/today, /audit)...")
        offset = None

        while True:
            try:
                url = f"https://api.telegram.org/bot{token}/getUpdates?timeout=10"
                if offset:
                    url += f"&offset={offset}"

                res = requests.get(url, timeout=15).json()
                if res.get("ok") and res.get("result"):
                    for update in res["result"]:
                        offset = update["update_id"] + 1
                        msg = update.get("message")
                        if msg and "text" in msg and "chat" in msg:
                            text = msg["text"].strip().lower()
                            chat_id = str(msg["chat"]["id"])

                            if text in ["/today", "/audit", "today", "audit"]:
                                from dashboard.backend.routes.audit import get_audit_recap
                                recap = get_audit_recap()
                                send_after_market_audit_broadcast(recap)
                            elif text in ["/start", "/help", "halo", "hi"]:
                                send_telegram_message(
                                    "<b>🤖 StockAI Trading Bot Ready!</b>\n\n"
                                    "Ketik perintah berikut kapan saja:\n"
                                    "• <b>/today</b> atau <b>/audit</b> : Cek hasil audit WIN/LOSS hari ini.\n"
                                    "• <b>/start</b> : Cek status bot.",
                                    target_chat_id=chat_id
                                )
            except Exception as e:
                pass
            time.sleep(2)

    thread = threading.Thread(target=listener_loop, daemon=True)
    thread.start()

process_telegram_incoming_commands = start_telegram_bot_listener

# Alias untuk kompatibilitas
send_daily_recommendations_broadcast = send_morning_radar_broadcast

if __name__ == "__main__":
    print("Testing Telegram Bot Module...")
    c_id = get_active_chat_id()
    print(f"Detected Chat ID: {c_id}")
    if c_id:
        send_telegram_message("<b>🤖 StockAI Bot Ready!</b>\nDual Notifikasi Harian & Perintah Interaktif (/today) telah aktif.")


