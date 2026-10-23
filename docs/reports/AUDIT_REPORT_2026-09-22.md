# Laporan Audit Akhir stock-analysis — 2026-09-22 — branch developments — commit f64f5ea

Keputusan rilis: BLOKIR. 6 P0 terbuka. Rilis hanya setelah P0 = 0 terverifikasi.

## 1. Ringkasan eksekutif

| Tim | P0 | P1 | P2 | P3 |
|---|---|---|---|---|
| AI & Data | 3 | 6 | 6 | 0 |
| Desain & UX | 0 | 0 | 0 | 0 (1 Critical, 5 High, 5 Medium, 2 Low skala WCAG/UX) |
| Keamanan & Teknis | 1 | 5 | 4 | 1 |
| Hukum & Etika | 3 | 0 | 0 | 0 (3 HIGH, 3 MEDIUM, 1 LOW skala hukum) |
| Total P0 lintas tim (dedup) | 6 | | | |

3 risiko terbesar:
1. Pipeline prediksi tidak parity: skema serve vs train beda, label vs horizon tidak selaras, backtest tidak realistis. Semua sinyal beli dari sistem ini tidak valid.
2. Nasihat beli personal + janji untung tampil publik tanpa lisensi Penasihat Investasi. Risiko pidana UU P2SK.
3. Bot Telegram tanpa allowlist + token plaintext di disk. Siapa pun bisa picu scan 700+ ticker.

## 2. Metodologi & skills per tim

| Tim | Ruang lingkup | Skills dipakai | Batasan |
|---|---|---|---|
| AI & Data (AI/ML QA, Data Governance, Quant Finance) | src/features, src/backtest, src/agents, src/collector, src/database, notebooks/02_Preprocessing.ipynb, data/processed | quant-codebase-review + references ml-contracts.md, multi-agent-review.md | Read-only; pickle feature lists tidak terverifikasi langsung (sandbox tanpa joblib/pandas); pytest tidak dijalankan |
| Desain & UX (UX, UI/A11y, CRO) | dashboard/frontend, components/ui/loading-state.tsx | .claude/skills/ui-ux-pro-max, dogfood | Tanpa render browser penuh; kontras tidak diukur instrumen |
| Keamanan & Teknis (Cybersecurity, Cloud Infra) | dashboard/backend, src/database, src/notifications, Dockerfile, compose, CI, scheduler | requesting-code-review (static scan), systematic-debugging | Read-only; race DB dinilai dari pola kode, crash konkuren belum direproduksi |
| Hukum & Etika (Legal, AI Ethics) | Teks hadapan pengguna + riset regulasi OJK/SEC via web | grounded-citations, document-to-action-items | Ledger sources.py tidak ada di host; nomor sitasi manual dari URL terverifikasi |
| Koordinator | Jadwal, severity, template, verifikasi spot-check | plan, documentation-sync | Spot-check 4 file; sisanya status agent-confirmed |

## 3. Temuan per tim

### Tim-1 AI & Data

#### AI-01 Skema serve vs train mismatch (jaminan gagal)
- Severity: P0
- Location: src/screener.py:102-124
- Evidence: serve bangun one-hot `Tick_{t}` lalu `scaler.transform(X)`; scaler dilatih di skema `Embed_*`. `X.fillna(0)` buta menutup error.
- Impact: seluruh output screener tidak valid.
- Fix: hapus screener.py atau selaraskan ke `expected_cols`; assert urutan kolom saat load model.
- Confidence: confirmed. Status verifikasi: Reproduced (koordinator baca kode).

#### AI-02 Label drift + kolom masa depan tersimpan
- Severity: P0
- Location: src/features/build_features.py:46-53; data/processed/feature_matrix.csv; 03_Modelling.ipynb:71-76
- Evidence: label `(Next_Close-Next_Open)/Next_Open>=0.03`; `Next_Day_*` ikut tersimpan; pickle tanpa target/horizon/cutoff.
- Impact: evaluasi bocor; artefak tidak teraudit.
- Fix: tulis `model_card.json` (definisi target, horizon, cutoff); drop kolom future dari artefak.
- Confidence: confirmed. Status: Reproduced parsial (build_features.py diverifikasi koordinator).

