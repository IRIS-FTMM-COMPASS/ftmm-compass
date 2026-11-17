# 08: Amankan SSE — autentikasi, batas koneksi, metrik

**Trello:** #162 — https://trello.com/c/mvVuvdBD/162-mantra-darryl-amankan-sse-autentikasi-batas-koneksi-dan-metrik
**Repo:** `ftmm-compass-ui/backend`
**Owner:** Mantra, Darryl
**Labels:** high, EPIC 4 — Integration & Refinement, Mantra, Darryl
**Due:** 2026-11-23
**Status:** ready-for-agent

**What to build:** Minta `get_current_user` pada handler chat/SSE, abaikan `user_id` dari body klien, batasi konkurensi dengan `asyncio.Semaphore`, batasi panjang antrian token per koneksi, dan ekspos metrik koneksi aktif, first-token latency, serta durasi stream.

**Blocked by:** None. Turunan kartu #127 yang kini difokuskan pada keamanan gateway.

- [ ] Request tanpa token → 401; identitas streaming berasal dari JWT, bukan payload.
- [ ] Melebihi batas koneksi → 429 atau 503 dengan envelope standar, bukan crash atau hang.
- [ ] Antrian token yang melebihi batas menutup stream dan menghentikan inferensi.
- [ ] `GET /api/v1/health` atau endpoint metrik internal menampilkan koneksi aktif, latensi first-token, dan durasi stream.
- [ ] Test autentikasi, batas koneksi, dan disconnect lulus bersama seluruh suite backend.
