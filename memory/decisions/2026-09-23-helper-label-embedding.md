# ADR 2026-09-23 — Helper label tunggal + embedding propagasi NaN

Kembali ke: [[../project-overview]]

## Masalah

S-4: dua path label (notebook temp `next_open/next_close` + `iloc[:-1]` vs builder `Next_Day_*` + drop) — setara tapi drift risk. S-5: `embedding.py` fillna default sembunyikan warm-up.

## Opsi

1. Biarkan + dokumentasi — ditolak untuk S-4 (drift pasti terjadi).
2. Helper tunggal + propagasi NaN (dipilih).
3. Helper + pertahankan fill-0 embed — ditolak: sinyal palsu.

## Keputusan

Opsi 2: `src/features/labels.py` (`compute_open_to_close_label` + `add_open_to_close_label`) dipakai notebook sel 4 dan `build_features.py:14,63-67`; `embedding.py` hapus fillna inti + final, NaN merambat, `strict_warmup` guard untuk serve. Test extended diselaraskan ke kontrak propagasi. Hasil: parity 9 + embeddings 12 + full 53 passed, ruff 0.

## Konsekuensi

Artefak S-1 (retrain sebelum S-5) berperilaku warm-up lama — retrain ulang sebelum klaim parity artefak. Serve path disarankan `strict_warmup=True` atau `drop_warmup_rows` + `build_serve_matrix`.
