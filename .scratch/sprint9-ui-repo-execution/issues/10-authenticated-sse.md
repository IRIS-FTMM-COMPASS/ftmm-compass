# 10: SSE terautentikasi dengan batas dan metrik

**What to build:** Percakapan streaming hanya melayani pengguna yang login dan tidak menerima identitas dari klien. Gateway menolak kelebihan koneksi dan memperlihatkan kondisi streaming pada probe kesehatan.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

**Sumber:** kartu Trello #162 — Mantra dan Darryl, high, due 23 Nov 2026.

- [ ] Permintaan streaming tanpa token ditolak dengan 401; identitas percakapan berasal dari token, bukan isi permintaan.
- [ ] Melebihi batas koneksi menghasilkan 429 atau 503, bukan kegagalan server atau permintaan menggantung.
- [ ] Antrean token yang melebihi batas menutup aliran dan menghentikan kerja yang tidak dipakai.
- [ ] Probe kesehatan menampilkan jumlah koneksi aktif, latensi token pertama, dan durasi streaming.
- [ ] Pengujian autentikasi, batas koneksi, dan pemutusan koneksi lulus.
