# 03: Katalog publik dari PostgreSQL dengan fallback lokal

**Trello:** #136 — https://trello.com/c/iHzMTlbL/136-mantra-migrasi-endpoint-get-api-v1-courses-ke-postgresql-session-getdb-dengan-fallback-cache
**Repo:** `ftmm-compass-ui/backend`
**Owner:** Mantra
**Labels:** high, EPIC 4 — Integration & Refinement, Mantra
**Due:** 2026-11-23
**Status:** ready-for-agent

**What to build:** Ubah `handle_list_courses` dan `handle_search_courses` di `backend/app.py` agar membaca `courses`, `curriculum_courses`, dan `curricula` lewat `AsyncSession = Depends(get_db)`. Fallback ke `data_loader.py` hanya saat database tidak tersedia.

**Blocked by:** None.

- [ ] `GET /api/v1/courses?prodi=TSD&page=1&per_page=10` mengembalikan 200 dengan `source: "database"` dan envelope `{source, data, meta}`.
- [ ] Filter prodi, semester, pagination, dan pencarian menghasilkan `meta.total`, `page`, `per_page`, `total_pages` yang sesuai isi database.
- [ ] Database dimatikan sementara → endpoint tetap 200 dengan `source: "local_fallback"`; tidak ada 500.
- [ ] Perubahan katalog lewat endpoint admin langsung terbaca di list tanpa rebuild proses.
- [ ] `uv run --directory backend python -m pytest tests -q` lulus, termasuk test lama yang memakai envelope lama.
