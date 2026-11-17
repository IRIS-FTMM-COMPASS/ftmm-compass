# 08: Persistensi draf rencana terverifikasi lintas sesi

**What to build:** Mahasiswa mengubah rencana studinya, melihat status penyimpanan yang benar-benar mengikuti request jaringan, dan menemukan rencana yang sama saat membuka aplikasi dari browser atau perangkat lain. Kegagalan simpan tidak menyembunyikan masalah.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] Perubahan rencana tersimpan di server dan indikator status berubah sesuai request yang sedang berjalan.
- [x] Memuat ulang halaman atau membuka aplikasi dari sesi lain menampilkan susunan mata kuliah yang sama.
- [x] Saat simpan gagal, antarmuka menampilkan pesan kesalahan dan tombol coba lagi yang berhasil.
- [x] Kontrak resource kanonik untuk rencana studi tetap dipertahankan; tidak ada penggantian nama endpoint.
- [x] Tidak ada mekanisme draf berbasis penyimpanan lokal browser yang dikembalikan.

## Comments

- Resolved 2026-11-17. Status simpan mengikuti PUT nyata lewat state machine, retry tersedia, dialog konfirmasi muncul saat draf lokal berbeda dari server. Kontrak `degree-plans` + `items` tidak berubah; tanpa localStorage. 12 assertion state machine lulus; build dan QA browser bersih. Trello #137 dan #89. Commit `0555192`, `421226d`.
