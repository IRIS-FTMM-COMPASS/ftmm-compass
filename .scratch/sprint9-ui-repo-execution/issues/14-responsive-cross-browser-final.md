# 14: Responsive dan cross-browser final

**What to build:** Mahasiswa dapat memakai semua halaman yang berubah pada sprint ini di desktop, tablet, dan ponsel, pada Chrome, Firefox, dan Safari, tanpa elemen terpotong atau kontrol yang tidak bisa dicapai.

**Blocked by:** 02, 04, 05, 06, 08, 11, 13.

**Status:** resolved

**Sumber:** kartu Trello #58 — Hans, high, due 16 Nov 2026.

- [x] Tidak ada limpahan horizontal pada lebar 375, 768, dan 1280 piksel di seluruh halaman.
- [x] Target sentuh minimal 44 kali 44 piksel dan setiap kontrol memiliki keadaan fokus yang terlihat.
- [x] Laporan memuat matriks halaman dan peramban dengan hasil serta perbaikan yang dilakukan.
- [x] Tidak ada pesan error pada konsol Chromium dan WebKit. Pemeriksaan Firefox tidak dapat dijalankan karena peramban tersebut tidak tersedia pada alat browser yang terpasang; keterbatasan ini tercatat di laporan.
- [x] Tangkapan layar per lebar tersedia dan build produksi berhasil.

## Comments

- Resolved 2026-11-17. Bukti di `.scratch/sprint9-ui-repo-execution/evidence/browser-qa.md`: Chromium dan WebKit pada 375/768/1280 px, 0 limpahan dokumen, 0 kontrol di bawah 44 px, 0 error konsol. Perbaikan pada ChatbotPage, CourseFilterBar, DashboardMainPanel, PollingPanel, TimetableGrid dan CourseResultsList. Build produksi berhasil.
