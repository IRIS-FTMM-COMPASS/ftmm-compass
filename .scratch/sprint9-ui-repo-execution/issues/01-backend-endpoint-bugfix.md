# 01: Bug fixing sistematis seluruh endpoint backend

**Trello:** #62 — https://trello.com/c/fgHaja1s/62-mantra-bug-fixing-backend-semua-endpoint
**Repo:** `ftmm-compass-ui/backend`
**Owner:** Mantra
**Labels:** high, EPIC 4 — Integration & Refinement
**Due:** 2026-11-23
**Status:** ready-for-agent

**What to build:** Perbaiki edge case validasi prasyarat, error handling yang belum ter-cover, dan ketidakkonsistenan format response di seluruh endpoint gateway. Gunakan hasil bug fixing #161 sebagai bukti terpisah untuk perbaikan notifikasi.

**Blocked by:** None.

- [ ] Edge case validasi prasyarat (urutan semester, paritas, SKS melebihi batas) mengembalikan 422 dengan `error.code` yang konsisten, bukan 500.
- [ ] Seluruh handler mengembalikan envelope standar untuk error 400/404/409/422/500; tidak ada respons error berbentuk string polos.
- [ ] Endpoint dual-tier `/api/v1/*` dan `/api/*` menghasilkan payload dengan bentuk yang sama untuk kasus sukses maupun gagal.
- [ ] Suite `uv run --directory backend python -m pytest tests -q` lulus tanpa test yang dilewati.
- [ ] Ringkasan perbaikan per endpoint ditulis sebagai catatan bukti, termasuk endpoint yang diperiksa tetapi tidak diubah.