#### AI-03 Horizon label vs serving tidak selaras
- Severity: P0
- Location: src/features/build_features.py:46-53; dashboard/backend/routes/audit.py:353-358; src/screener.py:139,155
- Evidence: label intraday open-to-close +3%; serve swing TP ATR 2.5-5% / audit 5 hari / "BELI BESOK PAGI".
- Impact: model dilatih untuk soal berbeda dari yang dijual.
- Fix: selaraskan label ke horizon serving, atau batasi klaim ke intraday.
- Confidence: confirmed. Status: agent-confirmed.

#### AI-04 Split time leakage
- Severity: P1
- Location: notebooks/02_Preprocessing.ipynb cell3
- Evidence: `concat` ticker-major lalu `split_idx=int(len*0.8)` tanpa sort tanggal.
- Impact: data masa depan bocor ke train; metrik overfit.
- Fix: sort by date, cutoff tanggal + embargo.
- Confidence: confirmed. Status: agent-confirmed.

#### AI-05 Artefak basi lintas skema
- Severity: P1
- Location: data/processed/X_train.csv (skema Tick_) vs serve Embed_
- Evidence: train 50 ticker vs serve 732; satu pipeline tidak ada.
- Impact: retrain dari nol wajib sebelum klaim apa pun.
- Fix: single pipeline retrain; tandai artefak lama stale.
- Confidence: confirmed. Status: agent-confirmed.

#### AI-06 Fill-zero buta indikator warm-up
- Severity: P1
- Location: 02 sel4; src/scheduler/daily_scheduler.py:156,170; src/explainability/shap_explainer.py:91-97; src/agents/multi_agent_v2.py:89-91; src/screener.py:121
- Evidence: RSI/MACD/BB NaN warm-up jadi 0; SHAP jelaskan nilai palsu.
- Impact: sinyal palsu + eksplanasi menyesatkan.
- Fix: drop warm-up; median fit-train only; bedakan missing vs nol.
- Confidence: confirmed. Status: agent-confirmed.

#### AI-07 Fundamental nowcast leak
- Severity: P1
- Location: src/collector/fundamental_collector.py
- Evidence: `ticker.info` saat ini overwrite `CURRENT_TIMESTAMP` tanpa as-of; missing = 0.0.
- Impact: fitur pakai info belum tersedia saat decision-time.
- Fix: snapshot berversi + NULL untuk missing.
- Confidence: confirmed. Status: agent-confirmed.

#### AI-08 Backtest tidak realistis
- Severity: P1 (P0 untuk klaim return)
- Location: src/backtest/vectorized_backtest.py:67-82
- Evidence: entry `closes[i]` bar sama; tanpa lot-100/volume cap/ARA-ARB; `equity_curve` tak terisi; strategi SMA-cross bukan strategi model.
- Impact: angka +820.5%/85.9% tidak dapat dipercaya.
- Fix: fill next-bar open, lot + volume cap, equity per-bar, backtest strategi model aktual net-of-cost.
- Confidence: confirmed. Status: Reproduced (koordinator baca kode).

#### AI-09 Label gross-of-cost; boosters tak terkalibrasi; Kelly paksa taruhan
- Severity: P1 / P2
- Location: build_features.py:53; multi_agent_system.py:204; dashboard/backend/routes/features.py:100-105
- Evidence: +3% belum dikurangi fee 0.15-0.25% + slip; boost sektor +2%, sentimen +1.5-4.5%/VETO -25%; threshold ganda 65/75 vs 55/80; Kelly clamp p [0.5,0.9] floor [5,25]%.
- Impact: hit-rate semu; sizing agresif.
- Fix: label net-of-cost; kalibrasi tunggal; izinkan 0%.
- Confidence: confirmed kode; hit-rate needs-verification. Status: agent-confirmed.

#### AI-10 Sumber data: TOS, survivorship, corporate action
- Severity: P1 / P2
- Location: src/collector/batch_collector.py:72; data/tickers.txt (732, current-only); akshare required tapi zero-import
- Evidence: yfinance di luar TOS + tanpa timeout; survivorship bias; nol `auto_adjust/actions`; feedparser tanpa timeout/UA.
- Impact: universe bias; legalitas rapuh; download gantung.
- Fix: timeout/retry/backoff + cache; point-in-time universe; harga adjusted eksplisit; hapus akshare atau pakai.
- Confidence: confirmed kode; legalitas needs-verification. Status: agent-confirmed.

### Tim-2 Keamanan & Teknis

#### SEC-01 Token Telegram plaintext di disk
- Severity: P0
- Location: .env (untracked, on disk)
- Evidence: `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` plaintext.
- Impact: takeover bot, spam/phish dari akun bot.
- Fix: revoke via @BotFather sekarang; secret manager; jangan tulis token asli di .env kerja. Mitigasi ada: .env untracked + dockerignore exclude.
- Confidence: confirmed. Status: agent-confirmed (koordinator tidak baca .env).

