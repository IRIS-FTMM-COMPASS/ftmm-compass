# 17: QA dan review siklus akun mandiri

**Trello:** #157 — https://trello.com/c/mFj5gwZe/157-darryl-qa-review-migrasi-siklus-akun-register-password-rbac-rate-limit
**Repo:** `ftmm-compass-ui/backend`, `ftmm-compass-ui/src`
**Owner:** Darryl
**Labels:** high, EPIC 4 — Integration & Refinement, Darryl
**Due:** 2026-11-23
**Status:** ready-for-agent

**What to build:** Verifikasi independen migrasi dan seluruh alur akun: registrasi, derivasi semester, ganti dan reset password, RBAC admin, rate limit, serta pencabutan token. Bukti harus bisa dijalankan ulang, bukan pembacaan kode.

**Blocked by:** Tiket 04, 05, 06, dan 13.

- [ ] `upgrade → downgrade → upgrade` sukses pada DB bersih dan DB ter-seed; tidak ada kolom sisa pada `users`.
- [ ] Kasus baru pytest mencakup register valid/salah domain/tahun di luar rentang/duplikat, login NIM/NIP/email, `must_change_password`, token lama 401, reset benar/salah, RBAC 403, paginasi admin, dan 429 pada login ke-6.
- [ ] Regression penuh lulus; test lama yang berubah kontrak diperbarui, bukan dihapus.
- [ ] Smoke browser mencakup register, kode pemulihan, reset, ganti password, aktivasi/nonaktif admin, dan 401 saat token dicabut.
- [ ] Bukti berupa output pytest ringkas, contoh `curl` dengan status dan body, serta screenshot terlampir pada kartu Trello setelah implementasi disetujui.
