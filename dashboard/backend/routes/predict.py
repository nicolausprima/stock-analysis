import asyncio
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response

# Konfigurasi path untuk absolute import
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from dashboard.backend.security import require_api_key
from src.config import CACHE_FILE, CACHE_PREV_FILE

DISCLAIMER_F4 = (
    "Konten ini riset kuantitatif untuk edukasi — BUKAN nasihat/rekomendasi investasi. "
    "Saham berisiko rugi. Kinerja masa lalu tidak menjamin hasil. "
    "Keputusan & risiko milik Anda (DYOR)."
)

router = APIRouter()
_executor = ThreadPoolExecutor(max_workers=2)

@router.get("/recommendations")
async def get_recommendations(request: Request, response: Response, force: bool = False):
    """Mengembalikan rekomendasi Top 10 dari snapshot terakhir (read-only).

    Kontrak baru (audit 2026-10-30, C-01): endpoint BACA tidak pernah memicu
    scan dan tidak pernah menolak snapshot karena umur. Umur data dikirim
    eksplisit lewat body ``data_age_hours`` + header ``X-Data-Age`` agar UI
    bisa jujur, bukan menyulap data nyata menjadi data contoh.

    - Default: snapshot terbaru; bila rusak/hilang -> snapshot sebelumnya.
    - ``?force=true``: scan ulang (wajib API key, dibatasi semaphore scan).
    """
    response.headers["Cache-Control"] = "no-store"

    if force:
        require_api_key(request)
        result = await _run_scan_guarded()
        response.headers["X-Data-Age"] = "0"
        return result

    snapshot, age_seconds = _load_snapshot_with_fallback()
    if snapshot is None:
        resp = _fallback_response()
        resp["fallback_reason"] = "no-snapshot-available"
        response.headers["X-Data-Age"] = "unknown"
        return resp

    if age_seconds is not None:
        snapshot = dict(snapshot)
        snapshot["data_age_hours"] = round(age_seconds / 3600, 2)
        response.headers["X-Data-Age"] = str(int(age_seconds))
    return snapshot


async def _run_scan_guarded(worker=None):
    """Jalankan scan di executor dengan penjaga konkurensi "satu scan global".

    Tanpa ini dua request bersamaan menjalankan dua scan penuh pada DB/model
    yang sama dan saling menimpa snapshot (audit 2026-10-30, B-02).
    """
    from dashboard.backend.rate_limit import SCAN_SEMAPHORE

    if not SCAN_SEMAPHORE.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail="Scan lain sedang berjalan. Coba lagi setelah selesai.",
            headers={"Retry-After": "30"},
        )
    try:
        return await asyncio.get_running_loop().run_in_executor(
            _executor, worker or _run_fresh_scan
        )
    finally:
        SCAN_SEMAPHORE.release()


_WIB = timezone(timedelta(hours=7))
_CACHE_TS_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d")


