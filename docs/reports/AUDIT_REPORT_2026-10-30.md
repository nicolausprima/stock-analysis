# Laporan Audit Menyeluruh — 2026-10-30 — branch `developments`

**Verdict rilis: BLOKIR untuk trafik publik.** 5 temuan P0, 12 P1. Sistem bisa berjalan, tetapi lapisan cache punya cacat desain yang membuat data yang tampil ke pengguna **tidak deterministik** (kadang data contoh, kadang scan 48 detik, kadang data 4 hari lalu) dan angka audit performa **tidak akurat** karena P&L LOSS di-hardcode.

Audit dijalankan sebagai 4 workstream paralel ("agent") + 1 koordinator:

| Workstream | Ruang lingkup | Metode |
|---|---|---|
| A · Cache & Konsistensi Data | `data/*`, `src/scheduler`, `routes/predict.py`, `routes/chart.py`, `routes/audit.py`, git/CI | inspeksi kode + probe HTTP nyata + inspeksi git index & SQLite |
| B · Backend/API | `dashboard/backend/**` (main, security, rate_limit, yf_client, 7 router) | review kode + uji endpoint via `TestClient` + pengukuran latency |
| C · Frontend/UX | `index.html`, `dashboard.html`, `app.js`, `style.css` | review kode + pengukuran ukuran aset + audit XSS/CSP/a11y statis |
| D · Data/ML & Ops | `src/features`, `src/screener`, `src/collector`, `src/database`, Docker/CI | review kode + query langsung ke SQLite audit |

Batasan: tidak ada browser/DevTools (tidak ada screenshot), tidak ada load test multi-worker, dan tidak ada deploy. Semua angka di bawah diukur di mesin lokal dengan kode di working tree saat audit.

---

## 1. Bukti terukur (bukan asumsi)

Semua angka berikut dihasilkan saat audit ini berjalan.

| # | Uji | Hasil |
|---|---|---|
| E1 | `GET /api/recommendations` dengan cache `2026-10-26 16:00:02` | **48.360 ms**, memicu full rescan sinkron; log: `Cache basi >24 jam (umur 3 days, 19:33:17)` |
| E2 | Header response `/`, `/dashboard`, `/css/style.css`, `/js/app.js`, `/api/*` | **semua `Cache-Control: None`**; HTML/CSS/JS punya `ETag`+`Last-Modified`, API tidak punya keduanya |
| E3 | Ukuran aset frontend | `lightweight-charts.js` **160 KB**, `app.js` **79 KB**, `style.css` **78 KB**, `index.html` **170 KB** (di dalamnya **77 KB CSS inline**) → ±317 KB render-blocking |
| E4 | Isi `data/signals_audit.db` | 516 sinyal `source='scan'`: **403 WIN / 104 LOSS / 9 PENDING** → win rate **79,5%**, bukan 85,9% |
| E5 | Status git file DB | `UU data/signals_audit.db` — **konflik merge belum selesai**, index punya 3 stage (base/ours/theirs); `-wal` 8 KB & `-shm` 32 KB untracked |
| E6 | Duplikasi CSS | 207 selector di landing vs 299 di `style.css`, **11 overlap** dengan aturan berbeda (`.hero-title`, `.footer`, `.legal-microcopy`, `.sr-only`, …) |
| E7 | `SCAN_SEMAPHORE` | dideklarasikan (`rate_limit.py:27`), **0 pemakaian** di seluruh repo |
| E8 | `src/scheduler/daily_scheduler.py` | **tidak punya `if __name__ == "__main__"`** → perintah worker di `docker-compose.yml` (komentar) tidak melakukan apa pun |
| E9 | `.env` | tidak ter-track git (aman); `.env.example` ter-track |

> Catatan transparansi: E1 mengeksekusi jalur produksi apa adanya. Efek sampingnya nyata: `data/latest_recommendations.json` ditulis ulang (timestamp `2026-10-30 11:34:07`, 4 sinyal, mode `BLOCK`) dan 4 sinyal `2026-10-30` masuk ke `data/signals_audit.db`. Itu justru bukti bahwa endpoint baca punya efek tulis.

---

## 2. Klaster CACHE — akar masalah yang Anda rasakan

Ini bagian terpenting. Keluhan "cache sering bermasalah" bukan satu bug, tapi **5 cacat yang saling menumpuk**.

### Arsitektur cache saat ini (de facto)

```
[GitHub Action 16:05 WIB] --git commit/push--> [repo data/signals_audit.db + latest_recommendations.json]
                                                          |
[Web process uvicorn --workers 2]                          |
  worker-1: chart_cache{}, HEADLINE_CACHE{}, rate_buckets |
  worker-2: chart_cache{}, HEADLINE_CACHE{}, rate_buckets |  <-- state terpisah
        |                                                 |
        +--> baca JSON (tanpa lock, tanpa atomic) <--------+
        +--> tulis JSON (dari web process saat cache basi / ?force=true)
```

