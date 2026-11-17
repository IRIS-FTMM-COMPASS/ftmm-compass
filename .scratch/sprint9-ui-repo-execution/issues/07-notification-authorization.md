# 07: Tutup IDOR notifikasi dan samakan mark-all

**Trello:** #161 — https://trello.com/c/GrvHCuMb/161-mantra-perbaiki-otorisasi-notifikasi-dan-konsistensi-mark-all
**Repo:** `ftmm-compass-ui/backend`
**Owner:** Mantra
**Labels:** high, EPIC 4 — Integration & Refinement, Mantra
**Due:** 2026-11-23
**Status:** ready-for-agent

**What to build:** Tambahkan filter `Notification.user_id == current_user.user_id` pada `POST /notifications/{id}/read`, kembalikan 404 untuk notifikasi milik user lain, dan samakan kriteria mark-all dengan query listing yang memang menampilkan notifikasi global.

**Blocked by:** None. Merupakan bagian #62 yang dipisah.

- [ ] User A menandai notifikasi user B → 404; test regresi menetapkan perilaku ini.
- [ ] Setelah mark-all, seluruh ID yang muncul di `GET /notifications` berstatus terbaca.
- [ ] Notifikasi global yang tampil di listing ikut tertandai, sedangkan yang tidak tampil tidak berubah.
- [ ] Bentuk response bagi klien sah tidak berubah.
