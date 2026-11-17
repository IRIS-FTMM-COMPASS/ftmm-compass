# 07: Gateway produksi: envelope error, putus koneksi SSE, container terkunci

**What to build:** Operator mendapatkan perilaku gateway yang konsisten saat terjadi kegagalan: error tak terduga tetap memakai envelope standar, koneksi yang ditinggalkan klien menghentikan pekerjaan, dan kontainer berjalan dengan hak akses minimal.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Error tak tertangani mengembalikan status 500 dengan envelope error kanonik tanpa detail internal.
- [ ] Respons pembatasan laju menyertakan petunjuk kapan klien boleh mencoba lagi.
- [ ] Generator streaming berhenti ketika klien memutus koneksi; tidak ada inferensi lanjutan yang terbuang.
- [ ] Kontainer berjalan sebagai pengguna non-root, menghapus seluruh capability Linux, dan memakai root filesystem read-only sejauh jalur yang dapat ditulis mengizinkan.
- [ ] Endpoint informasi root dan versi API konsisten di dua tier rute.
- [ ] Enam test kesiapan produksi hijau dan build kontainer berhasil dengan keluaran ringkas.
