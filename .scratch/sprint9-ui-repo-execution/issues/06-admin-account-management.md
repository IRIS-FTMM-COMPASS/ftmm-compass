# 06: Manajemen akun admin dan RBAC

**What to build:** Admin dapat mengelola akun dari antarmuka: mencari, memfilter, mengaktifkan, menonaktifkan, membuat akun staf, dan mereset password. Mahasiswa tidak melihat menu tersebut dan ditolak bila mencoba akses langsung.

**Blocked by:** 05 — Pemulihan dan ganti password dengan pencabutan sesi.

**Status:** ready-for-agent

**Sumber:** kartu Trello #155 dan #156 — Mantra dan Hans, high, due 23 Nov 2026.

- [ ] Halaman manajemen akun hanya tersedia untuk peran admin dan tidak muncul di navigasi mahasiswa.
- [ ] Daftar akun mendukung pencarian dan filter peran serta status, dengan pagination yang sesuai jumlah data.
- [ ] Aktivasi, nonaktifasi, dan pembuatan akun staf berubah langsung pada daftar.
- [ ] Reset oleh admin menampilkan kata sandi sementara sekali dan mencabut sesi akun yang bersangkutan.
- [ ] Setiap endpoint manajemen akun mengembalikan 403 untuk token mahasiswa dan 200 atau 201 untuk admin.
