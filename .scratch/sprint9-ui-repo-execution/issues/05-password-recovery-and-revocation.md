# 05: Pemulihan dan ganti password dengan pencabutan sesi

**What to build:** Mahasiswa dapat memulihkan akun dengan kode pemulihan dan mengganti password sendiri. Setelah password berubah, sesi lama tidak lagi bisa dipakai.

**Blocked by:** 04 — Registrasi mahasiswa dari awal sampai Dashboard.

**Status:** ready-for-agent

**Sumber:** kartu Trello #155, #156, #159 — Mantra dan Hans, high, due 23 Nov 2026.

- [ ] Reset dengan kode benar mengganti password, merotasi kode, dan mengizinkan login dengan password baru.
- [ ] Kode pemulihan salah menghasilkan pesan yang jelas tanpa mengubah akun.
- [ ] Ganti password dari profil berhasil dan sesi aktif tetap berlangsung.
- [ ] Token yang diterbitkan sebelum perubahan password ditolak dengan 401; token setelahnya tetap diterima.
- [ ] Migrasi penambahan kolom dapat dinaikkan dan diturunkan tanpa menyisakan kolom.
