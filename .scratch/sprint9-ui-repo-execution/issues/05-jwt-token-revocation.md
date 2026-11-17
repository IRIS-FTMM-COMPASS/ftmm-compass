# 05: Cabut token lama saat password berubah

**Trello:** #159 — https://trello.com/c/Xk4QWCfN/159-mantra-cabut-token-lama-saat-password-berubah-jwt-tokenversion
**Repo:** `ftmm-compass-ui/backend`
**Owner:** Mantra
**Labels:** high, EPIC 3 — Core Application, Mantra
**Due:** 2026-11-23
**Status:** ready-for-agent

**What to build:** Tambah kolom `users.token_version` lewat migrasi reversible, sertakan klaim versi di `create_access_token`, dan tolak token di `get_current_user` bila versinya berbeda. Naikkan versi pada handler ganti password, reset, dan reset oleh admin.

**Blocked by:** Tiket 04.

- [ ] Migrasi `upgrade head` lalu `downgrade -1` berhasil dan tidak menyisakan kolom pada `users`.
- [ ] Token sebelum ganti password → `GET /api/v1/auth/me` 401; token sesudahnya → 200.
- [ ] Reset password pengguna dan reset oleh admin sama-sama mencabut sesi lama target.
- [ ] `backend/tests/test_auth.py` memuat kasus old-token-401, new-token-200, dan admin-reset-401.