#### SEC-02 Listener Telegram tanpa allowlist picu job berat
- Severity: P1
- Location: src/notifications/telegram_bot.py:395-446
- Evidence: `/today /midday /bsjp /audittoday /auditall` dari chat_id mana saja; `/bsjp` scan 700+ ticker; tanpa rate-limit, tanpa cek chat_id.
- Impact: DoS + info disclosure oleh siapa pun.
- Fix: allowlist chat_id, cooldown 60s per-chat, 1 job berat max.
- Confidence: confirmed. Status: Reproduced (koordinator baca kode).

#### SEC-03 Param `days` chart tanpa batas
- Severity: P1
- Location: dashboard/backend/routes/chart.py:19,53
- Evidence: `days` langsung ke `f"{days}d"` untuk yf.download; cache-key abuse.
- Impact: request aneh/berat ke Yahoo.
- Fix: clamp 1-365, 400 bila di luar.
- Confidence: confirmed. Status: Reproduced (koordinator baca kode).

#### SEC-04 HTML injection pesan bot; prompt injection narasi
- Severity: P2
- Location: dashboard/backend/routes/telegram.py:32-36; dashboard/backend/routes/narasi.py:27-37
- Evidence: `payload.message` mentah ke parse_mode HTML; field numerik/string bebas ke prompt LLM.
- Impact: spoofing siaran; biaya LLM tak wajar.
- Fix: `html.escape` + batas panjang; clamp numerik + regex string.
- Confidence: confirmed. Status: agent-confirmed.

#### INF-01 yfinance tanpa timeout di ~20 callsite
- Severity: P1
- Location: chart.py:47-54; audit.py:296,643,657; daily_scheduler.py:84; batch_collector.py:35; ihsg_macro_agent 5x
- Evidence: semua `yf.download` tanpa timeout; chart sync-def blokir event loop.
- Impact: pasar ramai = thread gantung, /api/sync hang menit.
- Fix: helper download_with_timeout + retry/backoff/jitter + circuit-breaker.
- Confidence: confirmed. Status: agent-confirmed.

#### INF-02 Satu koneksi DuckDB global lintas thread
- Severity: P1
- Location: src/database/duckdb_market.py:44-81; duckdb_fundamental.py:42-69
- Evidence: lock hanya saat buat koneksi; `register("temp_prices")` tabrakan scheduler+API.
- Impact: race, write conflict, OOM (memory_limit 2GB hardcoded).
- Fix: koneksi-per-thread atau serialisasi penuh; limit via env.
- Confidence: likely. Status: needs-verification (repro konkuren).

#### INF-03 Serve 1 worker, executor kecil, tanpa resource limit
- Severity: P1
- Location: Dockerfile:30; docker-compose.yml:22; predict.py:19
- Evidence: tanpa --workers; max_workers=2; SEMAPHORE antre; tanpa cpus/mem_limit; /api/sync full scan dalam request.
- Impact: 2 request berat = antre/timeout.
- Fix: --workers 2-4, /sync async 202+job-id, limits di compose.
- Confidence: confirmed. Status: agent-confirmed.

#### INF-04 CI gate ompong; daily_scan auto-commit DB
- Severity: P2
- Location: .github/workflows/ci.yml; daily_scan.yml
- Evidence: `ruff ... || true`, `pip-audit ... || true`; push DB biner ke branch sama tanpa concurrency group.
- Impact: vuln/lint tetap hijau; konflik push; repo gendut.
- Fix: hapus `|| true`; tambah timeout-minutes + trivy; concurrency group; artefak eksternal.
- Confidence: confirmed. Status: agent-confirmed.

Verified clean: semua `.execute()` berparameter `?`; nol os.system/shell=True/eval/pickle.loads; tanpa CORSMiddleware; frontend buang `?api_key=` pakai header X-API-Key. Sensitif (/sync, /narasi, /telegram, /audit/run) sudah require_api_key.

### Tim-3 Desain & UX

#### UX-01 Scrollbar disembunyikan global [Critical|A11y]
- Location: dashboard/frontend/css/style.css:83-93; index.html:80-103
- Fix: hapus aturan; pertahankan indikator visible.

