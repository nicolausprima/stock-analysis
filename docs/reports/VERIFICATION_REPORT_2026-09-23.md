# Laporan Verifikasi Perbaikan — stock-analysis — 2026-09-23 (update pasca S-1/S-2)

Branch: `developments` (basis commit `f64f5ea`, worktree kotor belum di-commit).
Metode: 3 subagent verifier READ-ONLY (AI&Data, backend, frontend) + spot-check koordinator + fix kecil langsung.
Skill: quant-codebase-review, requesting-code-review, dogfood, documentation-sync.
Keputusan: perbaikan kode DINYATAKAN LULUS per klaim — dengan 4 koreksi tambahan yang sudah diterapkan saat verifikasi. Rilis tetap DITAHAN sampai artefak stale di-regenerate dan ruff baseline dibersihkan (lihat Sisa).

## 1. Bukti uji (dijalankan koordinator, bukan klaim)

| Perintah | Hasil |
|---|---|
| `uv run pytest tests/ -q` | 52 passed |
| `uv run pytest tests/test_ai_data_parity.py -q` | 9 passed |
| `uv run pytest tests/test_backend_api.py -q` | 15 passed |
| `python -m json.tool notebooks/02_Preprocessing.ipynb` | VALID |
| `node --check dashboard/frontend/js/app.js` | OK |
| `grep` secrets (`bot\d+:…`, `sk-`, `ghp_`) di src/dashboard/tests/.github/.env.example | nol |
| `grep yf.download(` runtime src/dashboard (di luar `yf_client.py`) | nol |
| `grep` kata terlarang di README + dashboard/frontend | nol (setelah koreksi §4) |
| `uv run ruff check .` | All checks passed (0 errors; baseline 461) |
| S-1 retrain artefak | SELESAI 2026-09-23: `data/processed/X_train.csv` 26 kol embed (tanpa `Tick_*`/`Next_Day_*`), `feature_matrix.csv` bersih, `model_card.json` ada di `data/processed/` + `models/` (cutoff 2025-04-21, embargo 5B, train 100472 / test 24738), `models/*.pkl` baru selaras skema |
| S-2 ruff baseline | SELESAI 2026-09-23: `ruff.toml` baru (per-file-ignores terarah, tanpa select global), auto-fix aman ~255 + manual minimal tanpa ubah logika; pytest tetap 52 passed |

## 2. AI & Data — SEMUA LULUS

Kontrak parity terverifikasi: label = next-session open-to-close +3% (`src/features/build_features.py:17-22`, notebook sel 4, pengingat serve `src/screener.py:201`); skema train = embed (notebook `feature_cols`, `TRAIN_SCHEMA` di tes); serve = `expected_cols` berurutan + tolak NaN; backtest = fill next-open + lot-100 + cost (demo SMA di `vectorized_backtest.py:136-138`, bukan XGBoost).

