# 10: Strategi cache katalog dan prasyarat

**Trello:** #59 — https://trello.com/c/DW7pv13j/59-mantra-implementasi-caching-strategy
**Repo:** `ftmm-compass-ui/backend`
**Owner:** Mantra
**Labels:** EPIC 4 — Integration & Refinement, Mantra, normal
**Due:** 2026-11-16
**Status:** ready-for-agent

**What to build:** Identifikasi query berulang pada `GET /api/v1/courses` dan pembacaan prasyarat, lalu terapkan cache in-process atau Redis dengan invalidasi saat admin menulis katalog. Dokumentasikan strategi dan batasnya.

**Blocked by:** Tiket 03 agar sumber data katalog final sebelum cache diterapkan.

- [ ] Daftar query yang di-cache memuat kunci cache, TTL, dan pemicu invalidasi untuk create/update/delete matkul.
- [ ] Dua request berturut-turut ke katalog menghasilkan hit cache yang teramati lewat metrik atau log; tidak ada perubahan payload.
- [ ] Setelah admin mengubah matkul, request berikutnya mengembalikan data baru tanpa menunggu TTL.
- [ ] Mode fallback lokal tidak ikut di-cache sehingga perubahan `data_loader.py` tetap terlihat pada saat pengembangan.
- [ ] Strategi cache tertulis di dokumentasi backend, termasuk alasan memilih medium dan perilaku saat cache gagal.
