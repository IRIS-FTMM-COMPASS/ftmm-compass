# 05: Tautan jadwal tetap terbawa lintas halaman

**What to build:** Sebagai mahasiswa, ketika saya menyalin tautan jadwal yang dibagikan, tautan itu tetap membawa jadwalnya setelah saya refresh atau berpindah ke menu lain dan kembali. Kalau saya menutup jadwal bagikan itu, yang hilang hanya penanda jadwalnya; halaman tempat saya berada tidak ikut berubah.

**Blocked by:** 01 — URL sebagai identitas halaman aktif.

**Status:** implemented — GitHub #45 (closed), PR #46

- [ ] Menyalin tautan jadwal dari halaman jadwal menghasilkan URL dengan penanda `#timetable=` pada path halaman aktif.
- [ ] Refresh tautan tersebut masih menerapkan jadwal yang dibagikan.
- [ ] Berpindah ke menu lain dan kembali membuat penanda jadwal tetap terbawa di address bar.
- [ ] Tombol untuk menutup jadwal bagikan menghapus hanya penanda jadwal; path halaman tidak berubah.
- [ ] Perpindahan menu tidak menghapus query string yang sedang dipakai halaman.
