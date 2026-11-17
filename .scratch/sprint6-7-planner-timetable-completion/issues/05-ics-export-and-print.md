# 05: Ekspor `.ics` dan cetak PDF dari jadwal yang sebenarnya

**What to build:** Mahasiswa mengunduh jadwal mingguannya sebagai berkas kalender yang bisa dipakai di ponsel, dan mencetak atau menyimpan jadwal sebagai PDF. Berkas yang dihasilkan berasal dari jadwal yang sama dengan yang tampil di planner.

**Blocked by:** 03 — Jadwal kelas nyata tersedia di planner.

**Status:** resolved

- [x] Tombol ekspor menghasilkan berkas `.ics` dengan minimal satu event, aturan pengulangan mingguan, serta nama mata kuliah dan jam yang sesuai section dari database.
- [x] Tombol cetak menghasilkan tampilan grid A4 landscape tanpa elemen navigasi.
- [x] Saat belum ada jadwal, tombol ekspor menampilkan pesan yang dapat ditindaklanjuti, bukan kegagalan diam-diam.
- [x] Verifikasi browser headless mengamati unduhan berkas dan isinya sesuai jadwal yang tampil di layar.

## Comments

- Resolved 2026-11-17. Ekspor kini mengembalikan hasil terstruktur dan menampilkan pesan aksi saat jadwal/periode kosong; `DTEND` diperbaiki untuk menit bukan kelipatan 60. Unduhan browser `jadwal-kuliah-ftmm-sem3.ics`: 3 event, `RRULE:FREQ=WEEKLY;COUNT=16`, DTSTART/DTEND 08:00–10:30, 13:00–15:30, 13:00–14:40. Cetak A4 landscape memakai stylesheet existing. Trello #88. Commit `0038eba`.