Tidak ada satu pun pemilik tunggal data. Penulis cache ada tiga: GitHub Action, web process (`?force=true`, cache-miss), dan scheduler in-process bila `ENABLE_SCHEDULER=true`. Pembaca ada dua worker dengan cache memori masing-masing.

### C-01 · Cache kedaluwarsa keras 24 jam → data contoh atau rescan 48 detik — **P0**
- **Lokasi:** `dashboard/backend/routes/predict.py:82-113` (ambang di `:103`), fallback `:135-160`, keputusan auth `:47-53`.
- **Bukti:** E1. Cache tertinggal 4 hari → `_read_cache()` menolak → di dev (token kosong) `is_authorized()` = True → `_run_fresh_scan()` jalan **sinkron di request** 48 detik. Di produksi (token diset) jalur anonim berakhir di `_fallback_response()` dengan `is_sample: true` → UI menampilkan **DATA CONTOH** (BBCA 9950, dst) seolah hasil analisis.
- **Dampak:** pengguna melihat data palsu, atau halaman menggantung ±1 menit, tergantung environment. Tidak ada "last known good". Kalau scan gagal 1 hari (libur/action merah), seluruh situs jatuh ke data contoh.
- **Perbaikan:** hapus expiry keras. Simpan snapshot `latest.json` + `latest.prev.json`; sajikan snapshot terakhir dengan metadata `age_hours`, dan **jangan pernah** mengganti data nyata dengan sampel. Pisahkan endpoint: `GET /api/recommendations` **read-only** (tidak boleh memicu scan), `POST /api/admin/rescan` untuk menulis.

### C-02 · Penulisan JSON tidak atomik → pembaca bisa melihat file setengah jadi — **P0**
- **Lokasi:** `src/scheduler/daily_scheduler.py:410-412` (`open(CACHE_FILE,'w')` + `json.dump` langsung ke path final).
- **Bukti:** kode; `_read_cache()` (`predict.py:88-92`) menangkap `json.JSONDecodeError` lalu mengembalikan `None` → berujung ke C-01.
- **Dampak:** race klasik. Selama ±100 ms penulisan, request yang masuk mendapat JSON terpotong → dianggap cache rusak → rescan/sampel. Di 700+ ticker, payload lebih besar → jendela race lebih lebar.
- **Perbaikan:** tulis ke `tmp` di direktori yang sama → `f.flush(); os.fsync()` → `os.replace(tmp, CACHE_FILE)` (atomik di POSIX & NTFS). Tambahkan `schema_version`, `scan_id`, `generated_at` (ISO-8601 dengan offset `+07:00`), `data_date`.

### C-03 · DB audit di-commit ke git + konflik merge belum selesai + WAL/SHM liar — **P0**
- **Lokasi:** `.gitignore:20-21` (`!data/signals_audit.db`), `.gitattributes` (hanya mengatur `data/stock_market.db`, **bukan** `signals_audit.db`), `.github/workflows/daily_scan.yml:112-129`, status git E5.
- **Bukti:** E5 — `git ls-files -u` mengembalikan 3 stage untuk file yang sama; `-wal`/`-shm` untracked; file `.db` ikut berubah setiap scan.
- **Dampak:** (a) konflik biner tidak bisa di-merge → DB bisa "kembali" ke snapshot lama atau berisi campuran; (b) `-wal` berisi transaksi yang belum checkpoint — kalau `.db` di-commit tanpa `-wal`, commit kehilangan baris terbaru; (c) setiap hari repo membesar karena blob SQLite baru; (d) `_ensure_valid_db()` (`audit.py:25-45`) akan **menghapus** file kalau header bukan `SQLite format 3` — pada konflik/LFS pointer, riwayat audit hilang permanen.
- **Perbaikan:** `git rm --cached data/signals_audit.db`, tambahkan `data/*.db`, `data/*.db-wal`, `data/*.db-shm` ke `.gitignore`, selesaikan konflik index (`git checkout --ours/theirs` **secara sadar**, setelah backup), dan pindahkan artefak ke release/artifact/object storage. DB adalah state runtime, bukan source code.

