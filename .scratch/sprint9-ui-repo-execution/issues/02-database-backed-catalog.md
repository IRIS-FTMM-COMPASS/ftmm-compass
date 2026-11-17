# 02: Katalog dari database dengan fallback

**What to build:** Perubahan katalog yang dibuat admin langsung terlihat oleh mahasiswa tanpa membangun ulang aplikasi. Saat database tidak tersedia, katalog tetap terbuka dengan sumber data lokal dan pemberitahuan sumber yang jelas.

**Blocked by:** 01 — Katalog resmi tanpa data demo.

**Status:** ready-for-agent

**Sumber:** kartu Trello #136 — Mantra, high, due 23 Nov 2026.

- [ ] Permintaan katalog dengan filter program studi, semester, pencarian, dan pagination mengembalikan 200 dengan sumber `database`.
- [ ] Data yang ditulis admin muncul pada permintaan berikutnya tanpa proses rebuild.
- [ ] Saat database dimatikan sementara, katalog tetap 200 dengan sumber `local_fallback`, bukan 500.
- [ ] Bentuk envelope katalog tidak berubah sehingga layar yang sudah ada tidak perlu penyesuaian.
- [ ] Seluruh pengujian backend lulus, termasuk pengujian lama yang memakai envelope katalog.
