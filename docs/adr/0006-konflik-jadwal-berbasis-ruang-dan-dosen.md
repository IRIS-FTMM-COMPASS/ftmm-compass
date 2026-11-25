# Konflik jadwal berbasis ruang dan dosen, bukan prodi

Sebelumnya papan jadwal menandai `kind="cohort"` setiap kali dua kelas dari prodi yang sama menempati hari dan jam yang bertabrakan. Aturan itu terlalu longgar: prodi yang sama belum tentu diambil oleh mahasiswa yang sama. Pada data katalog 2021, aturan tersebut menghasilkan 768 pasangan peringatan, 546 di antaranya berasal dari semester berbeda, sehingga hampir semua slot sibuk tampak "bentrok" dan peringatan kehilangan makna.

Konflik jadwal didefinisikan ulang menjadi dua jenis saja:

1. **Ruangan** — ruangan yang sama dipakai dua kelas pada blok jam yang bertabrakan.
2. **Dosen** — dosen yang sama ter-assign ke dua kelas pada blok jam yang bertabrakan.

Prodi tidak menjadi bagian dari aturan konflik. Dua MK prodi dan semester yang sama di ruang berbeda pada jam yang sama tidak ditandai; bentrok mahasiswa ditangani terpisah oleh timetable mahasiswa (`timetable_busy`) di solver.

**Status:** accepted

**Considered Options**: cohort per prodi + semester (ditolak: masih menandai kelas yang tidak mungkin diambil satu mahasiswa); cohort per prodi saja (ditolak: 768 pasangan palsu); menghapus semua peringatan konflik (ditolak: ruang dan dosen tetap tidak boleh tumpang tindih).

**Consequences**: `BoardConflictItem.kind` hanya `lecturer` dan `room`; `cohort_conflict_count` dihapus dari meta papan; finalisasi tetap memblokir konflik ruang/dosen. Deteksi konflik di `scheduling_board.py`, `scheduling_edits.py`, dan `scheduler.py` memakai definisi yang sama, sehingga hasil "Isi slot kosong" dan papan tidak lagi berbeda. Aturan booking ruang (ADR 0005) dan ketersediaan/preferensi dosen di solver tidak berubah. Pembatasan beban mengajar per kontrak perkuliahan tetap di luar cakupan papan ini.
