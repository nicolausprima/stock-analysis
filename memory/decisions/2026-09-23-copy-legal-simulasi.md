# ADR 2026-09-23 — Copy legal: simulasi, tanpa janji profit

Kembali ke: [[../project-overview]]

## Masalah

Copy hadapan pengguna berisiko dibaca sebagai nasihat beli + janji untung tanpa lisensi Penasihat Investasi (risiko pidana UU P2SK). Sumber: `../AUDIT_REPORT_2026-09-22.md` tim Hukum & Etika.

## Opsi

1. Pertahankan klaim performa — ditolak: risiko hukum.
2. Netralkan semua copy + watermark simulasi + disclaimer (dipilih).
3. Hapus semua angka — ditolak: hilangkan nilai riset.

## Keputusan

Opsi 2: kata terlarang (`High-Conviction`, `Realized …`, `Deploy Alpha`, `Get Tomorrow`, `pasti/janji untung`) = 0 di README + frontend; nilai = `SIM-WIN`/`SIM-LOSS`; watermark `SIMULASI BACKTEST — bukan hasil nyata`; disclaimer ID + DYOR di hero/CTA/dashboard/footer/broadcast/README.

## Konsekuensi

Setiap angka performa baru wajib label simulasi + metodologi (gross-of-cost) + tanggal. Klaim tanpa bukti = hapus.
