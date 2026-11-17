# 10: SSE terautentikasi dengan batas dan metrik

**What to build:** Percakapan streaming hanya melayani pengguna yang login dan tidak menerima identitas dari klien. Gateway menolak kelebihan koneksi dan memperlihatkan kondisi streaming pada probe kesehatan.

**Blocked by:** None (can start immediately).

**Status:** resolved

**Sumber:** kartu Trello #162 — Mantra dan Darryl, high, due 23 Nov 2026.

- [x] Permintaan streaming tanpa token ditolak dengan 401; identitas percakapan berasal dari token, bukan isi permintaan.
- [x] Melebihi batas koneksi menghasilkan 429 atau 503, bukan kegagalan server atau permintaan menggantung.
- [x] Antrean token yang melebihi batas menutup aliran dan menghentikan kerja yang tidak dipakai.
- [x] Probe kesehatan menampilkan jumlah koneksi aktif, latensi token pertama, dan durasi streaming.
- [x] Pengujian autentikasi, batas koneksi, dan pemutusan koneksi lulus.

## Comments

- Resolved 2026-11-17. /api/v1/chat/stream requires Bearer token, user id comes from JWT not body, connection cap returns 503 with Retry-After, queue cap closes stream, health probe exposes active_streams/first_token_latency_ms/last_stream_duration_ms; 11 tests in tests/test_chat.py and tests/test_health.py pass.