#### UX-02 Target sentuh <44px; reduced-motion diabaikan; pola tab rusak + heading loncat
- Location: style.css:449-464,1262-1279,1716-1731; index.html:2461-2645
- Fix: min-height 44px semua kontrol; `@media (prefers-reduced-motion: reduce)`; lengkapi tabpanel + arrow-key nav; h4 jadi h3.

#### UX-03 Tab saling meniadakan tanpa deep-link; kontrol chart hilang <=400px
- Location: dashboard.html:181-188; app.js:665-690; style.css:1667-1669
- Fix: hash routing + preserve sessionStorage; segmented control kompak.

#### UX-04 Grafik tanpa legenda/label/tooltip keyboard; bahasa hero tanpa konteks risiko
- Location: app.js:407-436,476-505,809-834; dashboard.html:76-82; index.html:2715
- Fix: ringkasan tekstual + legend statis; label hero jadi `Target Model +3.0% / SL -1.5%` + microcopy risiko.

#### UX-05 loading-state.tsx berisik bagi screen reader; token CSS ganda
- Location: components/ui/loading-state.tsx:41-93; dashboard.html:13 vs index.html:24-50
- Fix: role=status + aria-hidden timer; satu stylesheet token bersama.

#### CRO Hasil: tidak ada tombol transaksi buy/sell/subscribe.
`buy/sell` hanya badge sinyal. Tanpa confirmshaming/fake urgency/pre-checked. Sisa: badge BUY tanpa microcopy `sinyal bukan order`; tombol simulasi tanpa watermark `SIMULASI`; fallback narasi selalu positif. Confidence: tinggi.

Positif: :focus-visible 2px; tabel scope=col; aria-live error; esc()+textContent anti-XSS.

### Tim-4 Hukum & Etika

#### F1 Nasihat beli personal tanpa lisensi [HIGH]
- Location: telegram_bot.py:118,206-227,308-315; narasi.py:76; multi_agent_system.py:101; dashboard.html:196-202
- Evidence: "REKOMENDASI SAHAM SIAP BELI HARI INI", "Beli Sekarang (15:30-15:50)", "Saran Alokasi Modal: {kelly}% Portofolio".
- Basis: Penasihat Investasi wajib izin + fit & proper OJK [1]; tanpa izin dipidana UU P2SK [2]; robo-adviser AS = registered adviser + fiduciary duties [3].
- Fix: label beli jadi riset; hapus instruksi eksekusi; atau henti distribusi publik sampai berlisensi.

#### F2 Bahasa kepastian / janji untung [HIGH]
- Location: index.html:1858,2375,1845,1935,2588; dashboard.html:175; README.md:32-33
- Evidence: "high-probability breakout", "+3.0% targets with strict capital protection", "ALPHA +820.5%", "Win Rate 85.9%".
- Basis: iklan penasihat dilarang menyesatkan; gross wajib disertai net setara [4][5].
- Fix: hapus klaim hero; angka historis hanya dengan metodologi + net + periode.

#### F3 Simulasi disajikan sebagai track record [HIGH]
- Location: dashboard.html:246-269; telegram_bot.py:280-303; README.md:32-33,40
- Evidence: "Run 6-Month Performance Simulation" berdampingan "Cumulative Profit"; broadcast tanpa label hipotetis; "Realized" vs "Simulation" kontradiktif.
- Basis: SEC Marketing Rule larang hypothetical performance tanpa konteks [4][5].
- Fix: label permanen "SIMULASI BACKTEST — bukan hasil nyata"; pisahkan tab Simulasi vs Live.

#### F4 Disclaimer lemah & hilang di titik nasihat [MEDIUM]
- Location: ada README.md:4, index.html:2788, dashboard.html:351-357. Nihil di broadcast Telegram, response /narasi, kartu app.js.
- Basis: disclosure efektif + Reg BI sebelum/bersamaan rekomendasi [3][6].
- Fix (tempel): "Konten ini riset kuantitatif untuk edukasi — BUKAN nasihat/rekomendasi investasi. Saham berisiko rugi. Kinerja masa lalu tidak menjamin hasil. Keputusan & risiko milik Anda (DYOR)." Wajib di tiap broadcast, kartu sinyal, narasi LLM, footer dashboard.

#### F5 Sizing personal tanpa suitability [MEDIUM]
- Location: telegram_bot.py:144; index.html:2370-2441; predict.py:98-148
- Basis: robo-guidance wajib gali info klien; Reg BI care obligation [3][6].
- Fix: hapus "% Portofolio"; tampilkan formula generik; tambah gerbang profil risiko.

