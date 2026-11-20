# 04: Menu sidebar sebagai tautan asli

**What to build:** Sebagai pengguna, saya ingin item menu di sidebar dan blok identitas profil benar-benar berupa tautan. Klik kiri tetap terasa seperti berpindah halaman di dalam aplikasi tanpa reload, tetapi Ctrl+click atau middle-click membuka tab baru tepat di halaman yang saya maksud, sehingga saya bisa membuka dua modul sekaligus.

**Blocked by:** 01 — URL sebagai identitas halaman aktif.

**Status:** implemented — GitHub #44 (closed), PR #46

- [ ] Ctrl+click pada item sidebar membuka tab baru dengan path halaman tersebut.
- [ ] Middle-click pada item sidebar membuka tab baru dengan path halaman tersebut.
- [ ] Klik kiri biasa pada item sidebar tetap berpindah halaman tanpa reload penuh dan tanpa kehilangan sesi.
- [ ] Blok identitas profil dapat dibuka di tab baru menuju Profil Pengguna.
- [ ] Tombol akses cepat di dalam halaman tetap berperilaku sebagai tombol, bukan tautan baru.
- [ ] Highlight menu aktif dan judul header tetap benar setelah navigasi dengan klik kiri maupun setelah tab baru dibuka.
