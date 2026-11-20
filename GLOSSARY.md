# FTMM Compass

Glosarium untuk kosakata proses kerja proyek FTMM Compass yang tidak berarti sama dengan istilah umum rekayasa perangkat lunak.

## Language

**Kartu Trello**:
Unit perencanaan sprint pada board `FTMM COMPASS`; pemiliknya adalah anggota tim dan bukti penyelesaiannya dicatat sebagai komentar pada kartu tersebut.
_Avoid_: tiket, isu, task agen

**Tiket kerja**:
Berkas isu lokal di `.scratch/<slug>/issues/` yang diturunkan dari satu kartu Trello dan menjadi unit eksekusi agen.
_Avoid_: kartu, task Trello, isu eksternal

## Polling & Ketersediaan MK

**PJ Prodi**:
Dosen penanggung jawab satu program studi yang berwenang melihat rekap peminatan prodinya dan menentukan ketersediaan mata kuliah prodi untuk semester berikutnya. Tepat satu PJ berlaku untuk setiap prodi.
_Avoid_: kaprodi, koordinator dosen, dosen biasa, PJ dosen

**Rekap Peminatan**:
Agregat jumlah peminat per mata kuliah pilihan pada satu periode polling, tanpa identitas mahasiswa pemilih.
_Avoid_: wishlist dosen, daftar pemilih, rekap voting per mahasiswa

**MK Terkunci**:
Mata kuliah yang tetap tampil di katalog tetapi tidak dapat divote karena paritas semester tidak sesuai atau dinonaktifkan oleh PJ Prodi.
_Avoid_: MK dihapus, MK tersembunyi

## Penjadwalan Kelas

**Kelas MK**:
Satu kelas dari mata kuliah yang ditawarkan satu prodi pada satu periode akademik, dengan kuota pesertanya sendiri. Satu mata kuliah dapat memiliki satu sampai tiga kelas; kelas adalah unit penempatan jadwal.
_Avoid_: section, kelas fisik, kuota mingguan

**PJ MK**:
Dosen penanggung jawab satu atau lebih mata kuliah; jabatannya adalah relasi pada mata kuliah, berbeda dari PJ Prodi dan dari tim pengajar.
_Avoid_: dosen pengampu, PJ dosen, koordinator matkul

**Tim Pengajar**:
Dosen yang mengajar pada satu atau lebih Kelas MK; dapat sekaligus menjadi PJ MK pada mata kuliah lain.
_Avoid_: dosen pengajar, pengampu, dosen PJMK

## Manajemen Akun

**Akun nonaktif**:
Akun yang akses masuk dan sesinya dicabut oleh admin, tetapi data dan riwayat akademiknya tetap tersimpan.
_Avoid_: akun diblokir, akun dihapus

**Akun dianonimisasi**:
Akun yang data pribadinya dihapus permanen oleh admin, sedangkan riwayat akademiknya tetap melekat pada identitas lama dan tidak dipindahkan ke akun baru.
_Avoid_: hard delete, akun dihapus permanen

**Data identitas akademik terkunci**:
Identitas akademik mahasiswa — program studi, angkatan, NIM, dan semester aktif — yang tidak dapat diubah sendiri; hanya admin FTMM Compass yang dapat mengubahnya.
_Avoid_: data read-only, data Cybercampus

**Jejak wewenang admin**:
Catatan permanen atas tindakan admin pada akun, berisi pelaku, waktu, target, field yang berubah, alasan, dan nilai sebelum serta sesudah.
_Avoid_: log aktivitas pengguna, audit log umum
