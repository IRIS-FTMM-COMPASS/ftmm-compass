# 12: Kontrak bentrok jadwal dan indeks

**What to build:** Deteksi bentrok jadwal tetap benar dan cepat saat jumlah jadwal bertambah. Pemakaian tampilan bentrok di jalur aplikasi selalu dibatasi pada satu timetable.

**Blocked by:** None (can start immediately).

**Status:** resolved

**Sumber:** kartu Trello #143 dan #60 — Darryl, normal, due 23 Nov 2026.

- [x] Kontrak pemakaian tampilan bentrok ditulis dengan batasan timetable dan alasannya.
- [x] Pengukuran menunjukkan kueri terfilter di bawah 1 milidetik dan pemindaian penuh sekitar 23 milidetik, disertai perintah pengulangan.
- [x] Rencana eksekusi kedua kueri tersimpan sebagai bukti.
- [x] Pemeriksaan otomatis menolak pemakaian tampilan bentrok tanpa batasan timetable.
- [x] Perubahan indeks melalui migrasi yang dapat dinaikkan dan diturunkan, dan deteksi bentrok tetap menghasilkan pasangan yang sama seperti sebelumnya.

## Comments

- Resolved 2026-11-17. docs/database/TIMETABLE_CONFLICT_CONTRACT.md written, EXPLAIN plans saved under database/bench/plans/, filtered query 0.824 ms vs full scan 25.968 ms, static guard and parity tests in tests/test_timetable_conflicts.py pass (2 tests), alembic downgrade -1 then upgrade head verified clean.
