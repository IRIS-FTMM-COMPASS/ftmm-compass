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

Buat 17 tiket lokal, satu per kartu Trello yang lolos filter cakupan. Tiket memuat owner, label, due date, ketergantungan, dan kriteria penerimaan yang bisa dijalankan ulang. Tidak ada modifikasi Trello dan tidak ada implementasi kode dalam tahap ini.

## Inventaris Tiket

### Backend dan database

| Tiket | Trello | Owner | Fokus |
|---|---|---|---|
| 01 | #62 | Mantra | Bug fixing semua endpoint |
| 02 | #142 | Mantra | Pemisahan data demo dari katalog resmi |
| 03 | #136 | Mantra | `GET /api/v1/courses` dari PostgreSQL + fallback |
| 04 | #155 | Mantra | Registrasi, password, reset, admin users + migrasi |
| 05 | #159 | Mantra | Pencabutan token lama via `token_version` |
| 06 | #160 | Mantra | Rate limit login/register/reset |
| 07 | #161 | Mantra | IDOR notifikasi dan mark-all |
| 08 | #162 | Mantra, Darryl | Autentikasi, batas koneksi, metrik SSE |
| 09 | #143 | Darryl | Kontrak wajib filter `timetable_id` |
| 10 | #59 | Mantra | Caching katalog dan prasyarat (carryover) |
| 11 | #60 | Darryl | Review schema dan indeks (carryover) |

### Frontend dan QA

| Tiket | Trello | Owner | Fokus |
|---|---|---|---|
| 12 | #63 | Hans | Bug fixing semua halaman |
| 13 | #156 | Hans | Registrasi, reset, ganti password, admin UI |
| 14 | #163 | Hans | Reset sesi React saat 401/expiry |
| 15 | #166 | Hans | Error vs empty di Dashboard dan Notifikasi |
| 16 | #58 | Hans | Responsive dan cross-browser (carryover) |
| 17 | #157 | Darryl | QA migrasi akun, RBAC, rate limit |

## Urutan Eksekusi

1. #142 menentukan nasib seeder demo sebelum kredensial pada #155 diubah.
2. #155 membuka jalur register/reset dan kontrak respons; #156, #157, #159, #160 bergantung padanya.
3. #163 dan #166 adalah bagian dari #63 yang dipisah agar buktinya jelas.
4. #136, #143, #59, #60, #161, #162 berdiri sendiri; #143 harus selesai sebelum endpoint timetable memakai view.
5. #58 terakhir pada jalur frontend karena perubahan UI akun masih bergerak.

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
