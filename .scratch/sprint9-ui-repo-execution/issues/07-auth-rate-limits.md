# 07: Batas laju autentikasi

**What to build:** Penyerang tidak bisa menebak kata sandi atau membanjiri pendaftaran dan pemulihan akun. Batas yang terlampaui menghasilkan respons yang bisa dipahami klien.

**Blocked by:** 05 — Pemulihan dan ganti password dengan pencabutan sesi.

**Status:** resolved

**Sumber:** kartu Trello #160 — Mantra, high, due 23 Nov 2026.

- [x] Permintaan login keenam dalam satu menit menghasilkan 429 dengan kode `rate_limited`.
- [x] Permintaan registrasi dan pemulihan keempat dalam satu menit menghasilkan 429 dengan kode yang sama.
- [x] Respons 429 membawa penjelasan kapan klien boleh mencoba lagi.
- [x] Endpoint di luar autentikasi tidak terkena batas global.
- [x] Pengujian batas laju lulus bersama seluruh rangkaian backend.

## Comments

- Resolved 2026-11-17. login 5/minute, register and recover 3/minute, 429 code rate_limited with Retry-After; other endpoints unaffected; tests pass.
