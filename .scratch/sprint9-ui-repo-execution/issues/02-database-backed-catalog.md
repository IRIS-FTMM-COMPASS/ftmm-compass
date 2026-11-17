# 02: Katalog dari database dengan fallback

**What to build:** Perubahan katalog yang dibuat admin langsung terlihat oleh mahasiswa tanpa membangun ulang aplikasi. Saat database tidak tersedia, katalog tetap terbuka dengan sumber data lokal dan pemberitahuan sumber yang jelas.

**Blocked by:** 01 — Katalog resmi tanpa data demo.

**Status:** resolved

**Sumber:** kartu Trello #136 — Mantra, high, due 23 Nov 2026.

- [x] Permintaan katalog dengan filter program studi, semester, pencarian, dan pagination mengembalikan 200 dengan sumber `database`.
- [x] Data yang ditulis admin muncul pada permintaan berikutnya tanpa proses rebuild.
- [x] Saat database dimatikan sementara, katalog tetap 200 dengan sumber `local_fallback`, bukan 500.
- [x] Bentuk envelope katalog tidak berubah sehingga layar yang sudah ada tidak perlu penyesuaian.
- [x] Seluruh pengujian backend lulus, termasuk pengujian lama yang memakai envelope katalog.

## Comments

- Resolved 2026-11-17. catalog.get_catalog_from_source() reads authoritative curriculum from PostgreSQL and returns source 'database', falls back to 'local_fallback'; envelope unchanged; 12 tests in tests/test_courses.py pass.
