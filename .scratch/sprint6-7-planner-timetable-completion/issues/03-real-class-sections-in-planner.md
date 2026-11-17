# 03: Jadwal kelas nyata tersedia di planner

**What to build:** Mahasiswa membuka Degree Planner dan melihat kelas paralel yang benar-benar tersedia untuk mata kuliah pada periode akademik aktif, lengkap dengan hari, jam, dan ruang. Panel pemilih kelas tidak lagi menampilkan daftar kosong.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Endpoint pembaca section mengembalikan section dan jadwal dari tabel kelas di database untuk periode aktif, menggunakan envelope koleksi standar.
- [ ] Mahasiswa melihat daftar section nyata di panel pemilih kelas, termasuk kode section, hari, jam mulai, jam selesai, dan ruang.
- [ ] Kode mata kuliah yang tidak ada mengembalikan 404 dengan kode `course_not_found`; parameter tidak valid mengembalikan 422 dengan envelope error kanonik.
- [ ] Saat belum ada section untuk suatu mata kuliah, antarmuka menampilkan pesan yang menyebut penyebab dan tindakan berikutnya, bukan daftar kosong yang diam-diam gagal.
- [ ] Test API mencakup kasus sukses, tidak ditemukan, dan kondisi tanpa section; seluruhnya lulus.
