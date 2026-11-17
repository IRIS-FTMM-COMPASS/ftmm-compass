# 06: Planner dan timetable nyaman di ponsel dan tablet

**What to build:** Mahasiswa memakai Degree Planner dan Timetable Grid di layar sempit tanpa dropdown tak berguna, teks terpotong, atau geser horizontal halaman. Tata letak berubah bentuk secara nyata, bukan sekadar versi desktop yang diperkecil.

**Blocked by:** 04 — Deteksi bentrok dan alternatif kelas yang bisa diterapkan; 05 — Ekspor `.ics` dan cetak PDF dari jadwal yang sebenarnya.

**Status:** resolved

- [x] Di bawah 768 px, roadmap delapan semester berubah menjadi pemilih semester dan timetable berubah menjadi accordion per hari.
- [x] Pada lebar 375–414 px tidak ada horizontal scrollbar pada halaman utama dan teks tidak terpotong.
- [x] Seluruh tombol aksi memiliki luas sentuh minimal 44 x 44 px dengan jarak antar target yang cukup.
- [x] Drawer dan modal tetap dapat dibuka dan ditutup dengan Escape; indikator fokus terlihat saat navigasi keyboard.
- [x] Screenshot headless tersedia untuk lebar 375, 768, dan 1280 px dengan nol error console.

## Comments

- Resolved 2026-11-17. `SemesterSwitcher` + `DailyScheduleAccordion` aktif di <768 px, grid lama tetap di md+. Terukur scrollWidth = innerWidth pada 375/414/768/1280, target ≥44×44, Escape menutup modal/drawer, fokus terlihat, 0 error console. Enam screenshot ada di `evidence/`. Trello #139. Commit `8ca7ceb`.
