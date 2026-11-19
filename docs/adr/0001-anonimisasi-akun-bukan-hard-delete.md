# Anonimisasi akun, bukan hard delete

Penghapusan baris `users` ditolak oleh hampir semua foreign key (`ON DELETE RESTRICT`) dan menghilangkan riwayat akademik. Kami memutuskan akun dinonaktifkan lalu dianonimisasi: data pribadi dibersihkan, baris akun beserta riwayat akademiknya tetap ada, dan pendaftaran ulang memakai `user_id` baru tanpa memindahkan riwayat lama. Ini mengikuti kebijakan yang sudah tercatat di `SCHEMA_REVIEW.md`, memenuhi kebutuhan penghapusan data pribadi yang mendesak, dan menjaga integritas referensial.
