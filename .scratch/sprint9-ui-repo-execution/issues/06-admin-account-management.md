# 06: Manajemen akun admin dan RBAC

**What to build:** Admin dapat mengelola akun dari antarmuka: mencari, memfilter, mengaktifkan, menonaktifkan, membuat akun staf, dan mereset password. Mahasiswa tidak melihat menu tersebut dan ditolak bila mencoba akses langsung.

**Blocked by:** 05 — Pemulihan dan ganti password dengan pencabutan sesi.

**Status:** resolved

**Sumber:** kartu Trello #155 dan #156 — Mantra dan Hans, high, due 23 Nov 2026.

- [x] Halaman manajemen akun hanya tersedia untuk peran admin dan tidak muncul di navigasi mahasiswa.
- [x] Daftar akun mendukung pencarian dan filter peran serta status, dengan pagination yang sesuai jumlah data.
- [x] Aktivasi, nonaktifasi, dan pembuatan akun staf berubah langsung pada daftar.
- [x] Reset oleh admin menampilkan kata sandi sementara sekali dan mencabut sesi akun yang bersangkutan.
- [x] Setiap endpoint manajemen akun mengembalikan 403 untuk token mahasiswa dan 200 atau 201 untuk admin.

## Comments

- Resolved 2026-11-17. admin-only account list/create/update/reset endpoints and UI with search, filters, pagination and RBAC; student tokens get 403; tests pass.
