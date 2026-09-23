"""Helper yfinance dengan timeout + retry/backoff (INF-01).

Semua callsite yf.download wajib lewat sini agar request pasar ramai
tidak menggantung thread worker tanpa batas.
"""
import concurrent.futures
import functools
import random
import threading
import time

import yfinance as yf

YF_TIMEOUT_SEC = 15
YF_MAX_ATTEMPTS = 3
YF_BASE_BACKOFF_SEC = 1.0

# Timeout absolut per percobaan (thread tidak boleh gantung lebih dari ini,
# walau lib yfinance mengabaikan arg timeout di beberapa path).
YF_HARD_TIMEOUT_SEC = 25

# Circuit-breaker sederhana: setelah N gagal beruntun, tolak cepat sementara.
_CB_LOCK = threading.Lock()
_CB_FAILURES = 0
_CB_OPEN_UNTIL = 0.0
_CB_THRESHOLD = 5
_CB_COOLDOWN_SEC = 60.0

# yf.Ticker (news/info) juga bisa gantung -> pakai executor 1-thread + timeout.
_TICKER_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="yf-ticker")


def _circuit_open() -> bool:
    with _CB_LOCK:
        return time.time() < _CB_OPEN_UNTIL


def _record_success() -> None:
    global _CB_FAILURES
    with _CB_LOCK:
        _CB_FAILURES = 0


def _record_failure() -> None:
    global _CB_FAILURES, _CB_OPEN_UNTIL
    with _CB_LOCK:
        _CB_FAILURES += 1
        if _CB_FAILURES >= _CB_THRESHOLD:
            _CB_OPEN_UNTIL = time.time() + _CB_COOLDOWN_SEC
            _CB_FAILURES = 0


def download_with_timeout(*args, **kwargs):
    """yf.download + timeout default + retry/backoff/jitter + circuit-breaker.

    Hard timeout via thread agar lib yang abaikan arg timeout tetap dibatasi.
    Selalu pakai auto_adjust eksplisit + actions=False agar harga konsisten
    (hindari survivorship/corporate-action ambiguity).
    """
    if _circuit_open():
        raise TimeoutError("yfinance circuit-breaker terbuka (terlalu banyak gagal). Coba lagi nanti.")
    kwargs.setdefault("timeout", YF_TIMEOUT_SEC)
    kwargs.setdefault("progress", False)
    kwargs.setdefault("auto_adjust", True)
    kwargs.setdefault("actions", False)
    kwargs.setdefault("threads", False)
    last_err = None
    for attempt in range(1, YF_MAX_ATTEMPTS + 1):
        try:
            fut = _TICKER_EXECUTOR.submit(functools.partial(yf.download, *args, **kwargs))
            df = fut.result(timeout=YF_HARD_TIMEOUT_SEC)
            _record_success()
            return df
        except Exception as e:  # retry semua error jaringan/parsing
            last_err = e
            _record_failure()
            if attempt == YF_MAX_ATTEMPTS:
                break
            sleep = YF_BASE_BACKOFF_SEC * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
            time.sleep(sleep)
    raise last_err if last_err else RuntimeError("yf.download gagal tanpa error tertangkap")


def get_ticker_news(symbol: str, timeout: float = 20.0) -> list:
    """Ambil .news dari yf.Ticker dengan timeout executor (anti-gantung)."""
    def _fetch():
        return getattr(yf.Ticker(symbol), "news", []) or []
    try:
        fut = _TICKER_EXECUTOR.submit(_fetch)
        return fut.result(timeout=timeout)
    except Exception:
        return []


def get_ticker_info(symbol: str, timeout: float = 20.0) -> dict:
    """Ambil .info dari yf.Ticker dengan timeout executor (anti-gantung)."""
    def _fetch():
        return getattr(yf.Ticker(symbol), "info", {}) or {}
    try:
        fut = _TICKER_EXECUTOR.submit(_fetch)
        res = fut.result(timeout=timeout)
        return res if isinstance(res, dict) else {}
    except Exception:
        return {}
