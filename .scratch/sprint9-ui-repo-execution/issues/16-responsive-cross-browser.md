# 16: Responsive design dan uji cross-browser (carryover Sprint 8)

**Trello:** #58 — https://trello.com/c/mCbV2fom/58-hans-responsive-design-cross-browser-testing
**Repo:** `ftmm-compass-ui/src`
**Owner:** Hans
**Labels:** high, EPIC 4 — Integration & Refinement, Hans
**Due:** 2026-11-16
**Status:** ready-for-agent

**What to build:** Pastikan seluruh halaman tetap dapat dibaca dan dipakai pada desktop, tablet, dan mobile, lalu uji pada Chrome, Firefox, dan Safari. Perbaiki temuan dan susun laporan end-to-end dari sudut pandang pengguna.

**Blocked by:** Tiket 12 dan 13 agar perubahan UI terbaru tidak dikerjakan ulang.

- [ ] Tidak ada overflow horizontal pada lebar 375, 768, dan 1280 px di semua halaman.
- [ ] Target sentuh minimal 44 × 44 px dan setiap elemen interaktif memiliki focus state yang terlihat.
- [ ] Laporan memuat matriks halaman × browser dengan hasil lulus/gagal dan catatan perbaikan.
- [ ] Tidak ada error console pada ketiga browser; screenshot per breakpoint terlampir.
- [ ] `pnpm format` dan `pnpm --silent build -- --logLevel warn` lulus.
