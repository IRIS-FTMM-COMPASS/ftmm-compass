# 08: Sesi kedaluwarsa kembali ke login

**What to build:** Ketika token kedaluwarsa atau dicabut, pengguna langsung kembali ke layar login dari halaman mana pun. Tidak ada tombol atau data lama yang tetap tampak sampai halaman dimuat ulang.

**Blocked by:** 05 — Pemulihan dan ganti password dengan pencabutan sesi.

**Status:** resolved

**Sumber:** kartu Trello #163 — Hans, high, due 23 Nov 2026.

- [x] Respon 401 dari Dashboard, Degree Planner, atau Chatbot menampilkan form login tanpa reload manual.
- [x] State sesi React ikut kosong ketika token dihapus, sehingga data pengguna lama hilang dari layar.
- [x] Masa berlaku token dari respons login dipakai untuk mengakhiri sesi sebelum kedaluwarsa.
- [x] Alur diuji pada tampilan desktop dan mobile.
- [x] Build produksi berhasil tanpa peringatan baru.

## Comments

- Resolved 2026-11-17. frontend session clears on any 401 via global fetch wrapper, uses login expires_in for proactive expiry, admin nav guarded; pnpm build succeeds.