### C-04 · Tidak ada satu pun header cache di seluruh aplikasi — **P1**
- **Lokasi:** `dashboard/backend/main.py:150-170`; semua router.
- **Bukti:** E2. HTML/CSS/JS hanya punya `ETag`+`Last-Modified` (Starlette default) → browser memakai **heuristic caching** (≈10% umur file sejak `Last-Modified`). `index.html` yang berumur 2 bulan bisa dipakai dari cache hingga ±6 hari tanpa revalidasi. API tidak punya `Cache-Control`/`ETag`, jadi rentan di-cache heuristik oleh browser dan bfcache.
- **Dampak:** setelah deploy, sebagian pengguna tetap menjalankan JS/CSS/HTML lama; sebaliknya aset berversi tetap direvalidasi setiap navigasi (buang round-trip).
- **Perbaikan (kontrak minimum):**

| Path | Header |
|---|---|
| `/`, `/dashboard`, `*.html` | `Cache-Control: no-cache` (wajib revalidasi, boleh 304) |
| `/assets/<hash>.*` (CSS/JS/gambar) | `Cache-Control: public, max-age=31536000, immutable` |
| `/api/recommendations`, `/api/audit/*` | `Cache-Control: no-store` + `X-Data-Age: <detik>` |
| `/api/chart/*` | `public, max-age=60, stale-while-revalidate=300` (atau `no-store` bila sederhana) |

Implementasi paling kecil: subclass `StaticFiles` yang men-set header berdasarkan path, plus `JSONResponse` middleware untuk `/api/`.

### C-05 · Cache busting manual `?v=` dan versinya sudah tidak sinkron — **P1**
- **Lokasi:** `dashboard/frontend/dashboard.html:13` (`style.css?v=25`), `:473` (`app.js?v=27`).
- **Bukti:** dua nomor berbeda; tidak ada otomasi. `index.html` bahkan tidak memuat `style.css` (semua inline).
- **Dampak:** setiap kali Anda mengubah `app.js` dan lupa menaikkan `v`, pengguna lama tetap memakai JS lama — ini penyebab paling umum "sudah saya fix tapi masih bug yang sama". Sebaliknya `style.css?v=25` yang tidak pernah naik berarti CSS Anda **tidak pernah** ter-invalidate paksa.
- **Perbaikan:** ganti ke nama ber-hash (`app.<hash>.js`) yang di-generate saat build, atau naikkan versi otomatis dari hash isi file di server. Hapus query manual.

### C-06 · Semua cache memori terpisah per worker (`--workers 2`) — **P1**
- **Lokasi:** `Dockerfile:29`, `docker-compose.yml:20`; `routes/chart.py:13-17`; `routes/sentiment_filter.py:9-11`; `main.py:36-38`; `src/config.py:76`.
- **Bukti:** kamus/semaphore di level modul; proses uvicorn terpisah tidak berbagi memori. `src/config.py:89` juga men-snapshot `TICKERS` saat import.
- **Dampak:** `GET /api/chart/X` bisa memberi data berbeda antar request (worker A cache 5 menit, worker B fetch baru); rate limit efektif 2× batas; headline cache terisi ganda; `tickers.txt` baru tidak terbaca di worker long-running sampai restart.
- **Perbaikan:** pilih satu — (a) `--workers 1` + `--limit-concurrency` (paling murah untuk beban ini), atau (b) pindahkan state bersama ke Redis/SQLite dengan TTL, atau (c) terima inkonsistensi dan hapus cache memori chart (biarkan HTTP cache yang bekerja). Untuk `TICKERS`, baca per-job, bukan per-import.

### C-07 · Cache chart tidak pernah di-invalidate setelah scan — **P1**
- **Lokasi:** `routes/chart.py:30-40, 84-89`.
- **Bukti:** key hanya `ticker_days`; TTL 60 s (intraday) / 300 s (harian); tidak ada hook dari `run_daily_after_market_job`.
- **Dampak:** setelah scan 16:05, chart masih menyajikan candle lama hingga 5 menit; saat intraday, pengguna melihat harga yang "tidak cocok" dengan rekomendasi.
- **Perbaikan:** tambahkan `cache_epoch` global yang dinaikkan scheduler setelah scan (atau key berisi `data_date`), dan set `max-age` pendek di response.

### C-08 · Badge freshness salah untuk pengguna di luar WIB — **P2**
- **Lokasi:** `dashboard/frontend/js/app.js:96-120` (`new Date(String(tsRaw).replace(' ','T'))`).
- **Bukti:** server mengirim `"2026-10-26 16:00:02"` (WIB, tanpa offset). String tanpa zona di-parse sebagai **waktu lokal browser**.
- **Dampak:** pengguna di UTC melihat umur data −7 jam → badge "SEGERA" padahal data 4 hari; pengguna di WITA/WIT sebaliknya.
- **Perbaikan:** kirim timestamp ber-offset (`2026-10-26T16:00:02+07:00`) atau epoch milidetik; frontend cukup `new Date(epoch)`.

