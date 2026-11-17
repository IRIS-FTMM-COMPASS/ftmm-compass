# 09: Notifikasi milik pengguna dan mark-all

**What to build:** Pengguna hanya bisa menandai notifikasinya sendiri. Aksi tandai semua mengikuti daftar yang benar-benar tampil, sehingga tidak ada notifikasi yang berubah status tanpa terlihat.

**Blocked by:** None (can start immediately).

**Status:** resolved

**Sumber:** kartu Trello #161 — Mantra, high, due 23 Nov 2026.

- [x] Pengguna mencoba menandai notifikasi pengguna lain mendapatkan 404 dan datanya tidak berubah.
- [x] Setelah tandai semua, seluruh notifikasi yang muncul pada daftar berstatus terbaca.
- [x] Notifikasi global yang tidak ditampilkan tidak ikut berubah status.
- [x] Pengujian regresi menetapkan perilaku tersebut dan bentuk respons bagi pengguna sah tidak berubah.

## Comments

- Resolved 2026-11-17. shared _visible_notification_filter used by list, mark and mark-all; foreign notification returns 404; 4 tests in tests/test_notifications.py pass.
