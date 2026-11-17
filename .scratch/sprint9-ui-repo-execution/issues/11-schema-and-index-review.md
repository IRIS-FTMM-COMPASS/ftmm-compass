# 11: Review schema dan optimasi indeks database

**Trello:** #60 — https://trello.com/c/PJPtOUIm/60-darryl-review-optimasi-database-schema
**Repo:** `ftmm-compass-ui/database`
**Owner:** Darryl
**Labels:** EPIC 4 — Integration & Refinement, Darryl, normal
**Due:** 2026-11-16
**Status:** ready-for-agent

**What to build:** Ukur query lambat pada skema berjalan, tambahkan indeks yang diperlukan lewat migrasi Alembic reversible, dan verifikasi kelengkapan relasi prasyarat DAG. Koordinasikan hasilnya dengan tiket 03 dan 09.

**Blocked by:** None.

- [ ] Laporan berisi daftar query dengan waktu eksekusi sebelum dan sesudah perubahan, disertai `EXPLAIN (ANALYZE, BUFFERS)`.
- [ ] Indeks baru dibuat lewat file migrasi dengan `upgrade()` dan `downgrade()`, memakai `CREATE INDEX IF NOT EXISTS`.
- [ ] Relasi prasyarat tidak mengandung node yatim dan tetap acyclic; pemeriksaan lulus pada data ter-seed penuh.
- [ ] `alembic upgrade head` lalu `downgrade -1` berhasil tanpa objek sisa.
- [ ] Tidak ada perubahan DDL manual di luar berkas migrasi.
