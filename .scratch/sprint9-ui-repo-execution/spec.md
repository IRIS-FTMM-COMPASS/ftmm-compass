# Spec: Eksekusi Kartu Sprint 9 dan Carryover Sprint 8 di Repo UI

Status: ready-for-agent
Feature slug: `sprint9-ui-repo-execution`
Source: grilling 2026-11-17 (Q1–Q7), pembacaan langsung board Trello `FTMM COMPASS` lewat MCP, dan deskripsi lengkap kartu.

## Keputusan Grilling

| Keputusan | Hasil |
|---|---|
| Artefak | Tiket lokal `.scratch/<slug>/spec.md` + `issues/NN-*.md`, bukan kartu Trello baru |
| Cakupan | Semua pekerjaan yang bisa dijalankan di `ftmm-compass-ui`: frontend, `backend/`, `database/` |
| Carryover Sprint 8 | Semua kartu belum selesai ikut, setelah filter cakupan repo |
| Metadata | Owner, label EPIC/prioritas, dan due date kartu asli dipertahankan |
| Kartu lintas repo | Tidak dibuatkan tiket (`ftmm-compass-chatbot` bukan cakupan) |
| Kartu sprint review/planning | Tidak dibuatkan tiket (bukan pekerjaan agen) |
| Status tiket | `ready-for-agent` untuk implementasi |

## Problem Statement

Sprint 9 memuat 20 kartu dan Sprint 9 belum ada yang selesai. Sprint 8 menyisakan 11 kartu dengan due date 16 Nov 2026 yang lewat. Tanpa daftar kerja yang terfilter menurut repo, agen berisiko mengerjakan eksperimen riset di repo chatbot atau mengira kartu review sprint bisa dieksekusi otomatis.

Di repo UI, masalah konkret yang masih terbuka:

- Katalog publik belum memakai PostgreSQL sebagai sumber utama; perubahan admin belum langsung tampil.
- Data demo `seed.py` bercampur dengan katalog resmi, termasuk kode yang bentrok dengan SID307 dan TEL302.
- Siklus akun hanya bisa lewat seeder: tidak ada registrasi, ganti password, reset, atau manajemen akun admin.
- JWT stateless tidak bisa dicabut, rate limit auth tidak aktif, notifikasi punya IDOR, dan SSE tidak diautentikasi.
- Frontend menelan error fetch, menampilkan angka hardcode, dan tidak mereset state saat 401.
- Kontrak query `v_timetable_conflicts`, caching, dan review schema belum dikunci.

## Solution

Buat 14 tiket vertikal sebagai irisan tracer yang menembus data, API, antarmuka, dan pengujian. Satu tiket mencakup satu perilaku yang bisa dibuktikan sendiri. Tidak ada modifikasi Trello dan tidak ada implementasi kode dalam tahap ini.

## Inventaris Tiket

| Tiket | Kartu Trello | Owner | Perilaku yang dihasilkan |
|---|---|---|---|
| 01 | #142 | Mantra | Katalog hanya berisi kurikulum resmi |
| 02 | #136 | Mantra | Katalog dari database dengan fallback lokal |
| 03 | #59 | Mantra | Cache katalog dengan invalidasi dari admin |
| 04 | #155, #156 | Mantra, Hans | Registrasi sampai Dashboard |
| 05 | #155, #156, #159 | Mantra, Hans | Pemulihan dan ganti password, token lama dicabut |
| 06 | #155, #156 | Mantra, Hans | Manajemen akun admin dan RBAC |
| 07 | #160 | Mantra | Batas laju autentikasi |
| 08 | #163 | Hans | Sesi kedaluwarsa kembali ke login |
| 09 | #161 | Mantra | Notifikasi hanya milik pengguna |
| 10 | #162 | Mantra, Darryl | SSE diautentikasi dan terukur |
| 11 | #166 | Hans | Error fetch dibedakan dari data kosong |
| 12 | #143, #60 | Darryl | Kontrak bentrok jadwal dan indeks |
| 13 | #62 | Mantra | Regresi kontrak API dua tier |
| 14 | #58 | Hans | Responsive dan cross-browser final |

## Blocking Edges

| Tiket | Blocked by |
|---|---|
| 01 | None |
| 02 | 01 |
| 03 | 02 |
| 04 | 01 |
| 05 | 04 |
| 06 | 05 |
| 07 | 05 |
| 08 | 05 |
| 09 | None |
| 10 | None |
| 11 | None |
| 12 | None |
| 13 | 02, 04, 05, 06, 07, 09, 10, 12 |
| 14 | 02, 04, 05, 06, 08, 11, 13 |
## Urutan Eksekusi

1. Frontier awal: 01, 09, 10, 11, 12. Kelima tiket ini tidak punya blocker.
2. 02 menyusul 01, lalu 03 menyusul 02. 04 juga menyusul 01.
3. 05 menyusul 04; 06, 07, dan 08 menyusul 05.
4. 13 menunggu seluruh perubahan endpoint selesai: 02, 04, 05, 06, 07, 09, 10, 12.
5. 14 terakhir karena memeriksa semua perubahan antarmuka: 02, 04, 05, 06, 08, 11, 13.


## Kriteria Verifikasi Umum

- Backend: `uv run --directory backend python -m pytest tests -q` lulus; migrasi `upgrade head` → `downgrade -1` → `upgrade head` bersih.
- Frontend: `pnpm format`, `pnpm --silent build -- --logLevel warn`, dan inspeksi browser nyata pada 375/768/1280 px.
- Bukti setiap tiket: status HTTP dan contoh body, pernyataan migrasi, atau screenshot sesuai domainnya.
- Tidak ada perubahan pada board Trello sampai implementasi terverifikasi.

## Out of Scope

- Kartu AI Sprint 9 #64, #152, #153, #154 dan eksperimen retrieval Sprint 8 #144–151: repo `ftmm-compass-chatbot`.
- Kartu review/planning #66 dan #61: pekerjaan manusia.
- Pembuatan kartu Trello baru, pemindahan kartu, comment, atau perubahan status Trello.
- Implementasi kode, migrasi aktual, dan sinkronisasi status kartu; tiket ini hanya merencanakan pekerjaan.

## Catatan

- Branch kerja `chore/sprint9-ticket-scaffold` dibuat dari ref `upstream/main` lokal. Tidak ada push atau PR.
- Due date #58, #59, #60 tetap 16 Nov 2026 sesuai metadata asli dan sengaja dibiarkan lewat; ini sinyal carryover, bukan perubahan tanggal.
- Seluruh teks antarmuka memakai Bahasa Indonesia formal dan ramah; warna memakai token `@theme` serta helper `cn()`.
- Format tiket mengikuti skill `to-tickets`: `What to build`, `Blocked by`, `Status`, dan kriteria penerimaan yang dapat diamati; provenansi kartu Trello tetap dicantumkan tanpa path kode.
- Persetujuan granularitas, blocking edges, dan tidak ada penggabungan atau pemecahan tambahan diperoleh dari sesi grilling 2026-11-17.