### C-09 · CI menulis DB ke repo → memicu konflik yang jadi C-03 — **P2**
- **Lokasi:** `.github/workflows/daily_scan.yml:112-129` (`git pull --rebase ... || true` lalu `git add -f` DB).
- **Bukti:** `|| true` menyembunyikan kegagalan rebase; commit berikutnya bisa berjalan di atas index yang belum bersih.
- **Dampak:** persis kondisi E5.
- **Perbaikan:** hentikan commit artefak; upload sebagai artifact/release. Kalau tetap butuh persistensi, pakai volume/DB terkelola, bukan git.

### C-10 · "INDEXED BUS <5 ms" di landing bukan hasil pengukuran — **P2**
- **Lokasi:** `dashboard/frontend/index.html:3725-3732`.
- **Bukti:** angka hardcoded; pengukuran nyata: baca JSON ±beberapa ms, tetapi jalur cache-miss **48.360 ms** (E1).
- **Dampak:** klaim performa tidak bisa dipertahankan; bertabrakan dengan pengalaman pengguna.
- **Perbaikan:** ganti dengan metrik yang diukur server (`X-Data-Age`, durasi scan terakhir) atau hapus.

---

## 3. Backend / API

### B-01 · `GET /api/audit/track-record` menjalankan audit jaringan & bisa men-seed backtest — **P0**
- **Lokasi:** `dashboard/backend/routes/audit.py:128-152`.
- **Bukti:** setiap GET: `init_db()` → bila DB kosong `seed_simulation_audit()` (unduh 6 bulan × 10 ticker) lalu `run_audit()`; bila tidak kosong tetap `run_audit()`. `run_audit()` (`:234-370`) melakukan query DB lokal **atau** `download_with_timeout` per sinyal PENDING, dengan retry 3× dan hard timeout 25 s. Endpoint ini **tanpa** `require_api_key`.
- **Dampak:** setiap kunjungan halaman memicu kerja berat + menulis status WIN/LOSS. Dengan 9 sinyal PENDING sekarang, worst case ≈ 9 × 3 × 25 s. Ini sendiri adalah penyebab "dashboard kadang lambat/berat". Endpoint baca yang mengubah state juga membuat audit tidak reprodusibel.
- **Perbaikan:** pisahkan — `GET /audit/track-record` hanya baca DB (cepat, <10 ms). Audit dipindah ke job terjadwal/`POST /api/audit/run` ber-auth. Seed hanya lewat aksi eksplisit.

### B-02 · Tidak ada penjaga konkurensi nyata untuk scan — **P1**
- **Lokasi:** `predict.py:26` (`ThreadPoolExecutor(max_workers=2)`), `:36-53`; `rate_limit.py:27` (`SCAN_SEMAPHORE`, **tidak dipakai** — E7).
- **Bukti:** `?force=true` dan jalur cache-miss keduanya `run_in_executor(_run_fresh_scan)`; semaphore pemindaian tidak pernah di-acquire.
- **Dampak:** dua request bersamaan = dua scan paralel pada DB/model yang sama (CPU 2 core di compose), saling menimpa cache; `--limit-concurrency 100` tidak menolong karena scan berjalan di thread pool internal.
- **Perbaikan:** acquire `SCAN_SEMAPHORE(blocking=False)` → 409/429 bila sibuk; kembalikan `202 Accepted` + status job, bukan menahan koneksi HTTP.

### B-03 · Rate limit memakai `request.client.host` → di belakang proxy semua pengguna satu bucket — **P1**
- **Lokasi:** `main.py:42`; tidak ada penanganan `X-Forwarded-For`/`Forwarded` di seluruh backend.
- **Bukti:** grep: hanya satu kemunculan `request.client.host`; tidak ada middleware proxy header.
- **Dampak:** di Render/Railway/Nginx/Cloudflare, `client.host` adalah IP proxy → **seluruh pengguna berbagi 120 req/menit**. Satu pengguna yang membuka 10 kartu (10 chart + 10 narasi) bisa membuat semua orang kena 429. Di lokal, batas ini terlihat "normal" sehingga bug tidak terasa saat development.
- **Perbaikan:** percayai `X-Forwarded-For` hanya dari proxy tepercaya (env `TRUSTED_PROXY_IPS`, ambil hop paling kanan yang bukan proxy), atau rate limit per API key + per sesi, bukan per IP mentah.

### B-04 · Koneksi SQLite tidak ditutup (context manager bukan `close`) — **P2**
- **Lokasi:** `audit.py:62-74` (`init_db`), `:240`, `:398`, `:529`, dan `save_signals_to_db`.
- **Bukti:** `with get_db_connection() as conn:` pada `sqlite3.Connection` hanya commit/rollback, **tidak** menutup. Hanya `get_track_record()` yang memanggil `conn.close()` (`:220`); sisanya bergantung pada GC.
- **Dampak:** penumpukan handle/lock; pada beban tinggi memicu `database is locked` (timeout 60 s) atau `too many open files`, terutama dengan `--workers 2` + scheduler.
- **Perbaikan:** `contextlib.closing(...)` atau helper `@contextmanager` yang `try/finally: conn.close()`.

