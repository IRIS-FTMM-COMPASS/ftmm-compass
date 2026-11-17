# 12: Kontrak bentrok jadwal dan indeks

**What to build:** Deteksi bentrok jadwal tetap benar dan cepat saat jumlah jadwal bertambah. Pemakaian tampilan bentrok di jalur aplikasi selalu dibatasi pada satu timetable.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

**Sumber:** kartu Trello #143 dan #60 — Darryl, normal, due 23 Nov 2026.

- [ ] Kontrak pemakaian tampilan bentrok ditulis dengan batasan timetable dan alasannya.
- [ ] Pengukuran menunjukkan kueri terfilter di bawah 1 milidetik dan pemindaian penuh sekitar 23 milidetik, disertai perintah pengulangan.
- [ ] Rencana eksekusi kedua kueri tersimpan sebagai bukti.
- [ ] Pemeriksaan otomatis menolak pemakaian tampilan bentrok tanpa batasan timetable.
- [ ] Perubahan indeks melalui migrasi yang dapat dinaikkan dan diturunkan, dan deteksi bentrok tetap menghasilkan pasangan yang sama seperti sebelumnya.
