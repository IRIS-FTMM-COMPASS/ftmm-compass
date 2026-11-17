# 04: Deteksi bentrok dan alternatif kelas yang bisa diterapkan

**What to build:** Mahasiswa memilih section kelas untuk beberapa mata kuliah, melihat peringatan ketika ada bentrok jam, membandingkan dengan kelas paralel alternatif yang bebas bentrok, lalu menerapkan solusi langsung tanpa kembali ke katalog.

**Blocked by:** 03 — Jadwal kelas nyata tersedia di planner.

**Status:** resolved

- [x] Endpoint validasi jadwal menerima periode akademik dan daftar pasangan mata kuliah–section, lalu mengembalikan daftar bentrok dan alternatif bebas bentrok dari database.
- [x] Memilih dua section yang bertabrakan memunculkan banner peringatan yang menyebut nama mata kuliah dan rincian jam, dengan penanda teks dan warna.
- [x] Panel alternatif menampilkan sedikitnya satu kelas paralel yang benar-benar bebas bentrok.
- [x] Tombol "Terapkan Solusi" mengganti section terpilih dan grid jadwal diperbarui seketika tanpa memuat ulang halaman.
- [x] Tidak ada error pada console browser selama alur resolusi bentrok.
- [x] Test API membuktikan deteksi irisan jam dan penyaringan alternatif; seluruhnya lulus.

## Comments

- Resolved 2026-11-17. `POST /class-sections/validations` mengembalikan pasangan bentrok dan alternatif; alternatif kini saling bebas bentrok saat diterapkan sekaligus, dengan regresi test dua alternatif bertabrakan. Banner memakai teks + warna dan tombol "Terapkan Solusi" memperbarui grid tanpa reload. Trello #138. Commit `5e51853`, `1e1a38f`.