### B-05 · DB dihapus otomatis bila header tidak dikenali — **P2**
- **Lokasi:** `audit.py:25-45`, `src/database/market_db.py:17-35`.
- **Dampak:** kegagalan yang terlihat seperti "cache/database kosong" lalu sistem men-seed ulang — data hilang tanpa backup. Berbahaya bila file pernah di-LFS, terkena konflik merge, atau terpotong saat copy.
- **Perbaikan:** jangan `unlink`. Ganti nama ke `.corrupt-<ts>` lalu buat baru; laporkan lewat log/health.

### B-06 · Endpoint baca tanpa batas & tanpa paginasi — **P2**
- **Lokasi:** `audit.py:158-160` (`SELECT * ...` semua baris), `:403-410` (`get_audit_recap` full scan).
- **Dampak:** payload tumbuh linear; 516 baris sekarang, akan ribuan. Setiap page-load memuat semuanya dan frontend memfilter di klien.
- **Perbaikan:** `LIMIT/OFFSET` atau filter `from/to` + agregasi di SQL (bukan Python loop).

### B-07 · `asyncio.get_event_loop()` di dalam `async def` — **P2**
- **Lokasi:** `predict.py:40`, `:53`, `:373`.
- **Dampak:** deprecated sejak 3.10; di 3.12+ memunculkan `DeprecationWarning`, dan pada konteks tanpa loop bisa error. Repo sudah memakai Python 3.11 (CI).
- **Perbaikan:** `asyncio.get_running_loop()` / `asyncio.to_thread`.

### B-08 · Penjaga endpoint mahal dibungkus `except Exception: pass` — **P2**
- **Lokasi:** `main.py:62-73`.
- **Dampak:** satu bug di `check_expensive_limit` mematikan proteksi LLM/scan **tanpa jejak** di log. Kombinasi dengan B-02 = jalur DoS.
- **Perbaikan:** log exception; fail-closed untuk endpoint mahal.

### B-09 · Tidak ada kompresi response — **P3**
- **Lokasi:** `main.py:150-153` (hanya RateLimit & SecurityHeaders).
- **Dampak:** `index.html` 170 KB + `style.css` 78 KB + `app.js` 79 KB dikirim mentah; `GZipMiddleware` memotong ±70-80% untuk teks.
- **Perbaikan:** `app.add_middleware(GZipMiddleware, minimum_size=1024)`.

### B-10 · Healthcheck memakai endpoint bisnis — **P3**
- **Lokasi:** `Dockerfile:26-27`, `docker-compose.yml:38-43` → `/api/telegram/status`.
- **Dampak:** health ikut terpengaruh rate limit dan logika bisnis; tidak ada `/healthz` murni.
- **Perbaikan:** `GET /healthz` → `{"ok": true}` + cek file DB/model, tanpa dependensi jaringan.

---

## 4. Data / ML

### D-01 · P&L LOSS di-hardcode −1,5% padahal SL berbasis ATR (−1,2%…−2,0%) — **P0**
- **Lokasi:** `audit.py:172, 342, 350, 418, 479-480, 570, 755, 761, 774`; SL dihitung di `routes/features.py:100-118` (`sl_delta` clamp 1,2%-2,0%).
- **Bukti:** sembilan tempat menulis `real_ret = -1.5` tanpa melihat `stop_loss` sinyal tersebut.
- **Dampak:** win rate dan total profit di rekap, equity curve, dan broadcast Telegram **tidak akurat**. Sinyal dengan SL 1,2% dilaporkan rugi 1,5% (lebih buruk), yang SL 2,0% dilaporkan 1,5% (lebih baik). Semua keputusan rebalancing/rotasi yang memakai angka ini ikut bias.
- **Perbaikan:** hitung `real_ret = (stop_loss - entry_price) / entry_price * 100` (atau harga eksekusi sebenarnya) dan simpan `exit_price`. Hapus semua konstanta −1,5/-3,0 dari jalur rekap.

### D-02 · Angka publik tidak cocok dengan database — **P1**
- **Lokasi:** `index.html:3698-3708` ("85.9%", "298 SIM-WIN / 49 SIM-LOSS", "+820.5%").
- **Bukti:** E4: DB berisi 403 WIN / 104 LOSS → 79,5%. Tidak ada sumber untuk 298/49.
- **Dampak:** klaim marketing yang tidak dapat direproduksi. Ini juga risiko legal (sudah tercatat sebagai temuan hukum di `AUDIT_REPORT_2026-09-22.md`).
- **Perbaikan:** render dari API (`/api/audit/recap`) atau hapus angka; beri label "sampel/simulasi" yang eksplisit.

