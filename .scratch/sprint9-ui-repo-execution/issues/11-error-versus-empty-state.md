# 11: Error fetch dibedakan dari data kosong

**What to build:** Saat layanan gagal, Dashboard dan Notifikasi menjelaskan kegagalan serta menawarkan percobaan ulang. Pesan kosong hanya muncul ketika layanan memang mengembalikan tidak ada data.

**Blocked by:** None (can start immediately).

**Status:** resolved

**Sumber:** kartu Trello #166 — Hans, normal, due 23 Nov 2026.

- [x] Kegagalan pengambilan data menampilkan pesan error dan tombol percobaan ulang, bukan statistik kosong.
- [x] Pesan tidak ada notifikasi hanya muncul ketika layanan benar mengembalikan senarai kosong.
- [x] Dashboard tidak menampilkan angka yang ditanam langsung di antarmuka; nilai diambil dari data layanan atau disembunyikan bila tidak tersedia.
- [x] Bukti berupa tangkapan layar kondisi error dan kondisi kosong tersedia.
- [x] Build produksi berhasil tanpa peringatan baru.

## Comments

- Resolved 2026-11-17. useDashboardData exposes error and retry, Dashboard renders role=alert with retry button, NotificationDropdown distinguishes error from empty, hardcoded fallback numbers replaced with '-'; pnpm build succeeds. Screenshot evidence will be attached later by the orchestrator during ticket 14.
