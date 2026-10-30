FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Non-root user (jangan jalan sebagai root)
RUN useradd -m -u 10001 appuser \
    && mkdir -p /app/data /app/logs \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# /healthz: liveness murni, tidak menyentuh DB/model/jaringan (audit B-10).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status==200 else 1)"

# --workers 1 disengaja: cache chart, bucket rate limit, dan semaphore scan
# hidup di memori proses. Dengan 2 worker, tiap worker menyajikan data berbeda
# dan semaphore scan tidak lagi membatasi scan global (audit C-06/B-02).
# Skala vertikal dulu; bila butuh horizontal, pindahkan state ke Redis.
CMD ["uvicorn", "dashboard.backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--timeout-keep-alive", "30", "--limit-concurrency", "100"]
