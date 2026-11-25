# Periode akademik sebagai pasangan tahun ajaran dan term

Kalendar akademik FTMM memakai tahun ajaran `Y/Y+1` dengan dua periode tetap, Ganjil dan Genap. UI penjadwalan sebelumnya menampilkan `2026 ganjil` hanya untuk tiga periode, sehingga PJ Prodi tidak melihat urutan `2026/2027 Ganjil`, `2026/2027 Genap`, `2027/2028 Ganjil`, dan seterusnya. Keputusan ini menetapkan satu label kanonik dan jendela enam periode bergulir tanpa mengubah skema.

**Status:** accepted

## Keputusan

1. Satu baris `academic_periods` adalah kombinasi `academic_year_start` dan `term` (`ganjil` atau `genap`). Tepat satu periode berstatus aktif, ditentukan oleh `current_period()` di `backend/academics.py`.
2. Seeder membuat enam periode bergulir: tiga tahun ajaran terakhir, masing-masing Ganjil dan Genap. Hanya periode berjalan yang `is_active = true`.
3. Label kanonik UI penjadwalan adalah `YYYY/YYYY+1 Ganjil` atau `YYYY/YYYY+1 Genap`. Panel preferensi boleh menambahkan awalan `Semester N`, tetapi tahun ajaran dan term tetap tampil lengkap.
4. Urutan daftar periode memakai tahun ajaran menurun, lalu Ganjil sebelum Genap dalam tahun yang sama.
5. Seeder memperbarui `start_date`, `end_date`, dan `is_active` pada baris yang sudah ada. Periode lama tidak dihapus.

**Considered Options**: satu entitas per tahun ajaran tanpa term (ditolak: solver dan preferensi memakai term), hanya periode aktif (ditolak: perlu salin preferensi dan histori), label `2026 ganjil` (ditolak: tahun ajaran tidak lengkap), menambah kolom skema baru (ditolak: `academic_year_start` dan `term` sudah cukup).

**Consequences**: basis data yang sudah ada perlu menjalankan seeder ulang untuk mengisi enam periode; tidak ada migrasi skema. Semua panel penjadwalan memakai satu format label, dan daftar preferensi dapat disalin dari periode sebelumnya yang tetap tersedia dalam jendela tersebut.