### D-03 · Dua sumber kebenaran harga: SQLite vs DuckDB — **P1**
- **Lokasi:** scheduler & API memakai `src/database/market_db.py` (SQLite `stock_market.db`); backtest memakai `src/database/duckdb_market.py` (`stock_market.duckdb`); fundamental di `duckdb_fundamental.py`.
- **Bukti:** grep pemakaian: `duckdb_market` hanya dipakai `src/backtest/vectorized_backtest.py` + test; pipeline harian menulis ke SQLite saja.
- **Dampak:** backtest dan serve bisa memakai harga berbeda (hasil backtest tidak merepresentasikan produksi). Dua writer berbeda juga memperbesar risiko lock.
- **Perbaikan:** tetapkan satu store (DuckDB untuk OLAP + SQLite untuk audit state, atau satu saja) dan buat job sinkronisasi eksplisit; dokumentasikan di `memory/arsitektur.md`.

### D-04 · Skor backtest rule-based disajikan seolah probabilitas model — **P2**
- **Lokasi:** `audit.py:619-790` (base_score 68 + bonus → 65-88,5).
- **Bukti:** `seed_simulation_audit` mengisi `probability` dan `probability_raw` dengan angka rule-based, bukan keluaran XGBoost.
- **Dampak:** kolom "Skor keyakinan" di tabel audit mencampur dua jenis angka; pengguna menyimpulkan model memprediksi 88% padahal itu formula.
- **Perbaikan:** tambahkan kolom `score_kind` (`model`/`rule`) dan tampilkan badge berbeda; jangan isi `probability_raw` dengan skor rule.

### D-05 · Double-escaping teks narasi — **P2**
- **Lokasi:** backend `security.py:104-116` (`html.escape`) + `narasi.py:167`, lalu frontend `app.js:944` (`container.textContent = data.narasi`) dan `esc(d.bull_case)`.
- **Dampak:** teks yang mengandung `&`, `<`, `>` tampil sebagai `&amp;` / `&lt;` di UI. Untuk multi-agent, `esc()` meng-escape **lagi** → `&amp;lt;`.
- **Perbaikan:** pilih satu lapisan. Karena frontend memakai `textContent`/`esc()`, backend cukup memvalidasi & memotong panjang, tidak meng-escape.

### D-06 · Pembagian tanpa proteksi nol di embedding — **P2**
- **Lokasi:** `src/features/embedding.py` (`Embed_SMA20_Ratio`, `Embed_SMA50_Ratio`, `Embed_Volatility_ATR`).
- **Dampak:** `inf` → `NaN` (`replace` di akhir) → `build_serve_matrix` menolak ticker (`screener.py:70-78`). Untuk saham dengan SMA=0/ATR=0 (data tipis, suspend), ticker hilang diam-diam dari universe — bukan crash, tapi coverage menyusut tanpa terlihat.
- **Perbaikan:** guard `np.where(denom > 0, num/denom, 0.0)` dan catat jumlah ticker yang di-skip per scan ke payload (`skipped_reason`).

### D-07 · Dua implementasi pipeline yang harus dijaga sinkron — **P3**
- **Lokasi:** `src/screener.py:main()` vs `src/scheduler/daily_scheduler.py:run_daily_after_market_job()`.
- **Dampak:** perbaikan fitur di satu jalur mudah tertinggal di jalur lain (mis. `build_serve_matrix` sudah dipakai keduanya, tetapi `probability*100` vs fraksi berbeda). Ada keputusan lama `2026-09-22-paritas-pipeline-tunggal.md` — pastikan benar-benar diterapkan.
- **Perbaikan:** satu fungsi `compute_signals()` dipakai CLI & scheduler.

---

## 5. Frontend / UX

### F-01 · CSS ganda 155 KB dengan token yang sudah menyimpang — **P1**
- **Lokasi:** `index.html:18-2600` (inline `<style>` 77 KB) vs `css/style.css` (78 KB).
- **Bukti:** E6 — 11 selector sama dengan aturan berbeda; variabel kanonik berbeda (`--c-muted` di landing `#595959`, di `style.css` berbeda; `--c-surface` vs `--c-card`).
- **Dampak:** setiap perubahan desain harus dikerjakan dua kali; halaman landing dan dashboard perlahan berbeda (border, spacing, warna). Tidak bisa di-cache lintas halaman.
- **Perbaikan:** ekstrak token + komponen bersama ke `style.css`, landing memuat file itu, hapus blok inline. Tidak perlu build tool.