def _parse_cache_timestamp(raw) -> datetime | None:
    """Parse cache timestamp ke datetime WIB sadar-zona. None bila non-tanggal."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip()
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        dt = None
        for fmt in _CACHE_TS_FORMATS:
            try:
                dt = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=_WIB)
    return dt.astimezone(_WIB)


def _load_snapshot(path: Path) -> tuple[dict | None, float | None]:
    """Baca satu snapshot JSON -> ``(payload, age_seconds)``.

    Umur TIDAK dipakai untuk menolak data: snapshot tua tetap lebih jujur
    daripada data contoh. Yang divalidasi hanya bentuk payload.
    """
    if not path.exists():
        return None, None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Snapshot tidak terbaca ({path.name}): {e!s}")
        return None, None

    if not (
        isinstance(data, dict)
        and data.get("status") == "success"
        and (len(data.get("data", [])) >= 1 or data.get("macro_mode") == "BLOCK")
    ):
        print(f"Snapshot tidak valid skema ({path.name})")
        return None, None

    # Snapshot dari versi lama belum punya scan_id: beri id stabil turunan
    # timestamp supaya kontrak "dua request -> scan_id sama" tetap terpenuhi.
    if not data.get("scan_id"):
        data["scan_id"] = f"legacy-{data.get('timestamp') or 'unknown'}"

    ts = _parse_cache_timestamp(data.get("timestamp"))
    if ts is None:
        # Timestamp non-tanggal (mis. sample): hanya diterima di mode TESTING.
        if os.getenv("TESTING") == "true":
            return data, None
        print(f"Snapshot tanpa timestamp valid ({path.name}): {data.get('timestamp')!r}")
        return None, None

    age_seconds = max(
        0.0, (datetime.now(UTC).astimezone(_WIB) - ts).total_seconds()
    )
    return data, age_seconds


def _load_snapshot_with_fallback() -> tuple[dict | None, float | None]:
    """Snapshot terbaru; bila hilang/rusak pakai snapshot sebelumnya."""
    data, age = _load_snapshot(CACHE_FILE)
    if data is not None:
        return data, age

    data, age = _load_snapshot(CACHE_PREV_FILE)
    if data is not None:
        out = dict(data)
        out["fallback_reason"] = "previous-snapshot"
        out["is_sample"] = False
        return out, age
    return None, None


def _run_fresh_scan():
    """Analisa ulang dari data SQLite yang ada. Jika DB lokal kosong (misal di Render), jalankan scan otomatis."""
    if os.getenv("TESTING") == "true":
        return _fallback_response()

    try:
        from src.scheduler.daily_scheduler import run_daily_after_market_job
        res = run_daily_after_market_job(skip_download=True, broadcast_telegram=False)
        if isinstance(res, dict) and res.get("status") == "success" and (len(res.get("data", [])) > 0 or res.get("macro_mode") == "BLOCK"):
            return res

        # Jika DB lokal kosong / fresh deployment di cloud, jalankan scan dengan download data
        res = run_daily_after_market_job(skip_download=False, broadcast_telegram=False)
        if isinstance(res, dict) and res.get("status") == "success" and (len(res.get("data", [])) > 0 or res.get("macro_mode") == "BLOCK"):
            return res
    except Exception as err:
        print(f"Scheduler execution warning: {err!s}")

    return _fallback_response()


def _fallback_response():
    """Graceful fallback untuk CI / environment tanpa model.

    Selalu transparan: is_sample=True + source + fallback_reason agar tidak
    disangka hasil analisis nyata.
    """
    return {
        "status": "success",
        "is_sample": True,
        "source": "fallback-sample",
        "stale": True,
        "fallback_reason": "model-unavailable",
        "disclaimer": DISCLAIMER_F4,
        "timestamp": "Sample Data (Model Unavailable)",
        "total_scanned": 732,
        "data": [
            {
                "ticker": "BBCA.JK",
                "sector": "Finansial",
                "is_leading_sector": True,
                "probability": 82.5,
                "signal": 1,
                "close_price": 9950,
                "target_price": 10250,
                "stop_loss": 9800,
                "rsi": 54.2,
                "rsi_signal": "NETRAL",
                "macd_signal": "BULLISH",
                "trend": "UPTREND",
                "adx": 28.4,
                "rvol": 1.65,
                "risk_reward_ratio": 2.0,
                "kelly_allocation": 16.5,
                "reason": "Harga di atas MA-50, MACD Menguat (Uptrend), Volume Melonjak 1.7x (RVOL Breakout)",
                "sentiment_status": "POSITIF",
                "sentiment_impact": "BOOSTER (+3.0%)"
            },
            {
                "ticker": "BBRI.JK",
                "sector": "Finansial",
                "is_leading_sector": True,
                "probability": 81.0,
                "signal": 1,
                "close_price": 2950,
                "target_price": 3038,
                "stop_loss": 2906,
                "rsi": 44.8,
                "rsi_signal": "OVERSOLD",
                "macd_signal": "BULLISH",
                "trend": "UPTREND",
                "adx": 26.1,
                "rvol": 1.42,
                "risk_reward_ratio": 2.0,
                "kelly_allocation": 15.0,
                "reason": "Oversold (Koreksi Sehat), MACD Menguat (Uptrend)",
                "sentiment_status": "POSITIF",
                "sentiment_impact": "BOOSTER (+3.0%)"
            },
            {
                "ticker": "BMRI.JK",
                "sector": "Finansial",
                "is_leading_sector": True,
                "probability": 79.8,
                "signal": 1,
                "close_price": 6325,
                "target_price": 6515,
                "stop_loss": 6230,
                "rsi": 51.5,
                "rsi_signal": "NETRAL",
                "macd_signal": "BULLISH",
                "trend": "UPTREND",
                "adx": 24.5,
                "rvol": 1.35,
                "risk_reward_ratio": 2.0,
                "kelly_allocation": 14.0,
                "reason": "MACD Menguat (Uptrend), Harga di atas MA-50",
                "sentiment_status": "POSITIF",
                "sentiment_impact": "BOOSTER (+3.0%)"
            },
            {
                "ticker": "BBNI.JK",
                "sector": "Finansial",
                "is_leading_sector": True,
                "probability": 78.4,
                "signal": 1,
                "close_price": 4350,
                "target_price": 4480,
                "stop_loss": 4285,
                "rsi": 47.0,
                "rsi_signal": "NETRAL",
                "macd_signal": "BULLISH",
                "trend": "UPTREND",
                "adx": 23.8,
                "rvol": 1.25,
                "risk_reward_ratio": 2.0,
                "kelly_allocation": 13.5,
                "reason": "MACD Menguat (Uptrend), Akumulasi Volume",
                "sentiment_status": "POSITIF",
                "sentiment_impact": "BOOSTER (+3.0%)"
            },
            {
                "ticker": "TLKM.JK",
                "sector": "Infrastruktur",
                "is_leading_sector": False,
                "probability": 77.9,
                "signal": 1,
                "close_price": 2840,
                "target_price": 2925,
                "stop_loss": 2795,
                "rsi": 42.1,
                "rsi_signal": "OVERSOLD",
                "macd_signal": "BULLISH",
                "trend": "REBOUND",
                "adx": 22.0,
                "rvol": 1.15,
                "risk_reward_ratio": 1.9,
                "kelly_allocation": 12.0,
                "reason": "Oversold (Koreksi Sehat), Momentum Rebound",
                "sentiment_status": "NETRAL",
                "sentiment_impact": "STABIL"
            },
            {
                "ticker": "ASII.JK",
                "sector": "Konsumer Non-Primer",
                "is_leading_sector": False,
                "probability": 76.5,
                "signal": 1,
                "close_price": 4940,
                "target_price": 5088,
                "stop_loss": 4866,
                "rsi": 48.3,
                "rsi_signal": "NETRAL",
                "macd_signal": "BULLISH",
                "trend": "UPTREND",
                "adx": 21.4,
                "rvol": 1.20,
                "risk_reward_ratio": 2.0,
                "kelly_allocation": 11.5,
                "reason": "Harga di atas MA-50, Sinyal Reversal Bullish",
                "sentiment_status": "NETRAL",
                "sentiment_impact": "STABIL"
            },
            {
                "ticker": "PGAS.JK",
                "sector": "Energi",
                "is_leading_sector": True,
                "probability": 75.8,
                "signal": 1,
                "close_price": 1515,
                "target_price": 1560,
                "stop_loss": 1492,
                "rsi": 56.0,
                "rsi_signal": "NETRAL",
                "macd_signal": "BULLISH",
                "trend": "UPTREND",
                "adx": 25.2,
                "rvol": 1.45,
                "risk_reward_ratio": 2.0,
                "kelly_allocation": 12.0,
                "reason": "MACD Golden Cross, Breakout Support",
                "sentiment_status": "POSITIF",
                "sentiment_impact": "BOOSTER (+3.0%)"
            },
            {
                "ticker": "UNTR.JK",
                "sector": "Perindustrian",
                "is_leading_sector": False,
                "probability": 74.9,
                "signal": 1,
                "close_price": 24800,
                "target_price": 25540,
                "stop_loss": 24420,
                "rsi": 52.4,
                "rsi_signal": "NETRAL",
                "macd_signal": "BULLISH",
                "trend": "UPTREND",
                "adx": 23.0,
                "rvol": 1.18,
                "risk_reward_ratio": 1.9,
                "kelly_allocation": 11.0,
                "reason": "Harga di atas MA-50, Momentum Komoditas",
                "sentiment_status": "NETRAL",
                "sentiment_impact": "STABIL"
            },
            {
                "ticker": "PTBA.JK",
                "sector": "Energi",
                "is_leading_sector": True,
                "probability": 74.2,
                "signal": 1,
                "close_price": 2410,
                "target_price": 2482,
                "stop_loss": 2374,
                "rsi": 49.1,
                "rsi_signal": "NETRAL",
                "macd_signal": "BULLISH",
                "trend": "UPTREND",
                "adx": 24.1,
                "rvol": 1.30,
                "risk_reward_ratio": 2.0,
                "kelly_allocation": 11.5,
                "reason": "MACD Menguat (Uptrend), Akumulasi Institusi",
                "sentiment_status": "POSITIF",
                "sentiment_impact": "BOOSTER (+3.0%)"
            },
            {
                "ticker": "ADRO.JK",
                "sector": "Energi",
                "is_leading_sector": True,
                "probability": 73.5,
                "signal": 1,
                "close_price": 3650,
                "target_price": 3760,
                "stop_loss": 3595,
                "rsi": 53.0,
                "rsi_signal": "NETRAL",
                "macd_signal": "BULLISH",
                "trend": "UPTREND",
                "adx": 26.5,
                "rvol": 1.55,
                "risk_reward_ratio": 2.0,
                "kelly_allocation": 12.5,
                "reason": "MACD Menguat, Trendline Support, Volume Inflow",
                "sentiment_status": "POSITIF",
                "sentiment_impact": "BOOSTER (+3.0%)"
            }
        ]
    }




@router.get("/sync")
async def sync_market_data(request: Request):
    """Endpoint manual untuk memaksa sinkronisasi batch data 700+ saham & kalkulasi rekomendasi baru."""
    require_api_key(request)
    try:
        from src.scheduler.daily_scheduler import run_daily_after_market_job

        res = await _run_scan_guarded(run_daily_after_market_job)
        return {"status": "success", "message": "Sinkronisasi data 700+ saham selesai.", "data": res}

    except HTTPException:
        # 409 "scan sedang berjalan" harus sampai ke klien apa adanya,
        # bukan dibungkus jadi 500.
        raise
    except Exception as err:
        print(f"[SYNC] Gagal melakukan sinkronisasi data pasar: {err!s}")
        raise HTTPException(
            status_code=500,
            detail="Gagal melakukan sinkronisasi data pasar. Silakan coba lagi nanti."
        )