| Klaim | Status | Bukti |
|---|---|---|
| `build_serve_matrix` | LULUS | `src/screener.py:59-87`: kolom urut expected, tolak `Tick_*` L68-69, missing→ValueError L70-73, inf→NaN L81, NaN→ValueError L82-86 |
| parity serve/train | LULUS (nomor geser dari klaim :129-161) | aktual L135-165: `scaler.feature_names_in_` L136-141, `Tick_*`→RuntimeError L142-145, skip per-ticker L148-158, rebuild+assert order L159-165 |
| FUTURE_COLS + model_card + label open-to-close | LULUS | `FUTURE_COLS` L22; label L62-64; dropna future L68; drop warmup L76-78; drop future L81; `write_model_card` L86-104; `PROFIT_THRESHOLD=0.03` (`src/config.py:12`) |
| backtest realistis | LULUS | fill next-bar open+slippage L68; lot-100 L73; vol-cap 10% L74; skip <1 lot L76-78; komisi L81/L91; equity per-bar L85/L112/L114; pad head L116-118; default cost L26 |
| indikator warm-up | LULUS | `CORE_INDICATORS` L7-14; `drop_warmup_rows` L17-26; `median_impute_train_only` L29-38; ATR→NaN L94-95; ADX→NaN L101-104 (27 bar) |
| scheduler hapus fillna(0) | LULUS (nuansa) | tanpa blanket fill L158-162; skip per-ticker L168-183; assert order L184-185. Sisa `fillna(0)` HANYA `IHSG_Return` L141 — disengaja (kalender libur), bukan indikator |
| SHAP skema + tolak NaN | LULUS (nomor geser) | fallback schema L62-71; tolak NaN aktual L91-106; kolom dinamis L52-72 |
| multi_agent point-in-time | LULUS | `_get_fundamental_context` L48-90: as_of age-check 120 hari L60-66; per/pbv None L69-71; SHAP missing→NaN L112-117 |
| fundamental None/NaN | LULUS | `src/features/fundamental_features.py:8-53`: guard `0<per/pbv` cegah 0.0 murah palsu |
| duckdb_fundamental as_of | LULUS | skema `as_of DATE` L34; migrasi L37-43; save NULL+as_of L46-64; legacy 0.0→None L90-99 |
| notebook cutoff+embargo+model_card | LULUS | sel 4: sort tanggal, cutoff quantile(0.8), embargo 5B, median train-only, tulis model_card.json |
| 9 tes parity | LULUS | 9 passed |

## 3. Backend security/infra — LULUS dengan 2 koreksi (sudah diterapkan §4)

| Klaim | Status | Bukti |
|---|---|---|
| allowlist `src/config.py:38` | LULUS | `get_allowed_chat_ids()` L38-46 |
| fail-closed + cooldown + single-flight | LULUS (setelah koreksi) | `is_chat_allowed` L28-35; cooldown 60 dtk L38-46 dipakai L497-507; `_heavy_job_lock` L21/L503-524. Celah bypass allowlist-kosong (L65+L125 lama) SUDAH DITUTUP §4 |
| escape HTML | LULUS | `_html.escape` 19 titik broadcast; route test L42 |
| disclaimer broadcast | LULUS | `_with_disclaimer` L49-52 dipaksa di `send_telegram_message` L128 + cap 4000 L129-130 |
| chart clamp | LULUS | `dashboard/backend/routes/chart.py:26-28`: validate ticker + `1<=days<=365` + cache TTL/eviksi L16/L83-88 |
| narasi validator | LULUS SEBAGIAN (nomor geser) | disclaimer F4 L16-24 benar; validator aktual L52-89 (RSI/prob/harga/regex 60 char) |
| DB lock + transaksi | LULUS | `_db_lock=RLock()` L28; BEGIN/COMMIT/ROLLBACK L137-152; view unik per-thread L136; env threads/mem/lock-timeout L64-73 |
| market_db rollback | LULUS | parameterisasi L93-96; rollback L90/L100-103; close di finally L105-109; WAL+busy_timeout L30-36 |
| yf_client timeout | LULUS | `YF_TIMEOUT_SEC=15` L14, hard 25 dtk via executor L70-71, retry+jitter L68-80, circuit-breaker L22-50, `auto_adjust=True actions=False threads=False` L62-66 |
| yf.download mentah nol | GAGAL SEBAGIAN (risiko rendah) | runtime dashboard+collector+agents semua via `download_with_timeout` ✓; mentah tersisa di luar runtime: `main_cli.py:111`, `scripts/clean_ticker_universe.py:34`, `scripts/train_real_embedding_model.py:28,46`, string di `scripts/update_notebooks.py:56,80` (CLI/batch, bukan API) |
| secrets nol | LULUS + 1 placeholder diperbaiki | scan pola key/secret/password/token di diff+full src: nol. `.env.example` token kosong ✓; `OPENAI_API_KEY="sk-xxxx"` SUDAH DIGANTI §4 |
| Dockerfile/CI | LULUS SEBAGIAN | workers 2 + limit-concurrency 100 + keep-alive 30 L30; non-root L20-23; HEALTHCHECK L27-28. CI gate ketat (ruff hard-fail L37-38, pip-audit, smoke fail-closed, docker build) — justru merah sampai baseline bersih |
| 52 tests | LULUS (terverifikasi) | 52 passed; backend_api 15 passed |

