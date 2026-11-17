# 09: Sinkronisasi Trello dan koreksi drift knowledge base

**What to build:** Status board `FTMM COMPASS` akhirnya mencerminkan pekerjaan yang benar-benar terverifikasi. Setiap kartu in-scope membawa bukti teknis, klaim lama yang tidak sesuai kode dikoreksi, dan kartu yang ditunda tetap jujur statusnya.

**Blocked by:** 01, 02, 03, 04, 05, 06, 07, 08 — seluruh ticket implementasi harus selesai dan terverifikasi lebih dulu.

**Status:** resolved

- [x] Kesembilan kartu in-scope memiliki evidence comment yang memuat akar masalah, perubahan teknis, dan bukti eksekusi terukur.
- [x] Checklist deliverable dicentang dan flag `dueComplete` diubah menjadi true hanya untuk kartu yang buktinya sudah terverifikasi.
- [x] Kartu draf penyimpanan lokal ditutup dengan catatan bahwa kebutuhannya dipenuhi oleh persistensi server dan penyimpanan lokal sengaja tidak dipakai.
- [x] Kartu benchmark konkurensi dan streaming tetap berstatus belum selesai serta tidak disentuh.
- [x] Drift dikoreksi di comment: artefak dari repositori chatbot bukan bukti untuk kartu repositori UI, identitas pengguna kontainer adalah 1001, dan kontrak kanonik rencana studi tetap memakai resource `degree-plans`.
- [x] Tidak ada operasi publish atau push ke remote mana pun.

## Comments

- Resolved 2026-11-17. Sembilan kartu (#40, #53, #54, #88, #89, #129, #137, #138, #139) memiliki evidence comment, checklist tercentang, dan `dueComplete=true`; screenshot UI terlampir. #127 benchmark tetap `dueComplete=false` tanpa tulisan baru. Drift dikoreksi: UID 1001, `degree-plans` + `items`, artefak chatbot bukan bukti repo UI. Log lengkap: `evidence/trello-sync.md`. Commit `cc92912`, `b1751fc`.
