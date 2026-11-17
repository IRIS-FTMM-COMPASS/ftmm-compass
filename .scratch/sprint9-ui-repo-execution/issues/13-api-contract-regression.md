# 13: Regresi kontrak API dua tier

**What to build:** Seluruh titik akhir yang berubah pada sprint ini berperilaku sama di jalur kanonik dan jalur lawas, termasuk saat validasi gagal. Klien tidak menemui 500 atau bentuk error yang berbeda antar endpoint.

**Blocked by:** 02, 04, 05, 06, 07, 09, 10, 12.

**Status:** ready-for-agent

**Sumber:** kartu Trello #62 — Mantra, high, due 23 Nov 2026.

- [ ] Kasus validasi prasyarat pada batas semester, paritas, dan batas SKS menghasilkan 422 dengan kode error yang konsisten.
- [ ] Respons error memakai amplop standar untuk 400, 401, 403, 404, 409, 422, 429, dan 500 tanpa detail internal.
- [ ] Pasangan endpoint kanonik dan lawas mengembalikan payload yang sama untuk kasus sukses maupun gagal.
- [ ] Tidak ada handler yang mengembalikan teks biasa sebagai respons error.
- [ ] Seluruh rangkaian pengujian backend lulus dan ringkasan cakupan per endpoint tersedia.
