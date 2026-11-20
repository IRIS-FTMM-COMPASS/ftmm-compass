# 02: Deep link per halaman dan peran

**What to build:** Sebagai mahasiswa, PJ Prodi, atau admin, saya bisa membuka tautan langsung ke sebuah halaman di tab baru dan langsung mendapat halaman itu selama peran saya berwenang. Kalau saya mengetik alamat halaman yang bukan wewenang saya, saya dialihkan ke Dashboard, bukan disuguhi area kosong atau halaman terlindungi.

**Blocked by:** 01 — URL sebagai identitas halaman aktif.

**Status:** implemented — GitHub #42 (closed), PR #46

- [ ] Membuka `/dashboard`, `/course-finder`, `/degree-planner`, `/chatbot`, `/profile`, `/pj-courses`, dan `/admin-accounts` di tab baru menampilkan halaman yang bersangkutan untuk peran yang berwenang.
- [ ] Student dapat membuka Degree Planner, Course Finder, Compass AI, Profil Pengguna, dan Dashboard langsung dari URL.
- [ ] Lecturer dapat membuka Rekap & Kelola MK dan Course Finder langsung dari URL; membuka Degree Planner atau Compass AI mengalihkan ke Dashboard.
- [ ] Student atau admin yang membuka Rekap & Kelola MK dialihkan ke Dashboard dan tidak melihat area konten kosong.
- [ ] Admin dapat membuka Manajemen Akun; student dan lecturer yang membukanya dialihkan ke Dashboard.
- [ ] PJ Prodi tetap memakai wewenang lecturer untuk Rekap & Kelola MK; tidak ada peran baru yang diperkenalkan.
- [ ] Status dan judul halaman hasil alias `/` serta path tak dikenal konsisten dengan aturan di tiket 01.
