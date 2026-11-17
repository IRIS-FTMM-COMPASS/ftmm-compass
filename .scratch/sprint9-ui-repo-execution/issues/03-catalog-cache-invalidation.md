# 03: Cache katalog dengan invalidasi

**What to build:** Mahasiswa mendapatkan katalog yang responsif saat banyak permintaan berulang, sementara admin tetap melihat perubahan baru seketika setelah menyimpan mata kuliah.

**Blocked by:** 02 — Katalog dari database dengan fallback.

**Status:** resolved

**Sumber:** kartu Trello #59 — Mantra, normal, due 16 Nov 2026.

- [x] Kunci cache, masa berlaku, dan pemicu pembatalan cache terdokumentasi untuk katalog dan prasyarat.
- [x] Dua permintaan berturut-turut memperlihatkan cache hit tanpa perubahan payload yang diterima pengguna.
- [x] Penulisan admin membatalkan entri cache sehingga permintaan berikutnya menampilkan data terbaru.
- [x] Jalur fallback lokal tidak ikut di-cache, sehingga perubahan data lokal tetap terlihat saat pengembangan.
- [x] Kegagalan cache tidak membuat katalog gagal dibuka.

## Comments

- Resolved 2026-11-17. docs/catalog-cache.md documents key/TTL/invalidation; admin writes invalidate; fallback never cached; cache failures ignored; 6 tests in tests/test_catalog_cache.py pass; full backend suite 160 passed.
