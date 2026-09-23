# Conventions — Hermes

Kembali ke: [[project-overview]]. Aturan ini menang saat Hermes menulis/mengedit repo ini.

## Bahasa dan gaya jawab

- Jawab Bahasa Indonesia, ringkas ala caveman-lite (teknis tetap eksak).
- Klaim tanpa `path:line` + perintah verifikasi = hapus, bukan dipertahankan.

## Edit kode

- Baca file dulu (`read_file`), ubah via `patch`/`write_file`. Jangan cetak blok kode sebagai pengganti edit.
- Sentuh hanya yang diminta; tanpa refactor acak, tanpa rename, tanpa reformat.
- Tanpa commit/push kecuali diminta eksplisit.
- Jangan baca/cetak/commit secret (`.env`, token, credential).
- Notebook = JSON: jaga array string sel, lalu `python -m json.tool` tiap edit.
- Artefak (`models/*.pkl`, `data/processed/`, `*.db`, `data/*.json`) jangan di-commit kecuali sadar; `data/signals_audit.db` selalu revert.

## Kontrak ML (jangan dilanggar)

- Label: next-session open-to-close ≥0.03. Satu helper label (S-4 masih pending duplikasi).
- Warm-up indikator = NaN lalu drop; imputasi median fit-train-only. IHSG flat 0.0 hanya untuk kalender libur, bukan indikator.
- Serve = `build_serve_matrix` (kolom urut `expected_cols`, tolak `Tick_*`, tolak NaN). Fundamental stale >120 hari ditolak; None/NaN = n/a, bukan murah.
- Backtest = fill next-bar open + slippage, lot-100, cap 10% volume, komisi 0.15/0.25%.
- Setiap retrain wajib tulis `model_card.json` (target, horizon, cutoff, embargo, feature_cols).

## Backend/infra

- Semua `yfinance` runtime via `dashboard/backend/yf_client.py` (`download_with_timeout`, hard 25 dtk). Mentah di `main_cli.py`/`scripts/` = out-of-scope runtime, tandai.
- Token/secret hanya via env/secret manager, baca per-call, tidak pernah di-log. Telegram fail-closed (tanpa allowlist = tolak semua).
- Endpoint sensitif wajib `X-API-Key`; production fail-startup tanpa `API_AUTH_TOKEN`. Chart clamp 1–365 hari; narasi escape HTML + validator + disclaimer.
- DB: transaksi eksplisit + rollback + close di finally; DuckDB serialisasi via `_db_lock`.

## Frontend/legal-copy

- Klaim profit terlarang: `High-Conviction`, `Realized …`, `Deploy Alpha`, `Get Tomorrow`, `pasti/janji untung`, `100% … Engine`. Nilai = `SIM-WIN`/`SIM-LOSS`, konteks `SIMULASI BACKTEST — bukan hasil nyata`.
- A11y: target sentuh ≥44px, `:focus-visible`, `prefers-reduced-motion`, tab pakai pola tablist/tab/tabpanel + hash routing, loader satu live region, error `role=alert` + fokus terkelola.
- Cek JS: `node --check dashboard/frontend/js/app.js`.

## Verifikasi wajib tiap sesi kerja

```
uv run pytest tests/ -q
uv run ruff check . 2>&1 | tail -2
python -m json.tool notebooks/02_Preprocessing.ipynb > /dev/null && echo NOTEBOOK_VALID
node --check dashboard/frontend/js/app.js && echo JS_OK
```

Update [[progress/2026-09-23-verifikasi-dan-sisa]], [[todo]], [[known-issues]], dan `../VERIFICATION_REPORT_2026-09-23.md` tiap ada perubahan S.
