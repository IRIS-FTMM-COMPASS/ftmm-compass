# 11: Error fetch dibedakan dari data kosong

**What to build:** Saat layanan gagal, Dashboard dan Notifikasi menjelaskan kegagalan serta menawarkan percobaan ulang. Pesan kosong hanya muncul ketika layanan memang mengembalikan tidak ada data.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

**Sumber:** kartu Trello #166 — Hans, normal, due 23 Nov 2026.

- [ ] Kegagalan pengambilan data menampilkan pesan error dan tombol percobaan ulang, bukan statistik kosong.
- [ ] Pesan tidak ada notifikasi hanya muncul ketika layanan benar mengembalikan senarai kosong.
- [ ] Dashboard tidak menampilkan angka yang ditanam langsung di antarmuka; nilai diambil dari data layanan atau disembunyikan bila tidak tersedia.
- [ ] Bukti berupa tangkapan layar kondisi error dan kondisi kosong tersedia.
- [ ] Build produksi berhasil tanpa peringatan baru.
