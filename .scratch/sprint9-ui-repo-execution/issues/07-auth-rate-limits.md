# 07: Batas laju autentikasi

**What to build:** Penyerang tidak bisa menebak kata sandi atau membanjiri pendaftaran dan pemulihan akun. Batas yang terlampaui menghasilkan respons yang bisa dipahami klien.

**Blocked by:** 05 — Pemulihan dan ganti password dengan pencabutan sesi.

**Status:** ready-for-agent

**Sumber:** kartu Trello #160 — Mantra, high, due 23 Nov 2026.

- [ ] Permintaan login keenam dalam satu menit menghasilkan 429 dengan kode `rate_limited`.
- [ ] Permintaan registrasi dan pemulihan keempat dalam satu menit menghasilkan 429 dengan kode yang sama.
- [ ] Respons 429 membawa penjelasan kapan klien boleh mencoba lagi.
- [ ] Endpoint di luar autentikasi tidak terkena batas global.
- [ ] Pengujian batas laju lulus bersama seluruh rangkaian backend.
