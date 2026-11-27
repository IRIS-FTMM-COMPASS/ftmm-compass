# Seed Katalog FTMM (Sprint 7)

Pipeline untuk mengisi katalog 5 prodi FTMM (TSD, RN, TRKB, TE, TI) ke PostgreSQL schema V2.1 RC1.

```
PDF resmi (Drive tim: Dataset Matkul Prodi/Dokumen Mentah)  ──┐
Ekstrak/FIX *.json (detail: deskripsi, CPL, teks prasyarat) ──┤
                                                              ▼
backend/scripts/build_catalog.py      → database/seed/catalog_canonical.json   (struktur, di-commit)
                                      → Ekstrak/derived/catalog_details.json   (deskripsi/CPL/dosen, TIDAK di-commit)
backend/scripts/reconcile_catalog.py  → database/seed/reconciliation.json      (keputusan reviewer + bukti halaman)
                                      → database/seed/reconciliation_report.md
backend/scripts/seed_full_catalog.py  → deskripsi: Ekstrak/derived/catalog_details.json bila ada
                                          → fallback: Ekstrak/FIX *.json via json_record_key
                                          → fallback: kosong (mis. CI tanpa Ekstrak)
                                      → PostgreSQL
```

## Menjalankan

Seeder hanya butuh file yang sudah di-commit untuk struktur katalog. Deskripsi diambil
berurutan: `Ekstrak/derived/catalog_details.json` bila ada, lalu field `deskripsi` dari
`Ekstrak/FIX *.json` yang dicocokkan lewat `json_record_key`, lalu kosong bila keduanya
tidak ada. Semua file di bawah `Ekstrak/` gitignored dan tidak pernah di-commit.

`EKSTRAK_DIR` mengarahkan seeder ke direktori Ekstrak lain (default `<repo>/Ekstrak`).
Ini diperlukan misalnya saat bekerja di git worktree yang tidak memuat data gitignored:
arahkan `EKSTRAK_DIR` ke direktori Ekstrak yang sudah ada.

CI sengaja men-seed tanpa deskripsi karena direktori `Ekstrak/` tidak tersedia; deskripsi
kosong dan suite tes CI tidak memerlukan data terklasifikasi ini.

Seeder katalog tidak berjalan otomatis saat startup: `AUTO_SEED` default `false`, dan bila diaktifkan startup hanya menjalankan `seed_data()` dari `scripts/seed.py` (data demo). Lihat `docs/demo-data-policy.md` sebagai SSOT kebijakan data demo.

```bash
docker compose up -d postgres
uv run --directory backend alembic upgrade head
uv run --directory backend python -m scripts.seed_full_catalog
```

Membangun ulang katalog (butuh PDF di `Ekstrak/pdf/` dan 5 JSON di `Ekstrak/`):

```bash
uv run --with pypdf --directory backend python -m scripts.build_catalog
uv run --directory backend python -m scripts.reconcile_catalog
```

Seeder idempoten: aman dijalankan berulang, baris yang hilang dari katalog dinonaktifkan
(`is_active = false`), rule prasyarat milik seeder (`notes` diawali `seed:catalog`) dibuat ulang.

Rollback di bawah `b3f1c2d4e5a6` hanya jalan kalau tidak ada MK pilihan ber-`semester NULL`
(skema lama mewajibkan semester). Kalau seeder sudah pernah jalan, migrasi berhenti dengan pesan
`downgrade b3f1c2d4e5a6 butuh N baris MK pilihan ber-semester`. Pilihannya: isi
`recommended_semester`/`term` manual, atau reset katalog di DB dev (destruktif: `CASCADE` juga
menghapus `degree_plan_items` dan `student_course_records`):

```bash
psql "$DATABASE_URL" -c 'TRUNCATE curriculum_courses CASCADE'
uv run --directory backend python -m scripts.seed_full_catalog
```

`pg_trgm` (dibutuhkan migrasi indeks) harus tersedia di role database; lihat `backend/README.md`.

## Sumber kebenaran

| Data | Sumber | Catatan |
|---|---|---|
| Kode, nama, SKS, semester, wajib/pilihan | Tabel 4.1-4.5 **Panduan Pendidikan FTMM 2024-2025** (identik 2022-2023 & 2023-2024) | 37/37 total SKS per semester cocok dengan Sub-Jumlah/Jumlah tercetak |
| Deskripsi, CPL, teks prasyarat | Dokumen kurikulum 2021 per prodi (TSD & TRKB juga dari teks PDF; pilihan TI dari OCR); seeder membaca `Ekstrak/derived/catalog_details.json` atau `Ekstrak/FIX *.json` (via `json_record_key`) | keduanya gitignored, tidak di-commit |
| Aturan nilai, batas SKS, cumlaude | Panduan 2024-2025 hal 45-47 | belum di-seed (bukan scope kartu) |

Bukti per keputusan ada di `reconciliation.json` (field `evidence`: `pdf` / `inferred`, dan `pdf_check`).
Ringkasan temuan lengkap: `source_findings.md`. Transkripsi tabel PDF scan: `transcriptions/`.

## Status data di database

- `curriculum_courses.verification_status = 'verified'` hanya untuk baris yang tercetak persis di tabel resmi;
  kode sementara (`RKKX301`, `RNSX301`), kode yang dilengkapi (TE: KLJ301, KNJ401, PNJ495, PNJ499) dan
  alternatif agama TI bertanda `unverified`.
- **Semua** `course_requirement_rules` berstatus `unresolved` (belum ada verifikasi manusia), jadi belum
  dipakai sebagai aturan authoritative oleh Planner.
- Kode berhuruf **X** (`RKKX301`, `RNSX301`) adalah placeholder, bukan kode resmi.
