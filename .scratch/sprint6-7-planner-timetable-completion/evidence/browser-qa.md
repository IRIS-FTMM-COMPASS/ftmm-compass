# Browser QA: planner dan timetable

Tanggal: 2026-11-17. Cabang: `ticket/review-fixes`. Lingkungan: Vite milik agent di `http://127.0.0.1:9444`, gateway di `http://127.0.0.1:8001`, browser headless milik agent (`app:"own"`). Login memakai `mahasiswa.testing@ftmm.unair.ac.id` / `Mahasiswa2026!`, lalu membuka Degree Planner.

## Validasi gateway dari UI

- Tombol "Validasi Rencana Studi" diklik di tab Roadmap Studi.
- Satu permintaan `POST /api/v1/plans/validations` tercatat dengan status 200.
- Hasil tampil: `Hasil validasi gateway: rencana valid, 8 SKS terencana`.
- Setelah alur ini, `tab.errors()` mengembalikan 0 entri.
- Sebelum alur, tiga entri `net::ERR_ABORTED` muncul saat navigasi login ke planner. Ketiganya berasal dari pembatalan permintaan `class-sections` yang memang dibatalkan oleh `AbortController`; setelah dibersihkan, tidak ada error baru selama interaksi validator.

## Lebar dan overflow

Diukur dari `document.documentElement.scrollWidth` dan `clientWidth` pada halaman Degree Planner setelah sesi login:

| Lebar viewport | scrollWidth | clientWidth |
| --- | --- | --- |
| 375 | 375 | 375 |
| 414 | 414 | 414 |
| 768 | 768 | 768 |
| 1280 | 1280 | 1280 |

Tidak ada overflow horizontal pada keempat lebar tersebut.

## Target sentuh dan keyboard

- Pada 375 px, tab Roadmap menampilkan 25 elemen interaktif yang terlihat; 0 di antaranya lebih kecil dari 44 × 44 px.
- Pada 375 px, tab Jadwal Aktif juga menunjukkan 0 elemen interaktif terlihat yang lebih kecil dari 44 × 44 px.
- Tombol "Tambah Manual" membuka dialog pemilih matkul. Fokus berada di dalam dialog. Menekan `Escape` menutup dialog (`[role=dialog]` hilang); fokus kembali ke `body`, bukan ke tombol pemicu.
- Fokus pada tombol aksi memakai gaya `focus-visible` dari komponen yang sudah ada, tanpa `outline: none`.

## Ekspor iCalendar

- Tombol "Ekspor (.ics)" menghasilkan unduhan `jadwal-kuliah-ftmm-sem3.ics` (2029 byte).
- Berkas berisi tiga `BEGIN:VEVENT` dan tiga `RRULE:FREQ=WEEKLY;COUNT=16`.
- Nilai yang teramati:
  - `[TSD201] Algoritma & Struktur Data (A)`: `DTSTART;TZID=Asia/Jakarta:20260831T080000`, `DTEND;TZID=Asia/Jakarta:20260831T103000`.
  - `[TSD203] Basis Data Sains Data (A)`: `DTSTART;TZID=Asia/Jakarta:20260901T130000`, `DTEND;TZID=Asia/Jakarta:20260901T153000`.
  - `[TSD206] Kalkulus Multivariabel (A)`: `DTSTART;TZID=Asia/Jakarta:20260903T130000`, `DTEND;TZID=Asia/Jakarta:20260903T144000`.

## Berkas bukti

- `06-375.png`, `06-375-timetable.png`
- `06-768.png`, `06-768-timetable.png`
- `06-1280.png`, `06-1280-timetable.png`
- `jadwal-kuliah-ftmm-sem3.ics`

Seluruh berkas berukuran di bawah 5 MB, sehingga tidak ada berkas yang dilewati.
