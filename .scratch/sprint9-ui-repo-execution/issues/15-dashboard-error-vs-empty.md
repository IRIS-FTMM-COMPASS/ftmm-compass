# 15: Bedakan error fetch dari data kosong

**Trello:** #166 — https://trello.com/c/fGn3VpkD/166-hans-bedakan-error-fetch-dari-data-kosong-di-dashboard-dan-notifikasi
**Repo:** `ftmm-compass-ui/src`
**Owner:** Hans
**Labels:** EPIC 4 — Integration & Refinement, Hans, normal
**Due:** 2026-11-23
**Status:** ready-for-agent

**What to build:** Terapkan tiga state (loading, error + retry, empty) pada `useDashboardData.ts` dan `NotificationDropdown.tsx`. Hilangkan angka hardcode pada `DashboardStats.tsx` dan ambil nilai dari `/api/v1/dashboard/me` atau sembunyikan bila field tidak ada.

**Blocked by:** None. Bagian dari tiket 12 yang dipisah.

- [ ] Backend mati atau request gagal → banner error dan tombol retry muncul, bukan statistik kosong.
- [ ] Pesan "Tidak ada notifikasi" hanya muncul saat API benar mengembalikan `[]` atau `null`.
- [ ] Tidak ada angka hardcode "3 Kelas Paralel Aktif" atau "/ 12 SKS Standar BKD" di komponen Dashboard.
- [ ] Screenshot kondisi error dan empty terlampir; `pnpm --silent build -- --logLevel warn` lulus.
