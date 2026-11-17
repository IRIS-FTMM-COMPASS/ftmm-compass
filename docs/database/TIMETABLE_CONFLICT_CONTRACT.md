# Kontrak pemakaian `v_timetable_conflicts`

## Kontrak

`v_timetable_conflicts` hanya boleh dipakai dengan predicate `WHERE timetable_id = :timetable_id`.
Satu pemanggilan hanya boleh memeriksa satu timetable. Pemakaian tanpa predicate tersebut
termasuk pelanggaran kontrak, termasuk untuk laporan admin.

Alasan: view menggabungkan `timetable_items` dengan dirinya sendiri. Tanpa filter, planner
harus membaca seluruh item dua kali. Pada skala benchmark 24.014 item, kueri terfilter
selesai dalam 0,82 ms memakai `timetable_items_section_unique`, sedangkan pemindaian penuh
membutuhkan 25,97 ms dengan hash join. Selisihnya ~31 kali. Jika laporan seluruh mahasiswa
dibutuhkan, gunakan materialized view atau job terjadwal, bukan kueri view langsung.

Kolom keluaran yang dijamin: `timetable_id`, `timetable_item_a_id`,
`timetable_item_b_id`, `class_section_a_id`, `class_section_b_id`, `day_of_week`,
`conflict_start`, `conflict_end`. Pasangan bentrok simetris dan hanya muncul sekali
(`ti2.timetable_item_id > ti1.timetable_item_id`).

## Cara mengulang pengukuran

```bash
docker exec -i ftmm-compass-postgres psql -U postgres \
  -c "DROP DATABASE IF EXISTS ftmm_bench" \
  -c "CREATE DATABASE ftmm_bench TEMPLATE ftmm_compass_dev"
docker exec -i ftmm-compass-postgres psql -U postgres -d ftmm_bench \
  < database/bench/timetable_bench_data.sql
docker exec -i ftmm-compass-postgres psql -U postgres -d ftmm_bench \
  -f database/bench/benchmark_queries.sql
```

Data dummy memakai tahun akademik 2099 dan awalan `BENCH-` agar tidak menimpa data dev.
Rencana eksekusi tersimpan di `database/bench/plans/explain_q1_filtered.txt` dan
`database/bench/plans/explain_q2_full_scan.txt`.

## Penegakan otomatis

`backend/tests/test_timetable_conflicts.py` menolak pemakaian view tanpa filter
`timetable_id` pada kode aplikasi dan membandingkan hasil view dengan perhitungan
bentrok independen untuk satu timetable.
