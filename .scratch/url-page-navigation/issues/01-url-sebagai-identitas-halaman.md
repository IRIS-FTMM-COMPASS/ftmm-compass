# 01: URL sebagai identitas halaman aktif

**What to build:** Sebagai pengguna FTMM Compass, setiap kali saya memilih menu, halaman yang saya lihat tercermin di address bar. Kalau saya refresh, saya tetap berada di halaman itu; kalau saya menekan Back atau Forward, browser membawa saya ke halaman yang sesuai, bukan hanya mengubah teks URL. Halaman awal `/` tetap membuka Dashboard, sedangkan alamat yang tidak dikenal dibersihkan ke Dashboard.

**Blocked by:** None (can start immediately).

**Status:** implemented — GitHub #41 (closed), PR #46

- [ ] Klik setiap item menu sidebar mengubah path di address bar ke slug halaman yang sesuai tanpa reload penuh.
- [ ] Refresh pada setiap halaman — Dashboard, Course Finder, Rekap & Kelola MK, Degree Planner, Compass AI, Profil Pengguna, dan Manajemen Akun — menampilkan halaman yang sama persis sebelum refresh.
- [ ] Setelah tiga kali perpindahan menu, tombol Back dan Forward memindahkan halaman dan URL secara sinkron.
- [ ] Membuka `/` menampilkan Dashboard; path di luar daftar halaman diganti menjadi `/dashboard` di address bar.
- [ ] Judul header dan highlight menu aktif selalu sesuai dengan halaman setelah refresh, Back, atau Forward.
- [ ] Error boundary halaman di-reset saat halaman aktif berubah.
- [ ] Dokumentasi alur navigasi menyatakan URL sebagai identitas halaman, bukan state semata.
