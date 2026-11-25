# Gedung dan lantai sebagai kolom ruang; ruang tanpa prodi adalah ruang bersama

Master ruang awalnya hanya menyimpan kode unik, kapasitas, dan prodi pemilik wajib. Inventaris FTMM memuat ruang di dua gedung (NANO dan NANI) dengan penomoran yang tidak dijamin unik lintas gedung, serta ruang yang tidak dialokasikan kepada prodi tertentu. Kode ruang tetap ditulis apa adanya (misalnya `6.01`), sedangkan gedung dan lantai menjadi kolom tersendiri; prodi pemilik boleh kosong dan berarti Ruang Bersama yang dapat dipakai prodi mana pun pada blok waktu yang berbeda.

**Status:** accepted

**Considered Options**: awalan gedung di dalam kode ruang (ditolak: kode tidak lagi sesuai nama ruangan dan gedung tidak dapat difilter); tabel gedung terpisah (ditolak: hanya dua nilai yang diketahui); prodi pemilik wajib untuk semua ruang (ditolak: ruang bersama tidak bisa dipakai lintas prodi).

**Consequences**: solver harus menggabungkan ruang tanpa pemilik ke daftar setiap prodi dan validasi edit harus mengizinkannya; API penerima ruang tidak boleh menolak pemilik null. Kapasitas 60 pada data awal bersifat sementara dan admin menggantinya dengan kapasitas fisik yang sebenarnya.
