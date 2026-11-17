# 01: Admin mengelola katalog dengan rantai prasyarat yang tersimpan

**What to build:** Admin dapat membuat dan mengubah mata kuliah beserta rantai prasyaratnya melalui antarmuka admin. Data prasyarat benar-benar tersimpan dan terbaca kembali, detail satu mata kuliah dapat diambil lewat API, dan katalog langsung mencerminkan perubahan tanpa langkah rebuild manual.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Admin dapat membuat mata kuliah beserta daftar prasyarat; prasyarat terbaca kembali melalui endpoint detail.
- [ ] Admin dapat mengubah mata kuliah dan prasyaratnya; nilai baru muncul di daftar katalog dan di endpoint detail.
- [ ] Kode mata kuliah duplikat ditolak dengan status 409 dan envelope error kanonik.
- [ ] Parameter di luar batas ditolak dengan status 422 dan envelope error kanonik.
- [ ] Kode mata kuliah yang tidak terdaftar mengembalikan status 404 dengan kode error `course_not_found`.
- [ ] Test API mencakup keenam skenario di atas dan lulus dengan database yang sudah di-seed.
- [ ] Kartu Trello terkait menjadi bukti implementasi untuk ticket sinkronisasi akhir.
