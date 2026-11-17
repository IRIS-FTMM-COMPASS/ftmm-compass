# 14: Reset state sesi React saat 401 dan expiry

**Trello:** #163 — https://trello.com/c/yItDsr7i/163-hans-reset-state-sesi-react-saat-401-dan-tangani-expiry-token
**Repo:** `ftmm-compass-ui/src`
**Owner:** Hans
**Labels:** high, EPIC 3 — Core Application, Hans
**Due:** 2026-11-23
**Status:** ready-for-agent

**What to build:** Satukan penanganan 401 antara `apiFetch` dan `SessionProvider`. Beri tahu provider agar `user` dan `isLoggedIn` ikut ter-reset saat `clearSession()` dipanggil, lalu catat `expires_in` untuk logout otomatis sebelum kedaluwarsa.

**Blocked by:** None. Merupakan prasyarat tiket 13.

- [ ] 401 dari Dashboard, Planner, atau Chatbot langsung menampilkan form login tanpa reload manual.
- [ ] Tidak ada elemen yang tetap menampilkan data user lama setelah sesi dihapus atau token dicabut dari database.
- [ ] `expires_in` dari respons login dipakai untuk menjadwalkan logout sebelum token kedaluwarsa.
- [ ] Alur diuji di browser desktop dan mobile; `pnpm --silent build -- --logLevel warn` lulus.
