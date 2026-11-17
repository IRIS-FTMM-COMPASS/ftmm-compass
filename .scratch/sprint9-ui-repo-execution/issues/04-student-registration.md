# 04: Registrasi mahasiswa dari awal sampai Dashboard

**What to build:** Mahasiswa mendaftar dengan email institusi yang valid, langsung masuk ke Dashboard tanpa login ulang, dan menerima kode pemulihan yang ditampilkan tepat satu kali.

**Blocked by:** 01 — Katalog resmi tanpa data demo.

**Status:** resolved

**Sumber:** kartu Trello #155 dan #156 — Mantra dan Hans, high, due 23 Nov 2026.

- [x] Registrasi dengan email institusi yang valid menghasilkan akun, profil mahasiswa, dan sesi aktif di Dashboard.
- [x] Semester berjalan diturunkan dari tahun angkatan dan periode akademik aktif, lalu dibatasi pada rentang yang didukung.
- [x] Kode pemulihan hanya tampil sekali dan dapat disalin atau diunduh.
- [x] Email domain salah, tahun di luar rentang, serta duplikasi email atau NIM menghasilkan pesan yang menunjuk field yang bermasalah.
- [x] Tautan daftar akun pada layar login berfungsi dan seluruh pengujian autentikasi lulus.

## Comments

- Resolved 2026-11-17. POST /api/v1/auth/register creates account, profile and session with one-time recovery code; frontend registration form opens from login and lands on Dashboard; tests in tests/test_auth.py pass.
