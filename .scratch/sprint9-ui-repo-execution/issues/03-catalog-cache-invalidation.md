# 03: Cache katalog dengan invalidasi

**What to build:** Mahasiswa mendapatkan katalog yang responsif saat banyak permintaan berulang, sementara admin tetap melihat perubahan baru seketika setelah menyimpan mata kuliah.

**Blocked by:** 02 — Katalog dari database dengan fallback.

**Status:** ready-for-agent

**Sumber:** kartu Trello #59 — Mantra, normal, due 16 Nov 2026.

- [ ] Kunci cache, masa berlaku, dan pemicu pembatalan cache terdokumentasi untuk katalog dan prasyarat.
- [ ] Dua permintaan berturut-turut memperlihatkan cache hit tanpa perubahan payload yang diterima pengguna.
- [ ] Penulisan admin membatalkan entri cache sehingga permintaan berikutnya menampilkan data terbaru.
- [ ] Jalur fallback lokal tidak ikut di-cache, sehingga perubahan data lokal tetap terlihat saat pengembangan.
- [ ] Kegagalan cache tidak membuat katalog gagal dibuka.
