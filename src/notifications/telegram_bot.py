import json
import os
import sys
import threading
import time
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.config import TELEGRAM_CHAT_ID, get_allowed_chat_ids, get_telegram_bot_token

CONFIG_JSON = PROJECT_ROOT / "data" / "telegram_config.json"

# Cooldown per-chat untuk perintah berat + single-flight job berat (anti-DoS via bot).
_CHAT_COOLDOWN_SEC = 60.0
_last_cmd_at: dict[str, float] = {}
_heavy_job_lock = threading.Lock()

DISCLAIMER_TG = (
    "Konten ini riset kuantitatif untuk edukasi — BUKAN nasihat/rekomendasi investasi. "
    "Saham berisiko rugi. Kinerja masa lalu tidak menjamin hasil. Keputusan & risiko milik Anda (DYOR)."
)

def is_chat_allowed(chat_id: str) -> bool:
    """True jika chat terdaftar di allowlist. Tanpa allowlist -> tolak semua (fail-closed)."""
    if not chat_id:
        return False
    allowed = get_allowed_chat_ids()
    if not allowed:
        return False
    return str(chat_id).strip() in allowed


def _check_cooldown(chat_id: str) -> tuple[bool, int]:
    """Return (allowed, retry_sec). Cooldown per-chat untuk perintah berat."""
    now = time.time()
    last = _last_cmd_at.get(str(chat_id), 0.0)
    wait = int(_CHAT_COOLDOWN_SEC - (now - last)) + 1
    if wait > 0 and last > 0:
        return False, max(wait, 1)
    _last_cmd_at[str(chat_id)] = now
    return True, 0


def _with_disclaimer(html_text: str) -> str:
    if DISCLAIMER_TG in html_text:
        return html_text
    return f"{html_text}\n\n<i>{DISCLAIMER_TG}</i>"

def get_active_chat_id() -> str:
    """
    Mengambil chat_id utama dari allowlist (TELEGRAM_CHAT_ID / TELEGRAM_ALLOWED_CHAT_IDS).
    Fallback data/telegram_config.json hanya dipakai bila isinya ada di allowlist.
    Auto-detect getUpdates hanya menerima chat yang ada di allowlist (anti takeover).
    """
    allowed = get_allowed_chat_ids()
    if TELEGRAM_CHAT_ID and len(TELEGRAM_CHAT_ID.strip()) > 0:
        first = TELEGRAM_CHAT_ID.strip().split(",")[0].strip()
        if first in allowed:
            return first
        return ""  # fail-closed: env tunggal tak ada di allowlist -> tolak

    if allowed:
        return min(allowed)

    if CONFIG_JSON.exists():
        try:
            cfg = json.loads(CONFIG_JSON.read_text(encoding="utf-8"))
            if cfg.get("chat_id") and (not allowed or str(cfg["chat_id"]) in allowed):
                return str(cfg["chat_id"])
        except Exception:
            pass

    # Coba auto-detect dari getUpdates — hanya chat yang di-allowlist
    token = get_telegram_bot_token()
    if not token:
        return ""

    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        res = requests.get(url, timeout=5).json()
        if res.get("ok") and res.get("result"):
            for update in reversed(res["result"][-10:]):
                message = update.get("message") or update.get("channel_post")
                if message and "chat" in message:
                    chat_id = str(message["chat"]["id"])
                    if not allowed or chat_id in allowed:
                        _save_dynamic_chat_id(chat_id)
                        return chat_id
    except Exception as e:
        print(f"[TELEGRAM] Error auto-detecting chat_id: {str(e)[:100]}")

    return ""

def _save_dynamic_chat_id(chat_id: str):
    """Menyimpan chat_id yang terdeteksi ke file data/telegram_config.json tanpa mengubah .env."""
    try:
        CONFIG_JSON.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_JSON.write_text(json.dumps({"chat_id": chat_id}), encoding="utf-8")
        print(f"[TELEGRAM] Chat ID {chat_id} berhasil disimpan ke data/telegram_config.json!")
    except Exception as e:
        print(f"[TELEGRAM] Gagal menyimpan chat_id: {e!s}")

