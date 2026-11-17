# 01: Katalog resmi tanpa data demo

**What to build:** Mahasiswa membuka Course Finder dan Degree Planner lalu hanya melihat kurikulum resmi lima program studi. Kode contoh dan polling demo tidak muncul, dan backend dapat berjalan tanpa seeder demo.

**Blocked by:** None (can start immediately).

**Status:** resolved

**Sumber:** kartu Trello #142 — Mantra, normal, due 23 Nov 2026.

- [x] Keputusan pemisahan data demo ditulis bersama alasannya; hanya satu strategi yang diterapkan.
- [x] Backend start tanpa data demo dan semua rangkaian pengujian tetap lulus.
- [x] Katalog publik tidak mengembalikan kode contoh KIK101 dan tidak menampilkan kode polling demo yang sama dengan mata kuliah resmi.
- [x] Akun tes yang dibutuhkan pengujian otomatis berasal dari fixture, bukan dari kurikulum demo aktif.
- [x] Cara menjalankan mode demo didokumentasikan untuk pengembang.

## Comments

- Resolved 2026-11-17. AUTO_SEED default changed to false in backend/settings.py; strategy documented in docs/demo-data-policy.md; regression test test_public_catalog_excludes_demo_only_codes passes.
