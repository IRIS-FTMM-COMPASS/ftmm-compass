# FTMM Compass, Struktur & Isi Deck Presentasi

Dokumen ini adalah sumber tunggal untuk script `build_deck.js`. Setiap slide punya kicker besar (gaya template), satu kalimat aksi (isi argumen), konten visual, dan penjelasan lisan.

**Target:** 15 menit, 14 slide, audiens mahasiswa FTMM.
**Prinsip:** tunjukkan produk lewat layar nyata; progres dilaporkan jujur; tidak ada bagian riset dan tidak ada timeline sprint.

## Ghost deck test

Baca hanya kalimat aksi berurutan:

1. FTMM Compass menyatukan katalog, planner, jadwal, dan AI dalam satu platform.
2. Informasi akademik datang terlambat dan tersebar, jadi mahasiswa menyusun KRS dengan menebak.
3. Empat alat memakai satu data: katalog, planner, jadwal, dan AI.
4. Dashboard dan Course Finder menunjukkan posisi studi dan prasyarat tanpa pindah aplikasi.
5. Degree Planner dan Timetable menyusun 8 semester serta mendeteksi bentrok sebelum KRS.
6. Compass AI menyusun rekomendasi; polling membuka kelas yang dipilih mahasiswa.
7. Profil, preferensi, notifikasi, dan peran staf melengkapi alur mahasiswa.
8. Lima langkah dari login sampai rencana tersimpan.
9. Alur inti sudah berjalan. Compass AI dan deploy belum selesai.
10. Compass AI butuh layanan aktif, produk belum publik, evaluasi belum final, dan mobile belum penuh.
11. Empat langkah berikutnya menuju rilis kampus.
12. Satu platform, satu data, rencana yang dicek sebelum KRS.

---

## Slide 01, Judul

- **Kicker:** FTMM Compass
- **Judul:** Satu platform untuk merencanakan studi 8 semester
- **Subjudul (lime):** Katalog, planner, jadwal, dan AI di satu tempat
- **Footer:** Tim FTMM COMPASS, Fakultas Teknologi Maju dan Multidisiplin, UNAIR, November 2026
- **Visual:** background template, logo asterisk + wordmark, ribbon 3D kanan.
- **Penjelasan:** Buka dengan satu kalimat: "Hari ini saya menunjukkan bagaimana mahasiswa FTMM bisa menyusun rencana studi tanpa menebak." Jangan baca judul.

## Slide 02, Daftar Isi

- **Kicker:** Daftar Isi
- **Kalimat aksi:** Enam bagian: masalah, solusi, fitur, cara pakai, progres, penutup.
- **Konten:** 01 Latar Belakang, 02 Solusi, 03 Fitur, 04 Cara Pakai, 05 Progres & Batasan, 06 Penutup.
- **Visual:** grid dua kolom, angka besar lime, garis tipis pemisah.
- **Penjelasan:** 20 detik. Peta jalan, bukan daftar materi.

## Slide 03, Dalam Satu Menit

- **Kicker:** Dalam Satu Menit
- **Kalimat aksi:** FTMM Compass menyatukan katalog 5 prodi, 411 mata kuliah, dan planner 8 semester dalam satu platform.
- **Konten:** 4 stat card: `5` Prodi, `411` Mata kuliah, `8` Semester, `144` SKS. Satu baris bukti di bawah kartu: "Dashboard di Fitur 01 memakai akun uji: 44 SKS, IPK 3,78."
- **Visual:** empat kartu angka besar, aksen lime pada angka.
- **Penjelasan:** Angka 411 berasal dari katalog database, bukan tebakan. Tekankan: ini bukan mockup, aplikasinya berjalan.

## Slide 04, Latar Belakang

- **Kicker:** Latar Belakang
- **Kalimat aksi:** Informasi akademik datang terlambat dan tersebar, jadi mahasiswa menyusun KRS dengan menebak.
- **Konten:** 3 kartu masalah:
  1. **Terlambat**, Silabus, jadwal, dan MK baru tersedia mendekati KRS. Waktu menyusun rencana tinggal hitungan hari.
  2. **Tersebar**, Informasi ada di silabus PDF, portal akademik, grup angkatan, dan pengalaman senior. Tidak ada satu titik akses.
  3. **Tidak terpadu**, Belum ada alat yang menggabungkan pencarian MK, jadwal visual, rencana per semester, dan rekomendasi personal.
- **Penutup visual:** "Akibatnya: salah ambil, prasyarat terlewat, jadwal bentrok, dan lulus lebih lama."
- **Visual:** 3 kartu kaca, angka 01/02/03 lime.
- **Penjelasan:** Beri satu contoh konkret: mahasiswa baru tahu syarat prasyarat setelah KRS dibuka, padahal urutan MK menentukan semester berikutnya.

## Slide 05, Solusi

