# 13: UI siklus akun mandiri dan manajemen akun admin

**Trello:** #156 — https://trello.com/c/jmwAHR3H/156-hans-frontend-akun-mandiri-registrasi-ganti-password-manajemen-akun-admin
**Repo:** `ftmm-compass-ui/src`
**Owner:** Hans
**Labels:** high, EPIC 3 — Core Application, Hans
**Due:** 2026-11-23
**Status:** ready-for-agent

**What to build:** Tambah `RegisterPage`, alur kode pemulihan, panel ganti password di `ProfilePage`, dan `AccountManagementPage` khusus admin. Hubungkan tautan login yang masih mati, hapus badge statis, dan tampilkan `institutional_id`.

**Blocked by:** Tiket 04 untuk kontrak endpoint; tiket 14 untuk penanganan 401.

- [ ] Registrasi dengan email institusi valid langsung masuk Dashboard; kode pemulihan tampil sekali dan bisa disalin atau diunduh.
- [ ] Email salah domain atau tahun di luar rentang menampilkan error pada field email tanpa request sukses; kode `email_taken`, `nim_taken`, `invalid_recovery_code` diterjemahkan ke pesan Indonesia yang spesifik.
- [ ] Reset password dengan kode benar berhasil login dengan password baru; ganti password dari Profile menjaga sesi tetap aktif.
- [ ] Menu Manajemen Akun hanya muncul untuk `admin`; aksi aktivasi, nonaktif, reset, dan buat akun staf berfungsi dengan `temporary_password` sekali tampil.
- [ ] Modal wajib ganti password muncul saat `must_change_password = true` dan memblokir navigasi sampai selesai; `pnpm --silent build -- --logLevel warn` lulus.