def send_telegram_message(html_text: str, target_chat_id: str | None = None) -> dict:
    """
    Mengirim pesan HTML ke Telegram Bot. Token dibaca per-call dari env
    (tidak pernah di-log). Target di luar allowlist ditolak (fail-closed).
    """
    token = get_telegram_bot_token()
    chat_id = (target_chat_id or get_active_chat_id() or "").strip()

    if not token:
        return {"status": "error", "message": "Bot token belum terkonfigurasi."}

    if not chat_id:
        return {
            "status": "error",
            "message": "Chat ID belum terdeteksi. Set TELEGRAM_CHAT_ID / TELEGRAM_ALLOWED_CHAT_IDS."
        }

    if not is_chat_allowed(chat_id):
        return {"status": "error", "message": "Chat ID tidak diizinkan (allowlist)."}

    safe_text = _with_disclaimer(html_text)
    if len(safe_text) > 4000:
        safe_text = safe_text[:3990] + "…"

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": safe_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        res = requests.post(url, json=payload, timeout=8).json()
        if res.get("ok"):
            print("[TELEGRAM] Pesan berhasil terkirim ke Telegram!")
            return {"status": "success", "message": "Pesan terkirim!"}
        print(f"[TELEGRAM] Gagal mengirim pesan: {res.get('description')}")
        return {"status": "error", "message": res.get("description", "Error Telegram API")}
    except Exception as e:
        print(f"[TELEGRAM] Exception: {str(e)[:200]}")
        return {"status": "error", "message": "Gagal mengirim pesan Telegram."}

def format_idr(val: float) -> str:
    if not val or val <= 0:
        return "-"
    return f"Rp {val:,.0f}".replace(",", ".")

def send_morning_radar_broadcast(recommendations: list[dict]) -> dict:
    """
    [FASE 1: 08:30 WIB - PRE-MARKET RADAR]
    Sinyal riset kuantitatif untuk edukasi — BUKAN rekomendasi beli.
    """
    import html as _html
    if not recommendations:
        return {"status": "error", "message": "Tidak ada sinyal rekomendasi pagi ini."}

    today_str = time.strftime("%Y-%m-%d")

    top_stocks = recommendations[:5]

    msg = "<b>☀️ STOCKAI MORNING PRE-MARKET RADAR 🇮🇩</b>\n"
    msg += f"<i>📅 {today_str} | ⏰ 08:30 WIB (Pasar Buka 09:00 WIB)</i>\n"
    msg += "───────────────────────\n\n"
    msg += "<b>🎯 SINYAL RISET KUANTITATIF HARI INI (BUKAN REKOMENDASI BELI):</b>\n\n"

    for idx, s in enumerate(top_stocks, start=1):
        ticker_name = _html.escape(str(s.get('ticker', '?')).replace('.JK', ''))
        close_p = format_idr(s.get('close_price', 0))
        target_p = format_idr(s.get('target_price', 0))
        stop_p = format_idr(s.get('stop_loss', 0))
        score = s.get('probability', 0.0)
        reason = _html.escape(str(s.get('reason', 'Sinyal Momentum Bullish'))[:200])
        sector = _html.escape(str(s.get('sector', 'Umum'))[:40])
        is_leading = s.get('is_leading_sector', False)
        kelly = s.get('kelly_allocation', 10.0)
        rr = s.get('risk_reward_ratio', 2.0)

        cp = s.get('close_price', 1)
        tp_val = s.get('target_price', 1)
        sl_val = s.get('stop_loss', 1)
        tp_pct = ((tp_val - cp) / cp * 100) if cp > 0 else 3.0
        sl_pct = ((sl_val - cp) / cp * 100) if cp > 0 else -1.5

        sec_badge = f" [Sektor: {sector}{' ⚡' if is_leading else ''}]"

        msg += f"<b>{idx}. 📈 {ticker_name}</b> ({s['ticker']}){sec_badge}\n"
        msg += f"   • 💵 <b>Target Entry (Open):</b> {close_p}\n"
        msg += f"   • 🎯 <b>Target Profit (+{tp_pct:.1f}%):</b> {target_p}\n"
        msg += f"   • 🛑 <b>Stop Loss ({sl_pct:.1f}%):</b> {stop_p}\n"
        msg += f"   • 💰 <b>Referensi Sizing Model (bukan saran alokasi):</b> <code>{kelly:.0f}%</code> (R:R 1:{rr:.1f})\n"
        msg += f"   • 🤖 <b>AI Score:</b> <code>{score:.1f}%</code>\n"
        msg += f"   • 💡 <i>{reason}</i>\n\n"

    msg += "───────────────────────\n"
    msg += "💡 <i>Riset edukasi — keputusan & risiko milik Anda (DYOR). Pertimbangkan biaya & slippage sebelum bertindak.</i>"

    return send_telegram_message(msg)