- **Kicker:** Solusi
- **Kalimat aksi:** Empat alat memakai satu data: katalog, planner, jadwal, dan AI.
- **Konten:** 4 pilar:
  1. **Katalog resmi**, 5 prodi, filter, detail MK, diagram prasyarat.
  2. **Planner tervalidasi**, 8 semester; prasyarat, paritas, dan batas SKS dicek deterministik.
  3. **Jadwal visual**, bentrok terdeteksi sebelum KRS; kelas dipilih sesuai preferensi.
  4. **Compass AI**, menjawab pertanyaan akademik dengan konteks profil dan rencana pengguna.
- **Penutup visual:** "Validasi berjalan sebagai kode deterministik."
- **Visual:** 4 kartu sejajar, angka 01-04, aksen lime pada judul kartu.
- **Penjelasan:** Bedakan dari chatGPT biasa: validasi planner tidak diserahkan ke LLM; aturan kampus dijalankan sebagai kode deterministik.

## Slide 06, Fitur 01: Dashboard & Course Finder

- **Kicker:** Fitur 01
- **Kalimat aksi:** Dashboard dan Course Finder menunjukkan posisi studi dan prasyarat tanpa pindah aplikasi.
- **Konten kiri (2–3 bullet):**
  - SKS kumulatif, IPK, semester aktif, dan jadwal mingguan dalam satu tampilan.
  - Katalog 5 prodi dengan filter prodi, semester, SKS, tipe, dan paritas.
  - Detail MK menampilkan diagram alur prasyarat; satu klik tambah ke planner.
- **Visual kanan:** screenshot `01-dashboard.png` (atas) + `03-course-detail.png` (bawah), dibingkai kartu kaca.
- **Penjelasan:** Tunjukkan bahwa dashboard memakai data akun nyata (44 SKS, IPK 3,78) dan diagram prasyarat menjawab "MK ini boleh diambil kapan?".

## Slide 07, Fitur 02: Degree Planner & Timetable

- **Kicker:** Fitur 02
- **Kalimat aksi:** Degree Planner dan Timetable menyusun 8 semester serta mendeteksi bentrok sebelum KRS.
- **Konten kiri (2–3 bullet):**
  - Board 8 semester; MK wajib terkunci, MK pilihan bisa diseret.
  - Validasi otomatis: prasyarat, paritas ganjil/genap, dan batas SKS per IPS.
  - Sampai 10 skenario tersimpan di server; satu skenario aktif dipakai dashboard.
  - Jadwal mingguan menandai bentrok dan kelas yang dipilih.
- **Visual kanan:** screenshot `04-degree-planner.png`.
- **Penjelasan:** Tekankan persistensi server: rencana tidak hilang saat browser di-reset atau ganti perangkat.

## Slide 08, Fitur 03: Compass AI & Polling

- **Kicker:** Fitur 03
- **Kalimat aksi:** Compass AI menyusun rekomendasi; polling membuka kelas yang dipilih mahasiswa.
- **Konten kiri (2–4 bullet):**
  - Compass AI menjawab pertanyaan akademik dan merekomendasikan KRS.
  - Jawaban bisa langsung diterapkan ke Degree Planner lewat kartu rencana.
  - Polling MK pilihan: maksimal 3 vote prioritas per mahasiswa.
  - Kuorum minimum menentukan kelas pilihan dibuka; fakultas melihat jumlah peminat.
- **Visual kanan:** screenshot `05-compass-ai.png` + `06-polling.png` berdampingan.
- **Penjelasan:** Jujur: di mesin lokal, layanan chatbot sedang offline; UI menampilkan status dan fallback. Fitur tetap dirancang untuk tersambung ke microservice.

## Slide 09, Fitur Pendukung

- **Kicker:** Fitur Pendukung
- **Kalimat aksi:** Profil, preferensi, notifikasi, dan peran staf melengkapi alur mahasiswa.
- **Konten:** 4 kartu:
  1. **Akun & profil**, login NIM/email, JWT, multi-peran (mahasiswa, dosen, PJ, admin).
  2. **Preferensi jadwal**, jam dan hari yang dihindari dipakai saat memilih kelas.
  3. **Notifikasi**, perubahan status rencana dan pengumuman akademik.
  4. **Peran staf**, PJ mengelola ketersediaan MK dan penjadwalan; admin mengelola akun dan katalog.
- **Visual:** 2×2 kartu kaca.
- **Penjelasan:** Audiens mahasiswa cukup tahu bahwa dosen/PJ juga punya alur; jangan masuk detail operasional.

## Slide 10, Cara Pakai

- **Kicker:** Cara Pakai
- **Kalimat aksi:** Lima langkah dari login sampai rencana tersimpan.
- **Konten:** 5 langkah:
  1. **Masuk**, NIM atau email institusi.
  2. **Lihat posisi**, dashboard: SKS, IPK, jadwal, status polling.
  3. **Cari MK**, filter, baca prasyarat, tambah ke planner.
  4. **Susun rencana**, drag-and-drop, validasi otomatis, simpan skenario.
  5. **Tanya & vote**, Compass AI untuk rekomendasi; vote MK pilihan.
