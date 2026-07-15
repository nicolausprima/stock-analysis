# Stock Analysis — Project Overview

> Dokumen ini adalah konteks besar proyek, ditulis supaya AI assistant (atau siapa pun) yang baru masuk ke repo ini langsung paham tujuan, arsitektur, dan alur kerja tanpa perlu penjelasan ulang.

## 1. Tujuan Proyek

Prediksi pergerakan harga saham (Indonesia, via IDX) dengan pendekatan **multi-factor**, bukan cuma dari harga historis. Menggabungkan:
- Data harga historis (OHLCV)
- Indikator teknikal (RSI, MACD, Bollinger, ATR, dll)
- Faktor eksternal (sentimen berita, IHSG, kurs USD/IDR)
- Fitur turunan (lag, momentum, cross-sectional antar saham, kalender/earnings)

Output-nya bukan sekadar angka prediksi, tapi **dashboard interaktif** yang menjelaskan *kenapa* model memprediksi begitu (feature importance) — dan punya siklus evaluasi mandiri lewat backtest + feedback terstruktur dari user.

**Catatan penting:** ini proyek edukasi/riset, bukan rekomendasi investasi. Disclaimer ini harus selalu tampil di README dan dashboard.

## 2. Prinsip Desain

- **Time-based backtesting**, bukan random split — untuk menghindari data leakage dari masa depan.
- **Prediksi arah (naik/turun)** lebih diutamakan daripada harga exact — lebih realistis dan lebih mudah dievaluasi.
- **Feature importance selalu ditampilkan** di dashboard, bukan cuma hasil akhir.
- **Semua service jalan lokal/gratis** (yfinance, Airflow, MLflow, FastAPI, HTML/JS) — tidak ada dependency berbayar selama tidak di-deploy ke cloud.
- **Setiap eksperimen (run) punya jejak** — parameter, metrik, dan review manual dari user tersimpan bersama di MLflow, supaya proses berpikir kelihatan, bukan cuma hasil akhir.

## 3. Arsitektur Besar

```
Sumber Data (yfinance, scraping berita, IHSG/kurs)
        ↓
   Airflow DAG (orkestrasi, jadwal harian, incremental fetch)
        ↓
   Feature Engineering (src/features/*) → feature_matrix.parquet
        ↓
   Training (src/models/train.py) → MLflow tracking (params, metrics, artifacts, tags)
        ↓
   FastAPI Backend (dashboard/backend) → serve prediksi, feature importance, riwayat run
        ↓
   HTML/CSS/JS Frontend (dashboard/frontend) → visualisasi + form feedback backtest
        ↓
   User mengisi review terstruktur (checkbox: penyebab gagal & saran perbaikan)
        ↓
   Review tersimpan sebagai MLflow tag → jadi bahan iterasi & laporan/jurnal
```

## 4. Alur "Backtest Review Loop"

Ini yang membedakan proyek ini dari sekadar model prediksi biasa — ada siklus refleksi setelah tiap backtest:

1. Model dijalankan → hasil backtest tampil di dashboard (akurasi, periode yang meleset, feature importance).
2. User diberi checklist (bukan freeform): kemungkinan penyebab kegagalan + saran perbaikan untuk run berikutnya.
3. Jawaban disimpan sebagai tag di MLflow, terikat ke `run_id` yang sama.
4. Halaman "Riwayat Eksperimen" di dashboard mengagregasi semua review ini — jadi terlihat pola, misalnya "3 dari 5 run terakhir gagal karena sentimen belum ter-capture".
5. Insight ini jadi bahan langsung untuk bagian evaluasi/diskusi di laporan atau jurnal.

## 5. Tech Stack

| Layer | Tools |
|---|---|
| Data source | `yfinance`, scraping berita (Kontan/CNBC), IHSG & kurs |
| Orkestrasi | Airflow (reuse dari `ml-pipeline-lab` Docker environment) |
| Experiment tracking | MLflow (SQLite backend, lokal) |
| Model | XGBoost / LSTM / Prophet (dibandingkan di `03_Modelling.ipynb`) |
| Backend | FastAPI |
| Frontend | HTML/CSS/JS vanilla + Chart.js/ApexCharts |
| Deploy (opsional) | Railway (backend) + Vercel (frontend) — pola sama seperti PanganTrack |

## 6. Struktur Folder

```
stock-analysis/
├── README.md
├── docker-compose.yml
├── requirements.txt
├── dags/
│   └── stock_pipeline_dag.py         # orkestrasi: fetch → build_features → train
├── dashboard/
│   ├── backend/
│   │   ├── main.py
│   │   ├── mlflow_client.py
│   │   └── routes/
│   │       ├── features.py           # GET feature importance
│   │       ├── history.py            # GET riwayat run (+ review tags)
│   │       ├── predict.py            # GET prediksi
│   │       └── review.py             # POST feedback backtest (checklist)
│   └── frontend/
│       ├── index.html
│       ├── css/style.css
│       └── js/
│           ├── app.js
│           ├── chart-config.js
│           └── review-form.js        # form checklist feedback
├── data/
│   ├── processed/                    # feature_matrix.parquet
│   └── raw/
│       ├── macro/                    # IHSG, kurs
│       ├── news/                     # berita mentah
│       └── price/                    # OHLCV per ticker, incremental
├── logs/                             # opsional, review log di luar MLflow
├── models/                           # model.pkl (kalau tidak pakai MLflow registry)
├── mlruns/ & mlflow.db               # auto-generated MLflow tracking
├── notebooks/
│   ├── 01_EDA.ipynb
│   ├── 02_Preprocessing.ipynb
│   ├── 03_Modelling.ipynb
│   └── 04_Evaluation.ipynb
└── src/
    ├── config.py                     # path, daftar ticker, parameter default
    ├── data/
    │   ├── fetch_price.py            # incremental fetch (append, bukan re-download)
    │   ├── fetch_news.py
    │   ├── fetch_macro.py
    │   └── build_features.py         # gabungin semua fitur jadi feature_matrix
    ├── features/
    │   ├── technical_indicators.py   # SMA, EMA, RSI, MACD, Bollinger, ATR, ROC, OBV
    │   ├── lag_features.py           # return lag, momentum
    │   ├── sentiment_features.py     # skor sentimen + volume berita
    │   ├── cross_sectional.py        # korelasi & rank antar saham sejenis
    │   └── calendar_features.py      # earnings date, hari libur
    └── models/
        ├── train.py                  # + mlflow.start_run()
        ├── predict.py
        └── evaluate.py               # backtesting time-based split
```

## 7. Status Saat Ini

Struktur folder sudah dibuat, sebagian besar masih kosong (baru scaffold). Belum ada implementasi di:
- `src/data/*`, `src/features/*`, `src/models/*`
- `dashboard/backend/routes/review.py` + `dashboard/frontend/js/review-form.js`
- `dags/stock_pipeline_dag.py`

## 8. Urutan Pengerjaan yang Disarankan

1. `config.py` — daftar ticker, path, parameter default (fondasi semua modul lain)
2. `fetch_price.py` (incremental) — supaya cepat lihat data nyata masuk
3. `technical_indicators.py` + `build_features.py` — feature matrix pertama
4. `train.py` + MLflow tracking — model & backtest pertama
5. Backend FastAPI (`predict.py`, `history.py`)
6. Frontend dasar (`index.html`, `app.js`)
7. `review.py` + `review-form.js` — siklus feedback
8. Airflow DAG — otomasi update data harian