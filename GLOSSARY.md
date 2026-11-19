# FTMM Compass

Glosarium untuk kosakata proses kerja proyek FTMM Compass yang tidak berarti sama dengan istilah umum rekayasa perangkat lunak.

## Language

**Kartu Trello**:
Unit perencanaan sprint pada board `FTMM COMPASS`; pemiliknya adalah anggota tim dan bukti penyelesaiannya dicatat sebagai komentar pada kartu tersebut.
_Avoid_: tiket, isu, task agen

**Tiket kerja**:
Berkas isu lokal di `.scratch/<slug>/issues/` yang diturunkan dari satu kartu Trello dan menjadi unit eksekusi agen.
_Avoid_: kartu, task Trello, isu eksternal

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
