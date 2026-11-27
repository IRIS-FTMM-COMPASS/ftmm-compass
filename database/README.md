FTMM COMPASS database schema files.

Jalur skema kanonik adalah `uv run --directory backend alembic upgrade head`.
`schema_v2_1_rc1.sql` adalah baseline historis yang hanya dieksekusi oleh revisi
Alembic `d76b9c9047cc`; jangan menerapkannya langsung ke database. Perubahan
skema baru wajib lewat berkas migrasi di `backend/migrations/versions/`.
