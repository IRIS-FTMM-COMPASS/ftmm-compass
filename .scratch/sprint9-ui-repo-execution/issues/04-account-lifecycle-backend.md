# 04: Backend dan migrasi siklus akun mandiri

**Trello:** #155 — https://trello.com/c/SjQgzbSj/155-mantra-backend-migrasi-siklus-akun-mandiri-register-ganti-reset-password-admin-users
**Repo:** `ftmm-compass-ui/backend`
**Owner:** Mantra
**Labels:** high, EPIC 3 — Core Application, Mantra
**Due:** 2026-11-23
**Status:** ready-for-agent

**What to build:** Tambah registrasi mahasiswa, ganti password, reset dengan kode pemulihan, dan manajemen akun admin di `backend/api/auth.py` serta router baru `backend/api/admin_users.py`, dengan migrasi Alembic idempoten dari `down_revision = "c4d2e6f8a1b3"`.

**Blocked by:** Tiket 02 untuk keputusan kredensial seeder.

- [ ] `POST /auth/register` dengan email `@ftmm.unair.ac.id` mengembalikan 201 `{access_token, user, recovery_code}`; semester angkatan 2023 pada periode 2026 ganjil = 7; kode hanya tampil sekali.
- [ ] Email salah domain, tahun di luar 2000..tahun berjalan, email/NIM duplikat berturut-turut menghasilkan 422 `validation_error`, 409 `email_taken`, 409 `nim_taken`.
- [ ] Login menerima NIM, email, dan `institutional_id` 18 digit; `expires_in = 28800`; `GET /auth/me` tidak lagi memuat NIM/NIP hardcode.
- [ ] Ganti password → 204 dan token lama ditolak; reset dengan kode salah → 401 `invalid_recovery_code`; reset benar merotasi kode.
- [ ] `GET/POST/PATCH /admin/users` dan `/admin/users/{id}/password-reset` hanya untuk role admin; mahasiswa menerima 403.
- [ ] `alembic upgrade head` dan `downgrade -1` sukses pada DB bersih maupun ter-seed, tanpa kolom sisa.
