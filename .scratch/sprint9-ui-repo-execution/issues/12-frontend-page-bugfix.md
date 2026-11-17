# 12: Bug fixing seluruh halaman frontend

**Trello:** #63 — https://trello.com/c/K3720nCu/63-hans-bug-fixing-frontend-semua-halaman
**Repo:** `ftmm-compass-ui/src`
**Owner:** Hans
**Labels:** high, EPIC 4 — Integration & Refinement, Hans
**Due:** 2026-11-23
**Status:** ready-for-agent

**What to build:** Perbaiki bug hasil testing internal: masalah layout, state management, loading state yang tidak konsisten, dan error handling di semua halaman. Tiket 14 dan 15 memuat dua perbaikan yang dipisah agar buktinya jelas.

**Blocked by:** Tiket 14 dan 15 untuk perbaikan sesi dan error state.

- [ ] Setiap halaman memiliki state loading, error, dan empty yang teramati di browser, bukan tampilan kosong tanpa penjelasan.
- [ ] Navigasi antar halaman tidak menyisakan state lama setelah perpindahan tab pada `App.tsx`.
- [ ] Tidak ada tombol mati atau aksi yang gagal tanpa umpan balik; semua kontrol dapat dicapai via keyboard dengan focus ring terlihat.
- [ ] `pnpm format` dan `pnpm --silent build -- --logLevel warn` lulus.
- [ ] Screenshot desktop dan mobile dari halaman yang diubah terlampir sebagai bukti.