def send_midday_recap_broadcast(today_audit: dict | None = None, target_chat_id: str | None = None) -> dict:
    """
    [FASE 2: 12:00 WIB - MIDDAY MARKET RECAP]
    Mengirimkan update performa pasar Sesi 1 saat bursa istirahat (12:00 WIB).
    """
    today_str = time.strftime("%Y-%m-%d")
    today_info = today_audit or {}
    if not today_info:
        try:
            from dashboard.backend.routes.audit import get_today_audit_summary
            today_info = get_today_audit_summary()
        except Exception as e:
            print(f"[TELEGRAM] Error fetching today audit summary for midday: {e!s}")

    msg = "<b>☕ STOCKAI MIDDAY MARKET RECAP 🇮🇩</b>\n"
    msg += f"<i>📅 {today_str} | ⏰ 12:00 WIB (Jeda Sesi 1)</i>\n"
    msg += "───────────────────────\n\n"

    if today_info and today_info.get("signals"):
        t_win = today_info.get("win_count", 0)
        t_loss = today_info.get("loss_count", 0)
        t_pending = today_info.get("pending_count", 0)
        t_win_rate = today_info.get("win_rate", 0.0)

        msg += "<b>📊 PERKEMBANGAN SINYAL PAGI (SESI 1):</b>\n"
        msg += f"• 🎯 <b>Hasil Sementara:</b> {t_win} WIN ✅ / {t_loss} LOSS ❌ / {t_pending} PENDING ⏳\n"
        msg += f"• 📈 <b>Win Rate Sesi 1:</b> <code>{t_win_rate:.1f}%</code>\n\n"

        msg += "<b>📜 STATUS SAHAM SESI 1:</b>\n"
        for idx, s in enumerate(today_info["signals"][:5], start=1):
            st = s["status"]
            badge = "WIN ✅" if st == "WIN" else ("LOSS ❌" if st == "LOSS" else "BERJALAN ⏳")
            entry_p = format_idr(s["entry_price"])
            target_p = format_idr(s["target_price"])
            msg += f"{idx}. <b>{s['ticker']}</b>: {badge} (Entry {entry_p} → TP {target_p})\n"
        msg += "\n"

    msg += "───────────────────────\n"
    msg += "💡 <i>Catatan: Bursa akan kembali dibuka untuk Sesi 2 pukul 13:30 WIB. Pantau terus stop loss Anda!</i>"

    return send_telegram_message(msg, target_chat_id=target_chat_id)

def send_bsjp_radar_broadcast(recommendations: list[dict], target_chat_id: str | None = None) -> dict:
    """
    Sinyal riset sore (BSJP) untuk edukasi — BUKAN instruksi beli.
    """
    import html as _html
    if not recommendations:
        return {"status": "error", "message": "Tidak ada sinyal BSJP sore ini."}

    today_str = time.strftime("%Y-%m-%d")
    top_stocks = recommendations[:5]

    msg = "<b>🌇 STOCKAI BSJP RADAR (BELI SORE JUAL PAGI) 🇮🇩</b>\n"
    msg += f"<i>📅 {today_str} | ⏰ 15:30 WIB (30 Menit Sebelum Market Tutup)</i>\n"
    msg += "───────────────────────\n\n"
    msg += "<b>🚀 SINYAL RISET SORE INI (BUKAN INSTRUKSI BELI):</b>\n\n"

    for idx, s in enumerate(top_stocks, start=1):
        ticker_name = _html.escape(str(s.get('ticker', '?')).replace('.JK', ''))
        close_p = format_idr(s.get('close_price', 0))
        target_p = format_idr(s.get('target_price', 0))
        stop_p = format_idr(s.get('stop_loss', 0))
        score = s.get('probability', 0.0)
        reason = _html.escape(str(s.get('reason', 'Akumulasi & Volatilitas Menit Akhir'))[:200])

        msg += f"<b>{idx}. 🔥 {ticker_name}</b> ({_html.escape(str(s.get('ticker','?'))[:12])})\n"
        msg += f"   • 🛒 <b>Referensi Harga (15:30-15:50):</b> {close_p}\n"
        msg += f"   • 🎯 <b>Target Model (+3.0%):</b> {target_p}\n"
        msg += f"   • 🛑 <b>Stop Loss Model (-1.5%):</b> {stop_p}\n"
        msg += f"   • 🤖 <b>AI Score:</b> <code>{score:.1f}%</code>\n"
        msg += f"   • 💡 <i>{reason}</i>\n\n"

    msg += "───────────────────────\n"
    msg += "⏰ <i>Riset edukasi — bukan perintah eksekusi. Keputusan & risiko milik Anda (DYOR).</i>"

    return send_telegram_message(msg, target_chat_id=target_chat_id)

