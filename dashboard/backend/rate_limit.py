"""Rate limit terpusat untuk endpoint mahal (LLM, scan, broadcast).

- General /api: 120 req/menit/IP (di main.py).
- Endpoint mahal: batas jauh lebih ketat + semaphore konkurensi agar
  operasi 120-detik / scan 700+ ticker / broadcast tidak bisa di-DoS.
"""
import threading
import time

# Batas per-IP per 60 detik untuk path mahal: (limit, window_sec)
EXPENSIVE_LIMITS: dict[str, tuple[int, int]] = {
    "/api/narasi": (10, 60),
    "/api/narasi/multi-agent": (10, 60),
    "/api/sync": (5, 60),
    "/api/recommendations": (5, 60),  # hanya berlaku saat force=true (dicek di middleware)
    "/api/telegram/": (5, 60),  # prefix match
    "/api/audit/run": (10, 60),
    "/api/audit/seed-simulation": (3, 300),
}

_buckets: dict[str, list[float]] = {}
_lock = threading.Lock()

# Batasi konkurensi LLM global agar worker tidak habis (request 120s).
LLM_SEMAPHORE = threading.Semaphore(2)
# Batasi konkurensi fresh-scan global.
SCAN_SEMAPHORE = threading.Semaphore(1)


def _matched_limit(path: str, query: str = "") -> tuple[int, int] | None:
    # /api/recommendations hanya mahal saat force=true
    if path == "/api/recommendations" and "force=true" not in query.lower():
        return None
    for prefix, (limit, window) in EXPENSIVE_LIMITS.items():
        if path == prefix or (prefix.endswith("/") and path.startswith(prefix)):
            return (limit, window)
        if path == prefix:
            return (limit, window)
    return None


def check_expensive_limit(ip: str, path: str, query: str = "") -> tuple[bool, int]:
    """Return (allowed, retry_after_sec). True jika lolos."""
    matched = _matched_limit(path, query)
    if not matched:
        return True, 0
    limit, window = matched
    now = time.time()
    key = f"{ip}:{path.split('?')[0]}"
    with _lock:
        bucket = [t for t in _buckets.get(key, []) if now - t < window]
        if len(bucket) >= limit:
            retry = int(window - (now - bucket[0])) + 1 if bucket else window
            return False, max(retry, 1)
        bucket.append(now)
        _buckets[key] = bucket
        # Bound memory
        if len(_buckets) > 5000:
            oldest = sorted(_buckets, key=lambda k: _buckets[k][-1] if _buckets[k] else 0)[:2500]
            for k in oldest:
                _buckets.pop(k, None)
    return True, 0
