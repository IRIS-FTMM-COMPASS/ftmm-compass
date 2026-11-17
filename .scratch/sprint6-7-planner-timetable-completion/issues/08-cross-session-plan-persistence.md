# 08: Persistensi draf rencana terverifikasi lintas sesi

**What to build:** Mahasiswa mengubah rencana studinya, melihat status penyimpanan yang benar-benar mengikuti request jaringan, dan menemukan rencana yang sama saat membuka aplikasi dari browser atau perangkat lain. Kegagalan simpan tidak menyembunyikan masalah.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Perubahan rencana tersimpan di server dan indikator status berubah sesuai request yang sedang berjalan.
- [ ] Memuat ulang halaman atau membuka aplikasi dari sesi lain menampilkan susunan mata kuliah yang sama.
- [ ] Saat simpan gagal, antarmuka menampilkan pesan kesalahan dan tombol coba lagi yang berhasil.
- [ ] Kontrak resource kanonik untuk rencana studi tetap dipertahankan; tidak ada penggantian nama endpoint.
- [ ] Tidak ada mekanisme draf berbasis penyimpanan lokal browser yang dikembalikan.