def send_after_market_audit_broadcast(recap_data: dict, new_recommendations: list | None = None, today_audit: dict | None = None, macro_eval: dict | None = None) -> dict:
    """
    Mengirimkan ringkasan audit hasil trading KHUSUS HARI INI + Total Track Record + Rekomendasi Esok Hari.
    Semua string eksternal (headline/macro) di-escape agar aman di parse_mode HTML.
    """
    import html as _html
    summary = recap_data.get("summary", {})
    win_rate_total = summary.get("win_rate", 0.0)
    win_count_total = summary.get("win_count", 0)
    loss_count_total = summary.get("loss_count", 0)
    total_profit = summary.get("total_profit_pct", 0.0)
    total_signals = summary.get("total_signals", 0)

    today_str = time.strftime("%Y-%m-%d")

    # Ambil rincian sinyal khusus hari ini jika belum di-pass
    today_info = today_audit or {}
    if not today_info:
        try:
            from dashboard.backend.routes.audit import get_today_audit_summary
            today_info = get_today_audit_summary()
        except Exception as e:
            print(f"[TELEGRAM] Error fetching today audit summary: {e!s}")

    msg = "<b>📊 STOCKAI AFTER-MARKET AUDIT & SYNC 🇮🇩</b>\n"
    msg += f"<i>📅 {today_str} | ⏰ 16:05 WIB (Pasar Tutup)</i>\n"
    msg += "───────────────────────\n\n"

    # --- SECTION 0: KONDISI MAKRO & SENTIMEN BERITA ---
    if macro_eval:
        msg += "<b>🌐 KONDISI MAKRO & SENTIMEN BERITA:</b>\n"
        msg += f"• 🎯 <b>Status Pasar:</b> {_html.escape(str(macro_eval.get('mode_badge', 'NORMAL'))[:40])}\n"
        msg += f"• 📊 <b>Macro Score:</b> <code>{macro_eval.get('macro_score', 0):+.1f}</code>\n"
        for d in macro_eval.get('details', [])[:4]:
            msg += f"  {_html.escape(str(d)[:160])}\n"
        news = macro_eval.get('news_sentiment', {})
        if news and news.get('headlines'):
            msg += "📰 <b>Headline Ekonomi Terkini:</b>\n"
            for h in news['headlines'][:3]:
                msg += f"  • {_html.escape(str(h.get('title',''))[:160])}\n"
        msg += "───────────────────────\n\n"

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

        msg += "<b>📜 DETAIL SAHAM HARI INI:</b>\n"
        for idx, s in enumerate(today_info["signals"][:10], start=1):
            st = s["status"]
            ret_val = s.get("return_pct", 3.0 if st == "WIN" else (-1.5 if st == "LOSS" else 0.0))
            ret_sign = "+" if ret_val >= 0 else ""
            badge = f"WIN {ret_sign}{ret_val:.1f}% ✅" if st == "WIN" else (f"LOSS {ret_val:.1f}% ❌" if st == "LOSS" else "PENDING ⏳")
            entry_p = format_idr(s["entry_price"])
            target_p = format_idr(s["target_price"])
            msg += f"{idx}. <b>{s['ticker']}</b>: {badge} (Entry {entry_p} → TP {target_p})\n"
        msg += "\n"

    # --- SECTION 2: TOTAL TRACK RECORD AKUMULASI ---
    msg += "───────────────────────\n"
    msg += "<b>🏆 TOTAL TRACK RECORD AKUMULASI:</b>\n"
    msg += f"• 🎯 <b>Win Rate Total:</b> <code>{win_rate_total:.1f}%</code>\n"
    msg += f"• 📊 <b>Total Hasil:</b> {win_count_total} WIN ✅ / {loss_count_total} LOSS ❌\n"
    msg += f"• 📈 <b>Total Estimasi Profit:</b> <code>{'+' if total_profit >= 0 else ''}{total_profit:.1f}%</code> ({total_signals} Sinyal)\n\n"
    
    # --- SECTION 3: REKOMENDASI SINYAL BELI ESOK HARI ---
    if new_recommendations:
        msg += "───────────────────────\n"
        msg += "<b>🚀 SINYAL RISET UNTUK ESOK HARI (BUKAN REKOMENDASI BELI):</b>\n"
        for idx, s in enumerate(new_recommendations[:10], start=1):
            clean_tk = _html.escape(str(s.get('ticker','?')).replace('.JK', '')[:12])
            prob = s['probability']
            ep = format_idr(s['close_price'])
            tp = format_idr(s['target_price'])
            sl = format_idr(s['stop_loss'])
            msg += f"{idx}. <b>{clean_tk}</b> (AI Score: <code>{prob:.1f}%</code>) | Entry {ep} | TP {tp} | SL {sl}\n"
        msg += "\n"

    msg += "───────────────────────\n"
    msg += "🚀 <i>Data 700+ saham BEI terbaru telah diunduh dari Yahoo Finance & dianalisis untuk rekomendasi esok hari!</i>"

    return send_telegram_message(msg)

