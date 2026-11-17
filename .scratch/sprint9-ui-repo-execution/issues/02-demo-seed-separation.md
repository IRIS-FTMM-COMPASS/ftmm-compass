# 02: Putuskan nasib data demo seed.py

**Trello:** #142 — https://trello.com/c/eGFSLx0E/142-mantra-putuskan-nasib-seedpy-demo-agar-tidak-bercampur-dengan-katalog-asli
**Repo:** `ftmm-compass-ui/backend`, `database/seed/`
**Owner:** Mantra
**Labels:** EPIC 4 — Integration & Refinement, Mantra, normal
**Due:** 2026-11-23
**Status:** ready-for-agent

**What to build:** Inventarisasi pemakaian data demo (kurikulum "TSD 2023", KIK101, akun tes, polling SID307/TEL302), pilih satu strategi — hapus ke fixture test, flag `SEED_DEMO_DATA` yang default nonaktif, atau namespace kode khusus — lalu terapkan dan dokumentasikan alasannya.

**Blocked by:** None. Menjadi prasyarat kredensial seed pada tiket 04.

- [ ] Keputusan tertulis memuat alasan dan opsi yang ditolak; tidak ada dua strategi yang diterapkan sekaligus.
- [ ] Startup backend tanpa data demo berhasil; `seed_full_catalog.py` tetap manual dan tidak dipanggil otomatis.
- [ ] `GET /api/v1/courses` saat mode demo nonaktif tidak mengembalikan KIK101 dan tidak menampilkan SID307/TEL302 ganda.
- [ ] `backend/test_backend.py`, `test_api_endpoints.py`, dan `test_polling_api.py` tidak bergantung pada kurikulum demo dan tetap lulus.
- [ ] `database/seed/README.md` memuat nama flag atau fixture, perintah reproduksi demo, dan alasan keputusan.