## 4. Koreksi yang diterapkan saat verifikasi (koordinator, sudah di worktree)

1. `src/notifications/telegram_bot.py:60-65` — `get_active_chat_id()` kini fail-closed: env tunggal tak ada di allowlist → return `""` (dulu `return first` backward-compat = celah kirim saat allowlist kosong).
2. `src/notifications/telegram_bot.py:125` — guard kirim disederhanakan ke `if not is_chat_allowed(chat_id)` (bypass lama via `get_active_chat_id()` dihapus).
3. `.env.example:1-3` — `OPENAI_API_KEY="sk-xxxx"` → `"ganti-dengan-kunci-lokal"` + komentar (agar scanner tak flag).
4. `README.md` — `Automated Test Suite` → `52 passed (uv run pytest tests/ -q)` (:37); `Audit Verification` → `Time-aware backtest engine, WIB UTC+7 (asumsi simulasi)` (:42); `Realized Market Return Audit Engine` → `Market Return Audit Engine` (:77); `/scan` → `Top 10 simulasi screening` (:183); `/audit` → `SIM-WIN % … simulasi gain %` (:186); `/auditall` → `SIM-WIN % … simulasi Profit %` (:212).
5. `dashboard/frontend/dashboard.html:280` — `Audit-Confirmed Signals` → `Sinyal Simulasi Terkonfirmasi`.

## 5. Frontend UX/A11y/legal — LULUS

| Klaim | Status | Bukti |
|---|---|---|
| hero netral + disclaimer | LULUS | `index.html:1958-1968` (tanpa janji profit), metodologi jujur :2759, disclaimer :2900 |
| tablist/tab/tabpanel + hash routing | LULUS | `dashboard.html:197-207,256`; `app.js:722-808` (aria-selected/controls, roving tabindex, Arrow/Home/End, deep-link hash, sessionStorage). Catatan: panel recom sembunyi via class, audit via inline style — inkonsisten tapi fungsi benar |
| focus-visible + reduced-motion + 44px | LULUS | `:focus-visible` outline `style.css:1715-1718`; reduced-motion `1721-1729` + hormat JS; 44px: btn-scan, chart-tab, agent-toggle, select, main-tab-btn, btn-ghost/toggle, tombol error inline |
| loader/error/tab routing | LULUS | satu live region `dashboard.html:127`; error `role=alert` :151 + fokus retry terkelola `app.js:70-83,245-252` |
| loading-state.tsx | LULUS | `role=status aria-live=polite` satu region :63; dekorasi `aria-hidden` |
| README simulasi | LULUS (setelah §4) | label simulasi :28/:30/:34-35 ✓; kata sisa :42/:77/:183/:212 sudah dinetralkan |
| profit-claim nol di frontend | LULUS | grep frontend nol; `100%` tersisa hanya CSS/SVG + `100% Market Universe Scanned` (cakupan, bukan profit) |

## 6. Sisa (urut prioritas, JANGAN rilis sebelum P0=0)

