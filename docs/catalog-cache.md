# Cache katalog dan invalidasi

Dokumen ini merangkum kontrak cache katalog publik yang dipakai oleh endpoint
`/courses` dan `/courses/search`. Cache berada di dalam proses backend, memakai
`time.monotonic()` untuk masa berlaku, dan tidak menambah dependensi baru.

## Kunci cache

Cache menyimpan payload lengkap respons, bukan hanya daftar mata kuliah. Kunci
adalah tuple yang mencakup seluruh filter yang sudah dinormalisasi:

- `("list", norm_prodi, semester, q, page, per_page)` untuk daftar katalog.
- `("search", q, norm_prodi, top_k)` untuk pencarian.

`norm_prodi` berasal dari `normalize_prodi(prodi or program_studi)`, sehingga
alias seperti `tsd` dan nama lengkap menghasilkan kunci yang sama. Nilai `q`,
`semester`, `page`, `per_page`, dan `top_k` dipakai apa adanya karena nilai itu
juga memengaruhi `links`, `query`, dan isi payload yang dikirim ke pengguna.
Awalan `list` dan `search` mencegah tabrakan antarke dua handler.

Dua permintaan dengan kunci yang sama dalam masa berlaku mengembalikan salinan
payload yang identik. Entri disalin dengan `copy.deepcopy` saat ditulis dan dibaca
agar pemanggil tidak dapat mengubah isi cache.

## Masa berlaku

TTL adalah 30 detik, dihitung dengan `time.monotonic()` agar tidak terpengaruh
perubahan jam sistem. Entri kedaluwarsa dihapus saat dibaca, lalu permintaan
dihitung ulang dari database. TTL hanya menjadi pengaman; penulisan admin
langsung membatalkan cache lebih awal.

## Sumber yang di-cache

Hanya respons dengan `source == "database"` yang disimpan. Jalur
`local_fallback` tidak pernah ditulis ke cache, sehingga perubahan berkas
`Ekstrak/*.json` tetap terlihat segera saat pengembangan. Nilai `source` pada
envelope respons tidak diubah.

## Pemicu invalidasi

`invalidate_catalog_cache()` menghapus seluruh entri cache dan dipanggil oleh
ketiga handler admin di `backend/api/courses.py` setelah `commit` dan
`refresh_from_db`:

- `POST /admin/courses` saat mata kuliah dibuat.
- `PUT /admin/courses/{course_id}` saat mata kuliah diubah.
- `DELETE /admin/courses/{course_id}` saat mata kuliah dinonaktifkan.

`refresh_from_db` tetap menjadi sumber kebenaran untuk `_CURRICULUM`, yang
dipakai endpoint detail matakuliah. Cache respons dan `_CURRICULUM` keduanya
diperbarui pada setiap penulisan admin, sehingga tidak ada data lama yang
tersisa. Penulisan langsung ke database di luar handler admin tidak memicu
invalidasi dan baru terlihat setelah TTL berakhir.

## Prasyarat

Prasyarat tidak memiliki cache tersendiri. Data prasyarat dibangun oleh
`_load_requirement_leaves` di dalam `build_catalog_from_db` dan menjadi bagian
dari setiap `CourseModel` pada payload katalog. Dengan demikian prasyarat
mengikuti kunci, TTL, dan pemicu invalidasi yang sama dengan katalog. Endpoint
detail membaca prasyarat dari `_CURRICULUM` yang disegarkan oleh
`refresh_from_db`, bukan dari cache respons.

## Kegagalan cache

Seluruh operasi cache, termasuk penyalinan payload, dibungkus penanganan
exception. Kegagalan membaca cache dianggap sebagai cache miss, dan kegagalan
menulis cache diabaikan. Permintaan tetap dihitung dari `get_catalog_from_source`
seperti biasa, sehingga gangguan cache tidak pernah membuat katalog gagal dibuka.
