# 02: Validasi prasyarat rencana studi menjadi wewenang server

**What to build:** Mahasiswa menyusun rencana studi dengan umpan balik prasyarat yang tetap cepat di antarmuka, tetapi gateway menjadi pemegang aturan akhir. Rencana yang melanggar prasyarat ditolak berdasarkan data di database walaupun klien tidak mengirim daftar prasyarat.

**Blocked by:** 01 — Admin mengelola katalog dengan rantai prasyarat yang tersimpan.

**Status:** resolved

- [x] Gateway menolak rencana yang melanggar prasyarat meski klien mengirim array prasyarat kosong.
- [x] Prasyarat diambil dari sumber data resmi di database, bukan dari payload yang dikirim klien.
- [x] Umpan balik lokal di modal detail mata kuliah tetap tampil, tetapi keputusan akhir berasal dari endpoint validasi gateway.
- [x] Test penolakan prasyarat yang baru lulus bersama test parity semester dan batas SKS yang sudah ada.
- [x] Jalur penyimpanan rencana tidak menjalankan validasi akademik tambahan; aturan akademik tetap memiliki satu pemilik.

## Comments

- Resolved 2026-11-17. `handle_validate_plan` mengisi prasyarat dari katalog/database sebelum `validate_plan_constraints`; array klien ditimpa. Aksi "Validasi Rencana Studi" memanggil gateway; persistence tetap tanpa validasi akademik. QA browser: HTTP 200 dan teks hasil validasi tampil. Trello #53. Commit `39e1c33`, `421226d`.
