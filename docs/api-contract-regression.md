# Regresi kontrak API dua tier

Dokumen ini merangkum cakupan pengujian kontrak HTTP antara jalur kanonik `/api/v1` dan jalur lawas `/api`. Pengujian berada di `backend/tests/test_api_contract.py` dan memakai fixture `client` dari `backend/tests/conftest.py`.

Nama rute validasi yang terpasang di router adalah `/plans/validations` dengan bentuk jamak. Jalur kanoniknya adalah `POST /api/v1/plans/validations`, sedangkan alias lawasnya adalah `POST /api/plan/validate`. Kedua rute memakai satu handler yang sama.

## Cakupan pasangan endpoint

| No | Pasangan | Jalur kanonik | Jalur lawas | Kode status yang diuji | Kode amplop error yang teramati |
|----|----------|---------------|-------------|------------------------|---------------------------------|
| 1 | Kesehatan layanan | `GET /api/v1/health` | `GET /api/health` | 200 | Tidak ada, respons sukses |
| 2 | Daftar mata kuliah | `GET /api/v1/courses` | `GET /api/courses` | 200 | Tidak ada, respons sukses |
| 3 | Pencarian mata kuliah | `GET /api/v1/courses/search?q=kalkulus` | `GET /api/courses/search?q=kalkulus` | 200 | Tidak ada, respons sukses |
| 4 | Detail mata kuliah | `GET /api/v1/courses/AGI101` | `GET /api/courses/AGI101` | 200 | Tidak ada, respons sukses |
| 5 | Dasbor mahasiswa | `GET /api/v1/dashboard/me` | `GET /api/dashboard/me` | 200 | Tidak ada, respons sukses |
| 6 | Validasi rencana studi | `POST /api/v1/plans/validations` | `POST /api/plan/validate` | 200 | Tidak ada, `is_valid` bernilai false |
| 7 | Notifikasi mahasiswa | `GET /api/v1/notifications/me` | `GET /api/notifications/me` | 200 | Tidak ada, respons sukses |
| 8 | Registrasi mahasiswa | `POST /api/v1/auth/register` | `POST /api/auth/register` | 422 | `validation_error` (detail `invalid_email_domain`) |
| 9 | Pemulihan kata sandi | `POST /api/v1/auth/recover` | `POST /api/auth/recover` | 400 | `invalid_recovery_code` |
| 10 | Perubahan kata sandi | `POST /api/v1/auth/change-password` | `POST /api/auth/change-password` | 400 | `invalid_current_password` |
| 11 | Daftar akun administrasi | `GET /api/v1/admin/accounts` | `GET /api/admin/accounts` | 200 dan 403 | Sukses tanpa `error`; `forbidden` untuk peran non-admin |
| 12 | Streaming chat tanpa autentikasi | `POST /api/v1/chat/stream` | `POST /api/chat/stream` | 401 | `unauthorized` |

Setiap pasangan dibandingkan berdasarkan kode status dan isi JSON. Pasangan kelima dan ketujuh memakai header autentikasi mahasiswa melalui fixture `student_headers`. Pasangan keenam memakai muatan yang melanggar batas SKS sehingga aturan bisnis menolak rencana dengan HTTP 200 dan `is_valid` bernilai false pada kedua jalur.

Pasangan kedelapan sampai kedua belas membandingkan status, struktur kunci payload, dan kode error tanpa nilai dinamis seperti token atau kode pemulihan. Pasangan kedelapan dan kesembilan memanggil `limiter.reset()` serta memakai identifier unik supaya status email duplikat dan batas laju autentikasi tidak bocor antar tes. Pasangan kesepuluh memakai `student_headers` dengan kata sandi saat ini yang salah agar versi token sesi bersama tidak berubah. Pasangan kesebelas memakai `admin_headers` untuk respons sukses dan `student_headers` untuk penolakan 403. Pasangan kedua belas hanya mengecek penolakan 401 tanpa identitas.

## Cakupan amplop error

| Kode status | Pemicu yang dipakai | Kode error yang teramati | Isi `details` |
|-------------|---------------------|--------------------------|---------------|
| 400 | Rute probe yang melempar `HTTPException` 400 | `http_error` | Daftar kosong |
| 401 | `GET /api/v1/dashboard/me` tanpa autentikasi | `unauthorized` | Daftar kosong |
| 403 | `POST /api/v1/admin/courses` dengan peran mahasiswa | `forbidden` | Daftar kosong |
| 404 | `GET /api/v1/courses/ZZZ999` | `course_not_found` | Daftar kosong |
| 409 | `POST /api/v1/admin/courses` dengan kode `AGI101` | `duplicate_course_code` | Daftar kosong |
| 422 | `GET /api/v1/courses?per_page=0` | `validation_error` | Daftar berisi field `query.per_page` |
| 429 | Rute probe dengan pembatas laju satu permintaan per menit | `rate_limit_exceeded` | Daftar kosong |
| 500 | Rute probe yang melempar `RuntimeError` | `internal_server_error` | Daftar kosong |

Semua respons error di atas memiliki objek `error` pada tingkat teratas dengan `code` dan `message` berjenis string serta `details` berjenis daftar. Tidak ada respons yang memakai `text/plain`. Teks pengecualian internal dan jejak tumpukan tidak pernah muncul pada badan respons.

## Cakupan kegagalan validasi permintaan

Ketiga kasus berikut diuji pada `POST /api/v1/plans/validations` dan `POST /api/plan/validate`. Masing-masing menghasilkan HTTP 422 dengan `error.code` bernilai `validation_error` dan daftar `details` yang tidak kosong.

| Kasus | Field yang dilaporkan | Nilai yang melanggar skema |
|-------|-----------------------|----------------------------|
| Batas semester | `semester_saat_ini` | Nilai semester bukan bilangan bulat |
| Paritas semester | `plan.1.0.parity` | Nilai paritas di luar `odd` dan `even` |
| Batas SKS | `maks_sks_per_semester` | Nilai batas SKS bukan bilangan bulat |

## Catatan isolasi pengujian

Selama pengujian, `settings.CHATBOT_SERVICE_URL` diarahkan ke alamat lokal yang tidak aktif lalu dikembalikan setelah setiap tes. Hal ini membuat respons kesehatan dan pencarian tidak bergantung pada layanan eksternal. Rute probe untuk status 400, 429, dan 500 dipasang sementara dan daftar rute aplikasi dipulihkan di dalam blok `try` dan `finally`. Tidak ada perubahan permanen pada `backend/app.py`. Pasangan sprint 9 sengaja memakai jalur error—validasi, kode pemulihan salah, kata sandi salah, penolakan peran, dan tanpa autentikasi—sehingga tidak ada mutasi data maupun perubahan versi token yang bocor ke tes lain.
