# QA Evidence — Kartu #157 (migrasi siklus akun)

Tanggal: 2026-11-18
Branch: `fix/sprint9-account-qa-hardening` (dari `upstream/main` `540fcb8`)
Aplikasi: Vite lokal `http://127.0.0.1:8443`, gateway Docker `127.0.0.1:8001`, PostgreSQL `127.0.0.1:5432`
Browser: Chromium headless 1280x900 (satu tab, sesi nyata melalui UI)

## Akun uji

Registrasi baru dengan email institusi pola `qa157.tester****-2026@ftmm.unair.ac.id`, NIM unik, angkatan 2026. Kata sandi dan kode pemulihan tidak ditulis ke berkas ini; kode pada screenshot ditutup dengan redaksi hitam.

## Backend dan migrasi

- `uv run --directory backend python -m pytest tests -q`: lulus (exit 0). PR #17 mencatat 166 tes lulus.
- `alembic current` pada DB dev: `f3c9d1a7b2e8 (head)`.
- DB scratch `qa157_migration_check` (dibuat dan dihapus dalam pengujian ini): `upgrade head` → `downgrade -1` → `upgrade head` → `seed.py` berhasil; head akhir `f3c9d1a7b2e8`. Seed terverifikasi sampai 8/8 langkah.

## Alur browser yang disubmit

1. **Registrasi**: formulir diisi dan disubmit. Respons "Pendaftaran Berhasil", kode pemulihan tampil sekali, tombol "Lanjut ke Dashboard" mengarah ke Dashboard dengan data akun baru. Bukti: `qa157-01-register-form.png`, `qa157-02-register-success-redacted.png`.
2. **Ganti password** dari Profile: kata sandi saat ini dan baru disubmit. Muncul "Kata sandi berhasil diperbarui"; token di localStorage berganti (token lama tidak lagi cocok dengan `token_version`). Bukti: `qa157-03-change-password-form.png`, `qa157-04-change-password-success.png`.
3. **Sesi dicabut → 401**: tab kedua diberi token lama + objek user yang masih valid sebagai precondition, lalu dimuat ulang. Network menunjukkan 401 pada `/api/v1/notifications/me`, `/api/v1/dashboard/me`, `/api/v1/me/course-records`, `/api/v1/polling/my-votes`, `/api/v1/academic-periods/current`, `/api/v1/degree-plans`; UI kembali ke layar login. Bukti: `qa157-05-stale-token-401.png`.
4. **Pemulihan**: logout lewat konfirmasi, buka "Lupa sandi?", masukkan kode pemulihan sekali pakai dan kata sandi baru, submit. Muncul "Kata sandi berhasil dipulihkan dan kode pemulihan diperbarui"; kode lama tidak berlaku. Bukti: `qa157-06-recover-form.png`, `qa157-07-recover-success-redacted.png`.
5. **Login dengan kata sandi hasil pemulihan**: berhasil masuk Dashboard dan formulir login hilang. Bukti: `qa157-08-login-after-recovery.png`.

## Batas pengujian

- Tidak ada test runner frontend di repo; bukti ini memakai submit formulir nyata, bukan automated frontend test.
- Endpoint admin/RBAC tidak dijalankan lewat browser karena tidak ada kredensial admin uji; cakupan berasal dari 24 tes `backend/tests/test_auth.py` dan tes parity `test_api_contract.py` (403 untuk student/lecturer).
- Firefox tidak tersedia pada alat browser; WebKit tidak dipakai pada putaran ini.
- Precondition 401 disiapkan dengan menulis token lama ke localStorage tab uji; respons 401 berasal dari gateway sungguhan, bukan stub atau manipulasi tampilan.

## Kesimpulan

Checklist #157 terpenuhi untuk cakupan yang tersedia: migrasi reversible, regresi backend lulus, dan alur akun kritis disubmit di browser dengan bukti screenshot. Celah yang masih terbuka (hardening JWT, kebijakan kata sandi, normalisasi email, kontrak rate limit) ditangani terpisah pada branch yang sama dan tidak termasuk klaim QA ini.

## Reconfirmasi hardening pada branch yang sama (2026-11-18)

- `JWT_SECRET_KEY` tanpa env kini dihasilkan random per proses; production wajib men-set env untuk token yang stabil lintas worker.
- Kebijakan kata sandi minimal 8 karakter berlaku untuk register, recover, dan ganti password. Tes backend menolak 422; di browser, validasi `minLength=8` menghentikan submit sebelum request dikirim. Bukti: `qa157-09-short-password-rejected.png`.
- Login mencocokkan email secara case-insensitive. Login dengan email uji huruf besar berhasil masuk Dashboard. Bukti: `qa157-10-uppercase-email-login.png`.
- `DEFAULT_RATE_LIMIT` default dikosongkan sehingga endpoint di luar autentikasi tidak terkena batas global; batas auth 5/menit login dan 3/menit register/recover tetap aktif.
- Kontrak dokumen login diselaraskan menjadi NIM/email; NIP tidak didukung model data saat ini.
- Tes `test_auth.py` dan `test_api_contract.py` lulus setelah perubahan.
