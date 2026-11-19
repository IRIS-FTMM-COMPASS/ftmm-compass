# PJ Prodi sebagai atribut dosen, bukan role terpisah

PJ Prodi tetap ber-role `lecturer`; jabatan itu dinyatakan sebagai penanda pada profil dosen beserta prodi yang dipegangnya. Kami memilih ini daripada role `pj_dosen` karena role baru menuntut perubahan constraint `users.role`, seed, dan seluruh pemeriksaan role di frontend, padahal wewenang PJ hanya beda scope data, bukan beda identitas. Batas satu PJ per prodi ditegakkan oleh constraint unik pada kombinasi prodi dan penanda PJ, bukan oleh aplikasi.

**Status:** accepted

**Considered Options**: role `pj_dosen` baru (ditolak: menyentuh banyak titik otorisasi); penanda pada akun admin (ditolak: PJ bukan admin).