#### F6 Prompt LLM "meyakinkan" tanpa rem risiko [MEDIUM]
- Location: narasi.py:86 ("sangat padat, profesional, dan meyakinkan"); tanpa disclaimer di output.
- Fix: prompt wajib 1 kalimat risiko; append disclaimer F4; log source llm di UI.

#### F7 Tanpa pengungkapan konflik/limit model [LOW]
- Fix: baris persisten "AKSA tidak terafiliasi sekuritas mana pun; skor = output statistik, bukan jaminan."

Sources:
[1] SEOJK No. 2/SEOJK.04/2020 — https://ojk.go.id/id/regulasi/Documents/Pages/-Penilaian-Kemampuan-dan-Kepatutan-Bagi-Calon-Pihak-Utama-Manajer-Investasi-dan-Penasihat-Investasi/SEOJK%202%202020.pdf
[2] UU No. 4/2023 (UU P2SK) via Katadata — https://katadata.co.id/digital/fintech/68d677fa37566/eks-bos-investree-adrian-gunadi-diduga-rugikan-rp-2-7-t-terancam-bui-10-tahun
[3] SEC IM Guidance Update No. 2017-02, Robo-Advisers — https://www.sec.gov/investment/im-guidance-2017-02.pdf
[4] SEC Marketing Compliance FAQs — https://www.sec.gov/rules-regulations/staff-guidance/division-investment-management-frequently-asked-questions/marketing-compliance-frequently-asked-questions
[5] 17 CFR 275.206(4)-1 — https://www.law.cornell.edu/cfr/text/17/275.206(4)-1
[6] 17 CFR 240.15l-1 Reg BI — https://federal-regs.com/title/17/part/240/240.15l-1
[7] SEC Staff Bulletin Care Obligations — https://www.sec.gov/about/divisions-offices/division-trading-markets/broker-dealers/staff-bulletin-standards-conduct-broker-dealers-investment-advisers-care-obligations

## 4. Daftar P0 lintas tim (dedup)

| ID | Sumber | Judul | Lokasi | Status |
|---|---|---|---|---|
| P0-01 | AI-01 | Skema serve/train mismatch | src/screener.py:102-124 | Reproduced |
| P0-02 | AI-02/03 | Label/horizon mismatch + kolom future | build_features.py:46-53 | Reproduced parsial |
| P0-03 | SEC-01 | Token Telegram plaintext | .env | Agent-confirmed |
| P0-04 | SEC-02 | Listener tanpa allowlist | telegram_bot.py:395-446 | Reproduced |
| P0-05 | F1/F2 | Nasihat beli + janji untung tanpa lisensi | telegram_bot.py, index.html, README | Agent-confirmed |
| P0-06 | AI-08/F3 | Klaim +820.5%/85.9% dari backtest bocor | vectorized_backtest.py:67-82 | Reproduced |

## 5. Roadmap perbaikan prioritas

1. P0-03: revoke token Telegram sekarang. Pemilik: ops. Tutup: token baru di secret manager.
2. P0-04: allowlist + cooldown listener. Tutup: uji perintah dari chat asing ditolak.
3. P0-05: turunkan label beli jadi riset; hapus klaim hero; disclaimer F4 di semua titik. Tutup: grep "Beli Sekarang|high-probability|protect capital" nihil di user-facing text.
4. P0-01/P0-02: single pipeline + model_card.json + assert skema. Tutup: retrain repro, serve pakai expected_cols.
5. P0-06: backtest next-bar + net-of-cost; hapus angka lama sampai repro. Tutup: win/return baru dari pipeline teraudit.
6. P1 infra: timeout yfinance, koneksi DB per-thread, workers + limits, CI gate aktif.
7. P2/P3 backlog: UX/A11y fixes, token CSS tunggal, dead code (mlflow_client, stock_pipeline_dag, akshare).

## 6. Lampiran status verifikasi

| Klaim | Hasil | Bukti |
|---|---|---|
| Win 85.9% / +820.5% | DITOLAK sementara | Backtest same-bar fill + strategi beda; §AI-08 |
| Serve screener valid | DITOLAK | Skema mismatch; §AI-01 |
| 43/43 tests pass | Belum diverifikasi | pytest tidak dijalankan saat audit |
| Sub-5ms UI | Belum diverifikasi | Di luar cakupan ukur |
| CSP/X-API-Key/escaping | Lolos parsial | §SEC verified-clean |
| Disclaimer non-advice | GAGAL | §F4 |