def _format_today_audit(today_info: dict) -> str:
    today_str = time.strftime("%Y-%m-%d")
    if not today_info or not today_info.get("signals"):
        return f"<b>🔥 AUDIT TRADING HARI INI ({today_str})</b>\n───────────────────────\nBelum ada data audit sinyal untuk hari ini."

    t_win = today_info.get("win_count", 0)
    t_loss = today_info.get("loss_count", 0)
    t_pending = today_info.get("pending_count", 0)
    t_win_rate = today_info.get("win_rate", 0.0)
    t_gain = today_info.get("total_gain", 0.0)
    t_date = today_info.get("date", today_str)

    msg = f"<b>🔥 HASIL AUDIT TRADING HARI INI ({t_date})</b>\n"
    msg += "───────────────────────\n\n"
    msg += f"• 📊 <b>Hasil Sinyal:</b> {t_win} WIN ✅ / {t_loss} LOSS ❌"
    if t_pending > 0:
        msg += f" / {t_pending} PENDING ⏳"
    msg += f"\n• 🎯 <b>Win Rate Hari Ini:</b> <code>{t_win_rate:.1f}%</code>\n"
    msg += f"• 📈 <b>Gain Harian:</b> <code>{'+' if t_gain >= 0 else ''}{t_gain:.1f}%</code>\n\n"

    msg += "<b>📜 DETAIL SAHAM HARI INI:</b>\n"
    for idx, s in enumerate(today_info["signals"][:10], start=1):
        st = s["status"]
        ret_val = s.get("return_pct", 3.0 if st == "WIN" else (-1.5 if st == "LOSS" else 0.0))
        ret_sign = "+" if ret_val >= 0 else ""
        badge = f"WIN {ret_sign}{ret_val:.1f}% ✅" if st == "WIN" else (f"LOSS {ret_val:.1f}% ❌" if st == "LOSS" else "PENDING ⏳")
        entry_p = format_idr(s["entry_price"])
        target_p = format_idr(s["target_price"])
        msg += f"{idx}. <b>{s['ticker']}</b>: {badge} (Entry {entry_p} → TP {target_p})\n"
    return msg