### F-02 · Library chart 160 KB render-blocking di `<head>` — **P1**
- **Lokasi:** `dashboard.html:12`.
- **Dampak:** HTML parsing berhenti sampai 160 KB selesai diunduh & dieksekusi; di 3G/4G lambat ini menunda first paint dashboard. Library hanya dipakai setelah scan.
- **Perbaikan:** `defer` (atau muat dinamis saat scan pertama). Karena ada guard `typeof LightweightCharts === 'undefined'`, perubahan ini aman.

### F-03 · `innerHTML` tanpa escape di tabel audit + CSP `unsafe-inline` + API key di `sessionStorage` — **P1**
- **Lokasi:** `app.js:1344` (`${s.ticker}`), `:1469` (`${m.month_name}`), `:1345` (`${s.trading_date}`); `main.py:80-88` (CSP `script-src 'unsafe-inline'`); `app.js:10-33` (key di sessionStorage).
- **Bukti:** di jalur lain tim sudah disiplin memakai `esc()`; dua tempat ini tidak.
- **Dampak:** rantai XSS→pencurian API key: ticker/tanggal berasal dari DB (ditulis dari nama ticker Yahoo + input eksternal). Satu data berbahaya = eksekusi skrip di origin yang sama, `sessionStorage` terbaca, penyerang bisa memicu scan/telegram atas nama korban. `unsafe-inline` memperbesar dampak (tidak perlu file JS eksternal).
- **Perbaikan:** bungkus semua interpolasi dengan `esc()`; target CSP tanpa `unsafe-inline` (pindahkan inline script ke file, pakai nonce/hash).

### F-04 · "Tidak ada sinyal" diperlakukan sebagai error — **P2**
- **Lokasi:** `app.js:495-499` (`if (!data.data?.length) throw new Error('No buy signals found...')`).
- **Dampak:** pada mode `BLOCK` (risk-off), backend sengaja mengembalikan `data: []` (`predict.py:96`); UI menampilkan kotak error merah + "Coba lagi", bukan pesan "pasar risk-off, tahan cash". Pengguna mengira sistem rusak.
- **Perbaikan:** bedakan `status success + data kosong` (empty state informatif + `macro_mode`) dari HTTP/parse error.

### F-05 · Tidak ada auto-refresh / indikator umur data yang jujur — **P2**
- **Lokasi:** `app.js` (tidak ada polling/`visibilitychange`); badge hanya 3 status (DATA CONTOH / CACHE hh:mm / SEGERA).
- **Dampak:** dashboard bisa terbuka berjam-jam menampilkan data lama tanpa peringatan; setelah scan selesai di server, klien tidak tahu.
- **Perbaikan:** tampilkan `X-Data-Age` sebagai umur ("4 hari lalu") + tombol refresh; refresh saat tab kembali visible.

### F-06 · Dead code & helper tak terpakai — **P3**
- **Lokasi:** `app.js:887` (`renderAllMiniCharts`, 0 pemanggil setelah lazy-load).
- **Dampak:** 30 baris + kompleksitas konkurensi yang tidak diuji.
- **Perbaikan:** hapus.

### F-07 · Dua bahasa dalam satu produk — **P3**
- **Lokasi:** `index.html` (judul/isi Inggris) vs `dashboard.html` + `app.js` (Indonesia).
- **Dampak:** pengguna berpindah bahasa di tengah alur; juga menyulitkan konsistensi istilah ("Skor keyakinan" vs "confidence score").
- **Perbaikan:** pilih satu bahasa utama (Indonesia untuk audiens BEI) atau sediakan toggle.

---

## 6. Keamanan & Operasional

| ID | Sev | Temuan | Lokasi | Perbaikan |
|---|---|---|---|---|
| S-01 | P1 | Rate limit per-IP tidak sadar proxy (lihat B-03) | `main.py:42` | percayai XFF dari proxy tepercaya |
| S-02 | P2 | Perintah worker di compose tidak berfungsi (tidak ada `__main__`) — E8 | `docker-compose.yml:52-58`, `daily_scheduler.py` | tambah `if __name__ == "__main__": start_background_scheduler()` |
| S-03 | P2 | Tidak ada backup/retensi DB audit; DB tumbuh di git | `data/signals_audit.db`, workflow | backup terjadwal + VACUUM + rotasi |
| S-04 | P2 | `?force=true` dan `/api/sync` menjalankan pekerjaan berat di request thread | `predict.py:36-40`, `:367-378` | job queue + 202 + status |
| S-05 | P3 | Dua worker dengan state memori terpisah | `Dockerfile:29` | 1 worker atau state bersama |
| S-06 | P3 | `.env` aman (ignored), tetapi `API_AUTH_TOKEN` kosong = dev terbuka | `.gitignore:46`, `security.py:78-92` | pastikan `APP_ENV=production` di deploy; sudah fail-closed saat startup |

