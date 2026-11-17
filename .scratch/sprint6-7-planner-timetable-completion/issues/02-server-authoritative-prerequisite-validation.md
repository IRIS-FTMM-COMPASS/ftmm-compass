# 02: Validasi prasyarat rencana studi menjadi wewenang server

**What to build:** Mahasiswa menyusun rencana studi dengan umpan balik prasyarat yang tetap cepat di antarmuka, tetapi gateway menjadi pemegang aturan akhir. Rencana yang melanggar prasyarat ditolak berdasarkan data di database walaupun klien tidak mengirim daftar prasyarat.

**Blocked by:** 01 — Admin mengelola katalog dengan rantai prasyarat yang tersimpan.

**Status:** ready-for-agent

- [ ] Gateway menolak rencana yang melanggar prasyarat meski klien mengirim array prasyarat kosong.
- [ ] Prasyarat diambil dari sumber data resmi di database, bukan dari payload yang dikirim klien.
- [ ] Umpan balik lokal di modal detail mata kuliah tetap tampil, tetapi keputusan akhir berasal dari endpoint validasi gateway.
- [ ] Test penolakan prasyarat yang baru lulus bersama test parity semester dan batas SKS yang sudah ada.
- [ ] Jalur penyimpanan rencana tidak menjalankan validasi akademik tambahan; aturan akademik tetap memiliki satu pemilik.
