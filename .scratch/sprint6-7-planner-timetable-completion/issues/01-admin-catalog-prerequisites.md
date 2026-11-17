# 01: Admin mengelola katalog dengan rantai prasyarat yang tersimpan

**What to build:** Admin dapat membuat dan mengubah mata kuliah beserta rantai prasyaratnya melalui antarmuka admin. Data prasyarat benar-benar tersimpan dan terbaca kembali, detail satu mata kuliah dapat diambil lewat API, dan katalog langsung mencerminkan perubahan tanpa langkah rebuild manual.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] Admin dapat membuat mata kuliah beserta daftar prasyarat; prasyarat terbaca kembali melalui endpoint detail.
- [x] Admin dapat mengubah mata kuliah dan prasyaratnya; nilai baru muncul di daftar katalog dan di endpoint detail.
- [x] Kode mata kuliah duplikat ditolak dengan status 409 dan envelope error kanonik.
- [x] Parameter di luar batas ditolak dengan status 422 dan envelope error kanonik.
- [x] Kode mata kuliah yang tidak terdaftar mengembalikan status 404 dengan kode error `course_not_found`.
- [x] Test API mencakup keenam skenario di atas dan lulus dengan database yang sudah di-seed.
- [x] Kartu Trello terkait menjadi bukti implementasi untuk ticket sinkronisasi akhir.

## Comments

- Resolved 2026-11-17. `GET /api/v1/courses/{code}` + alias legacy, `replace_prerequisites` menulis `course_requirement_rules`/`nodes`, update benar-benar menerapkan field, 409/422/404 memakai envelope kanonik. 17 test terarah lulus; suite akhir 104 lulus. Trello #40. Commit `422f4b0`, `bf28340`, `ff2f0c4`.
