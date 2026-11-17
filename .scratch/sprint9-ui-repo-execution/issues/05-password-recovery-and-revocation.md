# 05: Pemulihan dan ganti password dengan pencabutan sesi

**What to build:** Mahasiswa dapat memulihkan akun dengan kode pemulihan dan mengganti password sendiri. Setelah password berubah, sesi lama tidak lagi bisa dipakai.

**Blocked by:** 04 — Registrasi mahasiswa dari awal sampai Dashboard.

**Status:** resolved

**Sumber:** kartu Trello #155, #156, #159 — Mantra dan Hans, high, due 23 Nov 2026.

- [x] Reset dengan kode benar mengganti password, merotasi kode, dan mengizinkan login dengan password baru.
- [x] Kode pemulihan salah menghasilkan pesan yang jelas tanpa mengubah akun.
- [x] Ganti password dari profil berhasil dan sesi aktif tetap berlangsung.
- [x] Token yang diterbitkan sebelum perubahan password ditolak dengan 401; token setelahnya tetap diterima.
- [x] Migrasi penambahan kolom dapat dinaikkan dan diturunkan tanpa menyisakan kolom.

## Comments

- Resolved 2026-11-17. recovery rotates code, change-password returns fresh token and revokes older ones via users.token_version; reversible migration f3c9d1a7b2e8 verified down and up; tests pass.
