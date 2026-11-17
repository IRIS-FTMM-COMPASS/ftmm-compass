# 04: Deteksi bentrok dan alternatif kelas yang bisa diterapkan

**What to build:** Mahasiswa memilih section kelas untuk beberapa mata kuliah, melihat peringatan ketika ada bentrok jam, membandingkan dengan kelas paralel alternatif yang bebas bentrok, lalu menerapkan solusi langsung tanpa kembali ke katalog.

**Blocked by:** 03 — Jadwal kelas nyata tersedia di planner.

**Status:** ready-for-agent

- [ ] Endpoint validasi jadwal menerima periode akademik dan daftar pasangan mata kuliah–section, lalu mengembalikan daftar bentrok dan alternatif bebas bentrok dari database.
- [ ] Memilih dua section yang bertabrakan memunculkan banner peringatan yang menyebut nama mata kuliah dan rincian jam, dengan penanda teks dan warna.
- [ ] Panel alternatif menampilkan sedikitnya satu kelas paralel yang benar-benar bebas bentrok.
- [ ] Tombol "Terapkan Solusi" mengganti section terpilih dan grid jadwal diperbarui seketika tanpa memuat ulang halaman.
- [ ] Tidak ada error pada console browser selama alur resolusi bentrok.
- [ ] Test API membuktikan deteksi irisan jam dan penyaringan alternatif; seluruhnya lulus.