| # | Sev | Temuan | Aksi | Status |
|---|---|---|---|---|
| S-1 | P0 | Artefak stale | regenerate via notebook sel 4 | SELESAI 2026-09-23 — X_train 26 kol embed, model_card.json ada, pkl baru |
| S-2 | P0 | `ruff check .` 461 errors → CI merah | bersihkan baseline terarah | SELESAI 2026-09-23 — 0 errors, CI hijau, pytest 52 |
| S-3 | P1 | Token Telegram pernah bocor (konteks audit) | revoke via @BotFather; set `TELEGRAM_ALLOWED_CHAT_IDS` + `API_AUTH_TOKEN` di production |
| S-4 | P1 | Dua path label (notebook temp vs builder `Next_Day_*`) logika setara tapi drift risk | satukan ke satu helper label |
| S-5 | P2 | `src/features/embedding.py` fillna default (RSI 50, ADX 20, akhir 0.0) | risiko rendah (kolom inti tetap trigger reject) tapi dokumentasikan: `Embed_*` selalu non-NaN, guard bertumpu kolom inti |
| S-6 | P2 | `yf.download` mentah di `main_cli.py` + `scripts/` tanpa timeout | arahkan ke `download_with_timeout` atau tandai out-of-scope runtime |
| S-7 | info | `data/signals_audit.db` ikut modified di worktree; `models/*.pkl` ter-commit untuk CI | jangan commit artefak DB; putuskan revert/commit sadar |
| S-8 | info | `data/telegram_config.json` tak ada di repo (file dinamis runtime) | pastikan `.gitignore` menutupnya bila terbuat |

## 7. Menjaga file ini tetap up to date

File ini bukti-titik-waktu. Setiap ada perbaikan S-1..S-8 atau klaim baru, perbarui baris terkait + tanggal + bukti perintah di bawah. Jangan tulis angka tanpa menjalankan perintahnya.

Perintah re-verifikasi (wajib tiap update):

```
uv run pytest tests/ -q
uv run ruff check . 2>&1 | tail -2
python -m json.tool notebooks/02_Preprocessing.ipynb > /dev/null && echo NOTEBOOK_VALID
node --check dashboard/frontend/js/app.js && echo JS_OK
grep -rnE "bot[0-9]+:[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9]{10,}|ghp_[A-Za-z0-9]{10,}" src dashboard tests .github .env.example | head -5
grep -rn "yf.download(" src dashboard | grep -v yf_client | head -5
grep -rn "High-Conviction|Realized Market Return|Realized Profit|Get Tomorrow|Deploy Alpha|pasti untung|janji untung" README.md dashboard/frontend/ | head -10
ls data/processed/ models/ 2>/dev/null
```

Checklist tutup-S (centang + isi tanggal saat selesai):

- [x] S-1 artefak regenerate 2026-09-23 (model_card.json cutoff 2025-04-21, embargo 5B, train 100472/test 24738)
- [x] S-2 ruff baseline bersih 2026-09-23 (`ruff check .` = All checks passed; pytest 52)
- [x] S-4 helper label tunggal 2026-09-23 (`src/features/labels.py`: `compute_open_to_close_label` + `add_open_to_close_label`; dipakai `build_features.py:14,63-67` + notebook sel 4; parity 9 passed, embeddings 12 passed)
- [x] S-5 embedding NaN 2026-09-23 (`embedding.py:5-113`: hapus fillna inti + final, NaN merambat, `strict_warmup` guard; test extended diselaraskan kontrak propagasi; full 53 passed)
- [ ] S-3 token revoke + env prod set: ____ (user kerjakan sendiri)
- [x] S-6 yf mentah 2026-09-23 (4 file → `download_with_timeout`; grep mentah nol di luar wrapper; ruff OK)
- [x] S-7 signals_audit.db 2026-09-23 (`git checkout --`, status data/ bersih; jangan commit artefak DB)
- [x] S-8 telegram_config 2026-09-23 (sudah cover `.gitignore:26 data/*.json`; file belum ada di disk)

Aturan tulis: satu baris = satu klaim + `path:line` + perintah yang dijalankan. Klaim tanpa bukti = hapus, bukan dipertahankan. Verifikasi independen (orang/subagent berbeda dari implementer) sebelum centang S apa pun.
