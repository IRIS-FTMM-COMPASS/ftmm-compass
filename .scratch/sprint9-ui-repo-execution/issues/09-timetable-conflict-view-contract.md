# 09: Kunci kontrak query v_timetable_conflicts

**Trello:** #143 — https://trello.com/c/JaRBiOF9/143-darryl-kunci-kontrak-query-vtimetableconflicts-wajib-filter-timetableid
**Repo:** `ftmm-compass-ui/database`
**Owner:** Darryl
**Labels:** EPIC 4 — Integration & Refinement, Darryl, normal
**Due:** 2026-11-23
**Status:** ready-for-agent

**What to build:** Tetapkan kontrak bahwa setiap pemakaian aplikasi harus memakai `WHERE timetable_id = :id`, lengkap dengan benchmark pembanding, rencana eksekusi, dan pemeriksaan statis yang menolak pemakaian tanpa filter.

**Blocked by:** None. Harus selesai sebelum endpoint timetable memakai view.

- [ ] `database/bench/RESULTS.md` memuat angka terukur query terfilter < 1 ms dan full scan ±23 ms beserta perintah reproduksi.
- [ ] `database/bench/benchmark_queries.sql` berisi pasangan query terfilter dan full scan dengan `EXPLAIN (ANALYZE, BUFFERS)`.
- [ ] Pemeriksaan statis gagal ketika menemukan referensi `v_timetable_conflicts` tanpa filter `timetable_id`.
- [ ] Tidak ada pemanggilan tanpa filter di kode aplikasi, dibuktikan dengan pencarian pada commit.
