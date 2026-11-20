# 03: Riwayat bersih saat sesi berubah

**What to build:** Sebagai pengguna, ketika saya logout, sesi saya habis, atau respons 401 terjadi, saya mendarat di Dashboard dengan riwayat browser yang sudah dibersihkan. Tombol Back tidak membawa saya kembali ke halaman yang sudah tidak boleh saya buka. Kalau saya membuka tautan langsung tanpa sesi, saya melihat Login terlebih dahulu, lalu masuk tetap dimulai dari Dashboard.

**Blocked by:** 01 — URL sebagai identitas halaman aktif.

**Status:** implemented — GitHub #43 (closed), PR #46

- [ ] Logout dari halaman mana pun menghasilkan Dashboard di address bar, dan tombol Back tidak kembali ke halaman sebelum logout.
- [ ] Sesi habis atau respons 401 saat berada di halaman terlindungi menghasilkan Dashboard tanpa menyisakan entri riwayat lama.
- [ ] Membuka deep link tanpa token/user tersimpan menampilkan Login, bukan konten halaman yang diminta.
- [ ] Login berhasil selalu membuka Dashboard, termasuk ketika proses diawali dari deep link.
- [ ] Perilaku Back setelah login tidak mengembalikan pengguna ke halaman yang diminta sebelum login.
