# 09: Sinkronisasi Trello dan koreksi drift knowledge base

**What to build:** Status board `FTMM COMPASS` akhirnya mencerminkan pekerjaan yang benar-benar terverifikasi. Setiap kartu in-scope membawa bukti teknis, klaim lama yang tidak sesuai kode dikoreksi, dan kartu yang ditunda tetap jujur statusnya.

**Blocked by:** 01, 02, 03, 04, 05, 06, 07, 08 — seluruh ticket implementasi harus selesai dan terverifikasi lebih dulu.

**Status:** ready-for-agent

- [ ] Kesembilan kartu in-scope memiliki evidence comment yang memuat akar masalah, perubahan teknis, dan bukti eksekusi terukur.
- [ ] Checklist deliverable dicentang dan flag `dueComplete` diubah menjadi true hanya untuk kartu yang buktinya sudah terverifikasi.
- [ ] Kartu draf penyimpanan lokal ditutup dengan catatan bahwa kebutuhannya dipenuhi oleh persistensi server dan penyimpanan lokal sengaja tidak dipakai.
- [ ] Kartu benchmark konkurensi dan streaming tetap berstatus belum selesai serta tidak disentuh.
- [ ] Drift dikoreksi di comment: artefak dari repositori chatbot bukan bukti untuk kartu repositori UI, identitas pengguna kontainer adalah 1001, dan kontrak kanonik rencana studi tetap memakai resource `degree-plans`.
- [ ] Tidak ada operasi publish atau push ke remote mana pun.
