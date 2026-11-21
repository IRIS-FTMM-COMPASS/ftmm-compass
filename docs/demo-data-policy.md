# Kebijakan data demo katalog

## Keputusan

Satu strategi yang dipakai: **data demo bersifat opt-in dan tidak pernah menjadi sumber katalog publik**.

> **SSOT:** Dokumen ini adalah sumber kebenaran untuk perilaku `AUTO_SEED` dan kebijakan data demo: default `false`, dan bila diaktifkan startup hanya menjalankan seeder demo.

`backend/scripts/seed.py` tetap menjadi seeder demo satu-satunya. `AUTO_SEED` default `false` di `backend/settings.py`; bila di-set `true`, startup hanya memanggil `seed_data()` dari `scripts/seed.py` (data demo) dan tidak pernah menjalankan seeder katalog penuh. Katalog publik dibangun hanya dari kurikulum otoritatif di PostgreSQL oleh `catalog.refresh_from_db()`, dengan fallback `Ekstrak/*.json`. Kurikulum demo 28 mata kuliah di `seed.py` kalah cakupan dari kurikulum resmi 411 mata kuliah sehingga tidak pernah terpilih sebagai kurikulum otoritatif.

Alasan: backend dapat start pada database kosong tanpa akun atau transkrip palsu, sementara pengujian otomatis masih dapat membiayai skenarionya sendiri lewat fixture `backend/tests/conftest.py` yang memanggil seeder secara eksplisit. Kode contoh `KIK101` dan kode voting demo tidak bocor ke endpoint katalog karena keduanya bukan bagian kurikulum otoritatif.

## Menjalankan mode demo

```bash
AUTO_SEED=true uv run --directory backend python app.py
# atau, untuk mengisi database yang sudah berjalan (urutan: katalog lalu demo):
uv run --directory backend python -m scripts.seed_full_catalog
uv run --directory backend python -m scripts.seed
```

Mode demo menambahkan akun `mahasiswa.testing@ftmm.unair.ac.id`, `dosen.testing@ftmm.unair.ac.id`, `admin@ftmm.unair.ac.id`, 45 akun pemilih sintetis, transkrip contoh, dan periode polling dengan suara contoh. Jangan aktifkan `AUTO_SEED` di lingkungan produksi.

## Penegakan otomatis

`backend/tests/test_courses.py::test_public_catalog_excludes_demo_only_codes` menolak regressions yang mengembalikan `KIK101` dari katalog publik.