def _format_audit_recap(recap_data: dict) -> str:
    s = recap_data.get("summary", {})
    msg = "<b>🏆 TOTAL TRACK RECORD AUDIT (6 BULAN)</b>\n"
    msg += "───────────────────────\n\n"
    msg += f"• 🎯 <b>Win Rate Total:</b> <code>{s.get('win_rate',0):.1f}%</code>\n"
    msg += f"• 📊 <b>Total Sinyal Audited:</b> {s.get('win_count',0)} WIN ✅ / {s.get('loss_count',0)} LOSS ❌\n"
    msg += f"• ⏳ <b>Pending Active:</b> {s.get('pending_count',0)}\n"
    msg += f"• 📈 <b>Estimasi Profit Kumulatif:</b> <code>{'+' if s.get('total_profit_pct',0) >= 0 else ''}{s.get('total_profit_pct',0):.1f}%</code>\n"
    return msg

def start_telegram_bot_listener():
    """
    Menjalankan background thread polling yang secara kontinu mendengarkan
    dan merespon pesan/perintah interaktif (/today, /midday, /bsjp, /audittoday, /auditall, /start) dari Telegram.
    """
    if os.getenv("TESTING") == "true" or "pytest" in sys.modules:
        return

    def send_today_picks(chat_id):
        """Kirim Top 10 rekomendasi hari ini ke chat tertentu."""
        import html as _html
        try:
            import json

            from src.config import CACHE_FILE
            if CACHE_FILE.exists():
                with open(CACHE_FILE) as f:
                    data = json.load(f)
                stocks = data.get("data", [])
                if stocks:
                    msg = "<b>📅 REKOMENDASI SAHAM HARI INI</b>\n"
                    msg += f"<i>{_html.escape(str(data.get('timestamp', '—')))}</i>\n"
                    msg += "───────────────────────\n\n"
                    for idx, s in enumerate(stocks[:10], 1):
                        import re as _re
                        raw_t = str(s.get('ticker', '?'))
                        t = _re.sub(r"[^A-Z0-9.]", "", raw_t.upper())[:12].replace('.JK', '')
                        msg += f"<b>{idx}. {_html.escape(t)}</b>\n"
                        msg += f"   💵 {s.get('close_price',0):,.0f} → 🎯 {s.get('target_price',0):,.0f} 🛑 {s.get('stop_loss',0):,.0f}\n"
                        msg += f"   🤖 Score: <code>{float(s.get('probability',0)):.1f}%</code> | {_html.escape(str(s.get('reason',''))[:200])}\n\n"
                    return send_telegram_message(msg, target_chat_id=chat_id)
            return send_telegram_message("Belum ada rekomendasi. Jalankan scan dulu.", target_chat_id=chat_id)
        except Exception:
            return send_telegram_message("Gagal memuat rekomendasi. Coba lagi nanti.", target_chat_id=chat_id)

    def listener_loop():
        token = get_telegram_bot_token()
        if not token:
            print("[TELEGRAM] Token belum dikonfigurasi, polling listener dilewati.")
            return

        print("[TELEGRAM] Background interactive listener aktif & siap menerima perintah (/today, /audit...)...")
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
                            text = msg["text"].strip().lower()[:32]
                            chat_id = str(msg["chat"]["id"])

                            # SEC-02: allowlist fail-closed — chat asing ditolak tanpa info.
                            if not is_chat_allowed(chat_id):
                                continue

                            if text in ["/start", "/help", "halo", "hi"]:
                                send_telegram_message(
                                    "<b>🤖 StockAI Trading Bot Ready!</b>\n\n"
                                    "Ketik perintah interaktif berikut kapan saja:\n"
                                    "• <b>/today</b> : Rekomendasi Saham Siap Beli Pagi 🎯\n"
                                    "• <b>/midday</b> : Update Sesi 1 & Progress Sinyal ☕\n"
                                    "• <b>/bsjp</b> : Sinyal Beli Sore Jual Pagi 🌇\n"
                                    "• <b>/audittoday</b> : Hasil Audit Trading Hari Ini 🔥\n"
                                    "• <b>/auditall</b> : Track Record & Win Rate Total (6 Bulan) 📊\n"
                                    "• <b>/start</b> : Menampilkan menu perintah ini",
                                    target_chat_id=chat_id
                                )
                                continue

                            # Perintah berat: cooldown 60s per-chat + single-flight global.
                            ok, retry = _check_cooldown(chat_id)
                            if not ok:
                                send_telegram_message(
                                    f"⏳ Terlalu sering. Coba lagi dalam {retry}s.",
                                    target_chat_id=chat_id)
                                continue
                            if _heavy_job_lock.locked():
                                send_telegram_message(
                                    "⏳ Job berat sedang berjalan. Coba lagi sebentar.",
                                    target_chat_id=chat_id)
                                continue

                            if text in ["/today", "today"]:
                                send_today_picks(chat_id)
                            elif text in ["/midday", "midday"]:
                                send_telegram_message("⏳ <b>Mengunduh data pasar Sesi 1 terbaru & meng-audit sinyal... Mohon tunggu sebentar.</b>", target_chat_id=chat_id)
                                def handle_midday(c_id=chat_id):
                                    if not _heavy_job_lock.acquire(blocking=False):
                                        return send_telegram_message("⏳ Job berat sedang berjalan.", target_chat_id=c_id)
                                    try:
                                        from dashboard.backend.routes.audit import (
                                            get_today_audit_summary,
                                            run_audit,
                                        )
                                        run_audit()
                                        info = get_today_audit_summary()
                                        send_midday_recap_broadcast(info, target_chat_id=c_id)
                                    except Exception:
                                        send_telegram_message("Gagal memuat midday recap. Coba lagi nanti.", target_chat_id=c_id)
                                    finally:
                                        _heavy_job_lock.release()
                                threading.Thread(target=handle_midday, daemon=True).start()

                            elif text in ["/bsjp", "bsjp"]:
                                send_telegram_message("⏳ <b>Mengunduh data intraday real-time 700+ saham BEI & menganalisis sinyal BSJP terbaru... Mohon tunggu sebentar.</b>", target_chat_id=chat_id)
                                def handle_bsjp(c_id=chat_id):
                                    if not _heavy_job_lock.acquire(blocking=False):
                                        return send_telegram_message("⏳ Job berat sedang berjalan.", target_chat_id=c_id)
                                    try:
                                        from src.scheduler.daily_scheduler import (
                                            run_daily_after_market_job,
                                        )
                                        res = run_daily_after_market_job(skip_download=False, broadcast_telegram=False, save_to_json=False, save_to_db=False)
                                        stocks = res.get("data", []) if isinstance(res, dict) else []
                                        if stocks:
                                            send_bsjp_radar_broadcast(stocks, target_chat_id=c_id)
                                        else:
                                            send_telegram_message("Belum ada sinyal BSJP sore ini.", target_chat_id=c_id)
                                    except Exception:
                                        send_telegram_message("Gagal memuat sinyal BSJP. Coba lagi nanti.", target_chat_id=c_id)
                                    finally:
                                        _heavy_job_lock.release()
                                threading.Thread(target=handle_bsjp, daemon=True).start()

                            elif text in ["/audittoday", "audittoday", "audit today", "/audit_today"]:
                                send_telegram_message("⏳ <b>Memeriksa & meng-audit hasil trading hari ini...</b>", target_chat_id=chat_id)
                                try:
                                    from dashboard.backend.routes.audit import (
                                        get_today_audit_summary,
                                        run_audit,
                                    )
                                    run_audit()
                                    info = get_today_audit_summary()
                                    send_telegram_message(_format_today_audit(info), target_chat_id=chat_id)
                                except Exception:
                                    send_telegram_message("Gagal memuat audit hari ini. Coba lagi nanti.", target_chat_id=chat_id)

                            elif text in ["/auditall", "auditall", "audit all", "/audit_all", "/audit", "audit"]:
                                send_telegram_message("⏳ <b>Memuat statistik track record akumulasi...</b>", target_chat_id=chat_id)
                                try:
                                    from dashboard.backend.routes.audit import (
                                        get_audit_recap,
                                        run_audit,
                                    )
                                    run_audit()
                                    recap = get_audit_recap()
                                    send_telegram_message(_format_audit_recap(recap), target_chat_id=chat_id)
                                except Exception:
                                    send_telegram_message("Gagal memuat track record. Coba lagi nanti.", target_chat_id=chat_id)
            except Exception as e:
                print(f"[TELEGRAM] Warning in listener loop: {e!s}")
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


