# Preferensi dosen dan assignment pengajar per periode akademik

Ketersediaan dosen sebelumnya menjadi syarat wajib yang bersifat global, pemetaan pengajar belum terikat periode, dan solver memperlakukan seluruh Tim Pengajar sebagai pengajar setiap Kelas MK. Model itu membuat dosen harus menjamin jam yang belum tentu diketahui, PJ Prodi mengelola detail berulang, dan kelas paralel berisiko memperlakukan semua dosen sebagai co-teacher. Keputusan ini memisahkan preferensi lunak dari blok tidak tersedia, mengikat pemetaan dan preferensi pada periode akademik, serta menetapkan satu Assignment Pengajar untuk setiap Kelas MK.

**Status:** accepted (amended 2026-11-25)

## Keputusan

1. **Preferensi dosen per periode**
   - Dosen mengisi Jam Preferensi dan Blok Tidak Tersedia untuk satu periode akademik, dengan opsi menyalin preferensi periode sebelumnya.
   - Jam Preferensi merupakan prioritas lunak. Blok Tidak Tersedia merupakan larangan keras dan bersifat opsional.
   - Preferensi kosong tidak memblokir solver, tetapi status kelengkapan tetap ditandai.
   - Hanya dosen yang mengedit preferensinya sendiri. PJ Prodi dan admin hanya membaca.
   - PJ Prodi atau admin menetapkan Deadline Preferensi. Setelah jadwal final, preferensi terkunci sampai proses unlock dijalankan.

2. **Pemetaan dan Assignment Pengajar**
   - PJ MK dan Tim Pengajar disimpan per periode akademik dan per mata kuliah/kurikulum.
   - Setiap mata kuliah/kurikulum wajib memiliki tepat satu PJ MK berakun sebelum kelas dapat dijadwalkan; anggota tim tambahan bersifat opsional.
   - PJ MK berada dalam Tim Pengajar dan berperan sama seperti dosen lain dalam hal mengajar.
   - Satu Kelas MK memiliki satu Assignment Pengajar, tanpa co-teacher.
   - Dosen eksternal dapat tercatat dalam Tim Pengajar, tetapi wajib memiliki akun dosen untuk mendapat Assignment Pengajar melalui auto-scheduler.
   - Kelas lintas prodi memakai pool gabungan dan ditangani oleh PJ Prodi pemilik/primary sebagai PJ lead.
   - Panel UI memakai label `Tim Pengajar` untuk pool per mata kuliah dan `Penugasan Kelas` untuk Assignment Pengajar. Setelah PJ MK/Tim Pengajar disimpan, UI menawarkan lanjut ke Penugasan Kelas dengan konteks mata kuliah yang sama.

3. **Auto-assignment**
   - PJ Prodi mengatur urutan Tim Pengajar, dengan PJ MK pada posisi pertama secara default.
   - Kelas paralel memakai snake order: kelas pertama ascending, kelas kedua descending, kelas ketiga ascending, dan seterusnya.
   - PJ Prodi dapat mem-pin dosen yang sama ke beberapa kelas non-paralel; solver tetap mencegah bentrok waktu.
   - Assignment ditampilkan sebagai preview saat generate. Override PJ dipertahankan, sedangkan kelas tanpa assignment atau reset eksplisit menghitung ulang assignment.
   - Jika dosen hasil auto-assignment tidak memiliki slot valid, solver mencoba dosen berikutnya dalam pool. Dosen yang di-pin tidak menerima fallback.

4. **Penjadwalan dan finalisasi**
   - Scheduler dijalankan manual oleh PJ Prodi/admin melalui aksi Perbarui Jadwal. Perubahan preferensi, pemetaan, atau assignment menandai jadwal sebagai stale.
   - Regenerate mencakup seluruh kelas draft dalam cakupan PJ Prodi. Kelas final dan jadwal yang diedit manual dilindungi sampai reset eksplisit.
   - Finalisasi diblokir oleh konflik keras, kelas belum terjadwal, atau jadwal stale.
   - Preferensi belum lengkap dan penempatan di luar Jam Preferensi menghasilkan peringatan, tetapi tidak memblokir finalisasi.
   - Satuan jadwal tetap mengikuti ADR 0004: satu Blok Jadwal per Kelas MK dengan durasi satu jam per SKS. Definisi konflik ruang/dosen mengikuti ADR 0006.

5. **Tampilan dan peran**
   - Papan Jadwal Bersama menampilkan seluruh Kelas MK dari lima prodi untuk semua peran. Filter program studi hanya mengubah tampilan dan tersedia pula untuk PJ Prodi. Hak edit, generate, dan finalisasi tetap admin untuk semua prodi serta PJ Prodi hanya untuk prodi dari profilnya. Dosen biasa membaca dengan filter `Kelas Saya`, tanpa kontrol edit atau diagnosis operasional.
   - Dashboard dosen menampilkan jadwal nyata, mata kuliah yang diampu termasuk yang belum terjadwal, status preferensi, deadline, serta status draft/final per kelas.
   - Klik Kelas Belum Terjadwal membuka aksi sesuai penyebab: formulir PJ MK untuk masalah dosen/pemetaan, atau detail penyebab untuk ruang, kapasitas, parity, dan MK terkunci.
   - Tidak ada fitur kontak atau usulan ke PJ Prodi/dosen di dalam aplikasi.

6. **Migrasi dan demo**
   - Ketersediaan lama disalin ke periode aktif sebagai Jam Preferensi dengan Blok Tidak Tersedia kosong.
   - Pemetaan global lama disalin ke periode aktif. Data lama dipertahankan sampai migrasi terverifikasi.
   - Mode demo memakai preferensi deterministik untuk seluruh dosen demo di lima prodi, bersifat idempoten, tidak menimpa data yang sudah diisi, dan menjalankan scheduler sekali setelah data siap. Produksi tidak auto-generate saat startup.

**Considered Options**: ketersediaan wajib global (ditolak: dosen harus menjamin jam yang belum pasti); semua Tim Pengajar mengajar setiap kelas (ditolak: menciptakan co-teacher palsu dan konflik); auto-generate setiap input berubah (ditolak: jadwal berubah sebelum review); multiple meetings per kelas (ditolak untuk saat ini: bertentangan dengan ADR 0004); fitur kontak dalam aplikasi (ditolak: menambah workflow yang belum diperlukan).

**Consequences**: skema perlu menambahkan konteks periode pada preferensi dan referensi pengajar, tabel Assignment Pengajar, Deadline Preferensi, serta status stale. Solver perlu memakai dosen yang diassign per kelas, bukan seluruh pool. Endpoint dashboard dosen harus mengambil data penugasan nyata. Migrasi data lama wajib idempoten dan dapat diverifikasi sebelum data sumber dihapus.