Catatan positif yang layak dipertahankan: validasi ticker regex, `hmac.compare_digest`, sanitasi input Pydantic, `yf_client` dengan timeout keras + circuit breaker, WAL + busy timeout, `read_only` container + `cap_drop: ALL`, security headers, dan pemisahan scheduler dari web process (opt-in). Fondasinya bagus — masalahnya ada di **kepemilikan state** dan **kontrak cache**, bukan di kualitas kode per baris.

---

## 7. Rencana perbaikan berurutan (usulan)

**Minggu 1 — hentikan ketidakpastian data (P0):**
1. C-03: backup DB, selesaikan konflik index, `git rm --cached` DB + ignore `*.db-wal/-shm`; hentikan commit artefak di CI.
2. C-02: penulisan atomik (tmp + `os.replace`) + metadata `schema_version`, `generated_at`, `scan_id`.
3. C-01: hapus expiry 24 jam; tambah `latest.prev.json`; endpoint baca **read-only**; sampel hanya bila benar-benar belum ada snapshot.
4. B-01: `track-record` hanya baca; audit dipindah ke job ber-auth.
5. D-01: P&L LOSS dihitung dari `stop_loss`/harga exit nyata, hapus konstanta −1,5.

**Minggu 2 — cache & HTTP yang benar (P1):**
6. C-04/C-05: `Cache-Control` per kelas path + nama aset ber-hash; hapus `?v=`.
7. C-06/C-07: putuskan 1 worker vs state bersama; invalidasi cache chart setelah scan.
8. B-02/B-04: semaphore scan dipakai; semua koneksi SQLite ditutup.
9. B-03: rate limit sadar proxy.
10. F-01/F-02/F-03: satukan CSS, `defer` chart lib, escape semua `innerHTML`.

**Minggu 3 — kualitas & kejujuran metrik (P2):**
11. D-02/F-05: angka landing dari API atau dihapus; badge umur data jujur.
12. D-03: satu sumber kebenaran harga.
13. D-04/D-05: pisahkan skor model vs rule; hapus double-escape.
14. B-06/B-09/B-10: paginasi, gzip, `/healthz`.

---

## 8. Lampiran — peta endpoint & perilaku cache

| Endpoint | Auth | Cache saat ini | Efek samping | Risiko |
|---|---|---|---|---|
| `GET /api/recommendations` | tidak (kecuali `force`) | JSON file, expiry 24 j | **menulis** JSON + DB saat cache basi | P0 (C-01) |
| `GET /api/recommendations?force=true` | ya | bypass | scan penuh sinkron | P1 (B-02) |
| `GET /api/chart/{ticker}` | tidak | memori per-worker 60 s/300 s | panggilan yfinance | P1 (C-06/07) |
| `POST /api/narasi` | ya | tidak ada | panggilan LLM 120 s | P2 (semaphore 2) |
| `POST /api/narasi/multi-agent` | ya | tidak ada | LLM/agen | P2 |
| `POST /api/news` | tidak | tidak ada | yfinance news | P3 |
| `GET /api/audit/track-record` | tidak | tidak ada | **audit jaringan + seed** | P0 (B-01) |
| `GET /api/audit/recap` | tidak | tidak ada | full table scan | P2 (B-06) |
| `GET /api/audit/run` | ya | tidak ada | tulis status | ok |
| `GET /api/audit/seed-simulation` | ya | tidak ada | unduh 6 bln, tulis DB | P2 |
| `GET /api/sync` | ya | bypass | scan penuh sinkron | P2 (S-04) |
| `GET /api/telegram/status` | tidak | tidak ada | baca env | ok |
| `GET /dashboard`, `/` | – | **tanpa header** | – | P1 (C-04) |

---

## 9. Definisi "selesai" untuk audit ini

Audit dianggap tuntas bila, pada satu hari bursa penuh:
1. `curl -I /api/recommendations` menunjukkan `Cache-Control: no-store` dan `X-Data-Age` < 60 menit setelah scan 16:05.
2. Dua request `/api/recommendations` berturut-turut tidak memicu scan (log bersih) dan mengembalikan `scan_id` yang sama.
3. Kill scheduler saat scan → pengguna tetap melihat snapshot terakhir, **bukan** DATA CONTOH.
4. `git status` bersih setelah scan (tidak ada `.db`, `-wal`, `-shm`).
5. `SELECT SUM(...)` rekap cocok dengan perhitungan manual dari `entry_price`/`stop_loss`/`exit_price` per sinyal.
