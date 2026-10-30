"""Alarm operasional untuk scan harian & kesegaran data (audit 2026-10-30).

Tujuan: mengubah "cache bermasalah" dari temuan manual menjadi notifikasi.
Semua fungsi di sini TIDAK PERNAH melempar exception — kegagalan alarm tidak
boleh menjatuhkan scheduler atau endpoint.

Dipakai oleh:
- ``src.scheduler.daily_scheduler`` (job gagal + snapshot basi)
- ``dashboard.backend.main`` endpoint ``/readyz`` (monitoring eksternal)
"""
import json
import os
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.utils.paths import CACHE_FILE

WIB = timezone(timedelta(hours=7))

# Satu alert per jenis per hari WIB, agar Telegram tidak dibanjiri saat job
# diulang-ulang di jendela waktu yang sama.
_alerted_on: dict[str, str] = {}


def now_wib() -> datetime:
    return datetime.now(UTC).astimezone(WIB)


def send_ops_alert(text: str, kind: str = "ops") -> bool:
    """Kirim alert ke Telegram. Return True bila terkirim.

    Bila token tidak diset (dev/test), alert hanya dicetak ke stdout dengan
    prefix ``[ALERT]`` supaya tetap terlihat di log proses.
    """
    body = f"[ALERT] {text}"
    print(body)
    if os.getenv("TESTING") == "true" or "pytest" in sys.modules:
        return False
    if not os.getenv("TELEGRAM_BOT_TOKEN"):
        return False
    try:
        from src.notifications.telegram_bot import send_telegram_message

        res = send_telegram_message(
            f"<b>⚠️ Operasional</b>\n{text}", target_chat_id=os.getenv("TELEGRAM_CHAT_ID")
        )
        return bool(res)
    except Exception as exc:  # noqa: BLE001 - alarm tidak boleh menjatuhkan pemanggil
        print(f"[ALERT] Gagal mengirim alert Telegram: {exc!s}")
        return False


def send_ops_alert_once(text: str, kind: str) -> bool:
    """Seperti :func:`send_ops_alert`, tapi maksimal sekali per hari WIB."""
    today = now_wib().strftime("%Y-%m-%d")
    if _alerted_on.get(kind) == today:
        return False
    _alerted_on[kind] = today
    return send_ops_alert(text, kind=kind)


def snapshot_age_minutes(path: Path | None = None, now: datetime | None = None) -> float | None:
    """Umur snapshot rekomendasi dalam menit, atau ``None`` bila tidak ada.

    Sumber utama ``generated_at`` di JSON; bila field itu hilang/rusak, pakai
    mtime file sebagai perkiraan yang lebih jujur daripada menganggap segar.
    """
    target = path or CACHE_FILE
    try:
        if not target.exists():
            return None
    except OSError:
        return None

    current = (now or now_wib()).astimezone(UTC)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        stamp = payload.get("generated_at") or payload.get("timestamp")
        parsed = datetime.fromisoformat(str(stamp))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=WIB)
        return round((current - parsed.astimezone(UTC)).total_seconds() / 60, 1)
    except (OSError, ValueError, TypeError, AttributeError):
        print(f"[ALERT] generated_at di {target.name} tidak terbaca; pakai mtime file.")

    try:
        mtime = datetime.fromtimestamp(target.stat().st_mtime, tz=UTC)
        return round((current - mtime).total_seconds() / 60, 1)
    except OSError:
        return None


def snapshot_status(path: Path | None = None, max_age_hours: float = 24.0) -> dict:
    """Ringkasan status snapshot untuk ``/readyz`` dan pemantauan."""
    age = snapshot_age_minutes(path)
    if age is None:
        return {
            "snapshot_present": False,
            "age_minutes": None,
            "max_age_hours": max_age_hours,
            "stale": True,
            "reason": "snapshot rekomendasi belum ada",
        }
    stale = age > max_age_hours * 60
    return {
        "snapshot_present": True,
        "age_minutes": age,
        "max_age_hours": max_age_hours,
        "stale": stale,
        "reason": "snapshot lebih tua dari batas" if stale else "ok",
    }


def check_daily_freshness(max_age_hours: float = 24.0) -> dict:
    """Periksa kesegaran snapshot dan kirim alert bila basi (sekali per hari)."""
    status = snapshot_status(max_age_hours=max_age_hours)
    if status["stale"]:
        if status["snapshot_present"]:
            msg = (
                f"Snapshot rekomendasi berumur {status['age_minutes']:.0f} menit "
                f"(batas {max_age_hours:.0f} jam). Scan terjadwal mungkin tidak jalan."
            )
        else:
            msg = "Snapshot rekomendasi tidak ditemukan. Scan terjadwal belum pernah sukses?"
        status["alerted"] = send_ops_alert_once(msg, kind="data-freshness")
    else:
        status["alerted"] = False
    return status