- **Visual:** 5 kartu bernomor horizontal; aksen lime pada nomor.
- **Penjelasan:** Alur ini dipakai mahasiswa setiap awal semester.

## Slide 11, Yang Sudah Berjalan

- **Kicker:** Yang Sudah Berjalan
- **Kalimat aksi:** Alur inti sudah berjalan. Compass AI dan deploy belum selesai.
- **Konten:** progress bar per modul (estimasi internal per 28 Nov 2026):
  - Katalog & Course Finder, 95%
  - Dashboard & Jadwal, 90%
  - Degree Planner, 90%
  - Polling MK Pilihan, 85%
  - Peran PJ/Dosen & Admin, 80%
  - Mobile & aksesibilitas, 70%
  - Compass AI, 65%
- **Catatan kaki:** "Persentase adalah estimasi checklist internal, bukan metrik otomatis."
- **Visual:** bar horizontal lime/putih, angka di ujung.
- **Penjelasan:** Jangan defensif. Sebut yang sudah: 38 tabel, 73 route, 411 MK, 5 prodi, aplikasi berjalan. Lalu sebut yang belum tanpa dibacakan semua.

## Slide 12, Batasan

- **Kicker:** Batasan
- **Kalimat aksi:** Compass AI butuh layanan aktif, produk belum publik, evaluasi belum final, dan mobile belum penuh.
- **Konten:** 4 kartu:
  1. **Compass AI (RISIKO)**, Bergantung pada microservice chatbot + Ollama; jika mati, endpoint mengembalikan 503 dan UI memakai fallback lokal.
  2. **Deploy (INFO)**, Belum ada URL publik; saat ini berjalan lokal (Vite 8443, FastAPI 8001–8050, PostgreSQL).
  3. **Evaluasi (INFO)**, Perbandingan RAG/CAG/Hybrid masih berjalan; hasil belum final.
  4. **Mobile (INFO)**, Cakupan responsif dan aksesibilitas belum penuh.
- **Visual:** 2×2 kartu dengan label status (oranye untuk risiko, putih untuk info).
- **Penjelasan:** Sebutkan batasan apa adanya. Jangan sembunyikan 503.

## Slide 13, Next Steps

- **Kicker:** Selanjutnya
- **Kalimat aksi:** Empat langkah berikutnya menuju rilis kampus.
- **Konten:** 4 kartu:
  1. **Deploy publik**, domain kampus, HTTPS, monitoring.
  2. **Finalisasi evaluasi**, benchmark RAG/CAG/Hybrid dan paper.
  3. **UAT mahasiswa**, uji alur nyata dan ukur SUS.
  4. **Perluas mobile & integrasi**, aksesibilitas, responsif, integrasi SIAKAD.
- **Visual:** 4 kartu bernomor, garis waktu horizontal tipis.
- **Penjelasan:** Hubungkan dengan batasan slide sebelumnya: setiap batasan punya langkah berikutnya.

## Slide 14, Penutup

- **Kicker:** Penutup
- **Kalimat aksi:** Satu platform, satu data, rencana yang dicek sebelum KRS.
- **Konten:** 3 takeaway:
  1. FTMM Compass menyatukan katalog, planner, jadwal, dan AI.
  2. Validasi prasyarat, paritas, dan SKS berjalan deterministik.
  3. Alur inti berjalan; AI dan deploy menyusul.
- **Footer:** Tim FTMM COMPASS, FTMM UNAIR, November 2026, "Terima kasih"
- **Visual:** background gelap, aksen lime, ribbon.
- **Penjelasan:** Slide ini bertahan saat Q&A. Ajakan: "Silakan dicoba di lingkungan lokal; kami terbuka pada masukan alur."

---

## Catatan produksi

- **Palet:** background template `image1.png`; teks putih `FFFFFF`; aksen lime `D3FC72`; kartu kaca gelap transparan.
- **Font:** judul `Inter Heavy`; kicker/body `Anantason`; subjudul `Anantason Light`; kartu `Anantason Bold`; wordmark `Helvetica Now Bold`. Font ini ditanam dari template ke deck oleh `embed_fonts.py`, jadi tetap tampil di mesin tanpa font tersebut.
- **Ukuran:** 20 × 11,25 inci (16:9), mengikuti template.
- **Aset:** `presentation/assets/image1.png` (background), `image2.png` (logo), `image4.png` (ribbon), `presentation/assets/screens/*.png` (tangkapan layar lokal).
- **Build:** `node presentation/build_deck.js` menghasilkan `FTMM-Compass-Deck.pptx` dan `FTMM-Compass-Deck.pdf`; font ditanam oleh `embed_fonts.py` di tengah pipeline.
- **Aturan UI:** pemisah teks memakai koma, bukan `·`; tidak ada emoji di output CLI.
- **Bukti screenshot:** diambil dari aplikasi lokal pada 28 November 2026 memakai akun `mahasiswa.testing@ftmm.unair.ac.id`; data dashboard 44 SKS dan IPK 3,78 berasal dari akun uji tersebut.
