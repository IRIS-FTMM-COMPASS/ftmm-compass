# UI Conventions

Aturan UI yang mengikat untuk perubahan di `ftmm-compass-ui`.

## Pemilihan data panjang

- Daftar pilihan dengan lebih dari ~10 opsi **WAJIB** memakai `SearchableCombobox` (`src/shared/ui/SearchableCombobox.tsx`): pengguna bisa mengetik untuk menyaring lalu memilih.
- Contoh: mata kuliah pada form PJMK, akun dosen pada tim pengajar, dosen pada Ketersediaan Dosen, program studi pada form ruangan.
- Native `<select>` hanya untuk daftar pendek dan tetap: hari, jam, status aktif/nonaktif.
- Alasan: katalog mata kuliah dan daftar dosen panjang; native select memaksa scroll tanpa pencarian dan tidak ramah keyboard untuk data besar.

## Lebar tabel

- Tabel data memakai `table-layout: fixed` dengan `colgroup` lebar eksplisit dan sel `truncate`, supaya lebar kolom tidak bergeser saat halaman, sort, atau isi baris berubah.
- Tabel yang lebih lebar dari viewport memakai pembungkus `overflow-x-auto` dengan `min-w` pada tabel; kolom tidak boleh mengubah lebar saat data berganti.

## Warna prodi

- Warna prodi berasal dari token `@theme` (`--color-prodi-*`) dan dirender lewat `ProdiBadge`/`prodiTone`, bukan hex langsung di TSX.
- Status bentrok tetap memakai warna danger/orange; warna prodi hanya untuk identitas, bukan status.
