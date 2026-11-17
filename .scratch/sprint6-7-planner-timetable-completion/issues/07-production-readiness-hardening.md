# 07: Gateway produksi: envelope error, putus koneksi SSE, container terkunci

**What to build:** Operator mendapatkan perilaku gateway yang konsisten saat terjadi kegagalan: error tak terduga tetap memakai envelope standar, koneksi yang ditinggalkan klien menghentikan pekerjaan, dan kontainer berjalan dengan hak akses minimal.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] Error tak tertangani mengembalikan status 500 dengan envelope error kanonik tanpa detail internal.
- [x] Respons pembatasan laju menyertakan petunjuk kapan klien boleh mencoba lagi.
- [x] Generator streaming berhenti ketika klien memutus koneksi; tidak ada inferensi lanjutan yang terbuang.
- [x] Kontainer berjalan sebagai pengguna non-root, menghapus seluruh capability Linux, dan memakai root filesystem read-only sejauh jalur yang dapat ditulis mengizinkan.
- [x] Endpoint informasi root dan versi API konsisten di dua tier rute.
- [x] Enam test kesiapan produksi hijau dan build kontainer berhasil dengan keluaran ringkas.

## Comments

- Resolved 2026-11-17. Satu catch-all mengembalikan 500 envelope tanpa detail, 429 membawa retry hint, generator SSE berhenti saat klien pergi, compose memakai `cap_drop: ALL` + read-only dengan UID non-root 1001, root/version parity aktif di dua tier. 6 test readiness lulus, `docker compose config --quiet` lulus, build quiet. Trello #129. Commit `f2bba91`, `a12c461`, `8084765`.
