# ADR 2026-09-23 — Telegram fail-closed + cooldown

Kembali ke: [[../project-overview]]

## Masalah

Bot tanpa allowlist + token di disk: siapa pun picu scan 700+ ticker (DoS/biaya), kirim atas nama bot. Verifier temukan sisa celah: `get_active_chat_id()` fallback env tunggal + bypass kirim saat allowlist kosong.

## Opsi

1. Biarkan backward-compat — ditolak: celah takeover.
2. Fail-closed penuh + cooldown + single-flight + disclaimer (dipilih).
3. Matikan bot — ditolak: hilangkan kanal utama.

## Keputusan

Opsi 2: `is_chat_allowed` tolak saat allowlist kosong; `get_active_chat_id` return `""` bila env tak di allowlist; guard kirim tanpa bypass; cooldown 60 dtk/chat + single-flight job berat; token per-call tanpa log; escape HTML; disclaimer tiap pesan. S-3 (revoke + env prod) oleh user.

## Konsekuensi

Deploy tanpa `TELEGRAM_ALLOWED_CHAT_IDS` = bot bisu (sengaja). Rotasi token tanpa restart didukung.
