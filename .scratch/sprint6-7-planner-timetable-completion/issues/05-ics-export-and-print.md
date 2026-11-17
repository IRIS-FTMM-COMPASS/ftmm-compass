# 05: Ekspor `.ics` dan cetak PDF dari jadwal yang sebenarnya

**What to build:** Mahasiswa mengunduh jadwal mingguannya sebagai berkas kalender yang bisa dipakai di ponsel, dan mencetak atau menyimpan jadwal sebagai PDF. Berkas yang dihasilkan berasal dari jadwal yang sama dengan yang tampil di planner.

**Blocked by:** 03 — Jadwal kelas nyata tersedia di planner.

**Status:** ready-for-agent

- [ ] Tombol ekspor menghasilkan berkas `.ics` dengan minimal satu event, aturan pengulangan mingguan, serta nama mata kuliah dan jam yang sesuai section dari database.
- [ ] Tombol cetak menghasilkan tampilan grid A4 landscape tanpa elemen navigasi.
- [ ] Saat belum ada jadwal, tombol ekspor menampilkan pesan yang dapat ditindaklanjuti, bukan kegagalan diam-diam.
- [ ] Verifikasi browser headless mengamati unduhan berkas dan isinya sesuai jadwal yang tampil di layar.
