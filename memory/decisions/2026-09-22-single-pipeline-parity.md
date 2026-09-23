# ADR 2026-09-22 — Pipeline tunggal + model_card + assert skema

Kembali ke: [[../project-overview]]

## Masalah

Sinyal beli invalid: serve bangun one-hot `Tick_*` sementara scaler dilatih di skema `Embed_*`; label vs horizon tidak selaras; kolom masa depan (`Next_Day_*`) ikut tersimpan; artefak tanpa target/horizon/cutoff. Sumber: `../AUDIT_REPORT_2026-09-22.md` AI-01/AI-02/AI-03.

## Opsi

1. Hapus `src/screener.py` — cepat, tapi hilangkan serve.
2. Pipeline tunggal + `model_card.json` + assert urutan kolom (dipilih).
3. Adapter skema Tick_→Embed_ — ditolak: sembunyikan skew, bukan perbaiki.

## Keputusan

Opsi 2: `build_serve_matrix` (kolom urut `expected_cols`, tolak `Tick_*`/NaN), `FUTURE_COLS` + `write_model_card`, label open-to-close, notebook cutoff quantile(0.8) + embargo 5B + median train-only, retrain penuh 2026-09-23 (cutoff 2025-04-21, train 100472/test 24738).

## Konsekuensi

Retrain wajib tiap ubah target/fitur; artefak lama = stale; serve gagal keras (ValueError/RuntimeError) lebih baik dari sinyal salah.
