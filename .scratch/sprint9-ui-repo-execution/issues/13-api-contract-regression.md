# 13: Regresi kontrak API dua tier

**What to build:** Seluruh titik akhir yang berubah pada sprint ini berperilaku sama di jalur kanonik dan jalur lawas, termasuk saat validasi gagal. Klien tidak menemui 500 atau bentuk error yang berbeda antar endpoint.

**Blocked by:** 02, 04, 05, 06, 07, 09, 10, 12.

**Status:** resolved

**Sumber:** kartu Trello #62 — Mantra, high, due 23 Nov 2026.

- [x] Kasus validasi prasyarat pada batas semester, paritas, dan batas SKS menghasilkan 422 dengan kode error yang konsisten.
- [x] Respons error memakai amplop standar untuk 400, 401, 403, 404, 409, 422, 429, dan 500 tanpa detail internal.
- [x] Pasangan endpoint kanonik dan lawas mengembalikan payload yang sama untuk kasus sukses maupun gagal.
- [x] Tidak ada handler yang mengembalikan teks biasa sebagai respons error.
- [x] Seluruh rangkaian pengujian backend lulus dan ringkasan cakupan per endpoint tersedia.

## Comments

- Resolved 2026-11-17. backend/tests/test_api_contract.py covers canonical/legacy parity, 422 validation cases and error envelope for 400/401/403/404/409/422/429/500; docs/api-contract-regression.md has coverage table; full backend suite 160 passed.
