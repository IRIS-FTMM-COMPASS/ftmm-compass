# T14 — Responsive dan cross-browser final: bukti pemeriksaan browser

Tanggal: 2026-11-17
Aplikasi: `http://localhost:8443` (Vite), gateway API pada port 8001.
Akun uji: `mahasiswa.testing@ftmm.unair.ac.id` (akun demo seed) untuk putaran awal. Permukaan auth sprint 9 diverifikasi dengan akun admin seed `admin@ftmm.unair.ac.id` (kata sandi demo tidak dicatat di dokumen ini). Formulir registrasi, pemulihan, dan ganti kata sandi tidak disubmit — pemeriksaan dibatasi pada rendered state, geometri, fokus keyboard, dan error konsol.

## Metode

- Pemeriksaan memakai tab browser sungguhan melalui alat browser: **Chromium headless** (managed) dan **WebKit headless** (padanan Safari). Firefox tidak tersedia pada alat browser yang terpasang, sehingga tidak dapat diuji.
- Viewport yang diperiksa: 375×812, 768×1024, dan 1280×900 CSS piksel.
- Yang diukur: `document.scrollWidth` terhadap lebar viewport, elemen yang keluar dari viewport, target sentuh lebih kecil dari 44×44 piksel, keadaan fokus keyboard (`:focus-visible`), dan pesan error konsol.
- Kontrol yang berada di dalam wadah `overflow-x-auto` (bilah filter Course Finder, bilah prompt cepat Compass AI, kolom roadmap Degree Planner) tidak dihitung sebagai limpahan horizontal halaman karena dokumen tidak ikut bergeser.
- State error Dashboard dibuat dengan membatalkan `GET /api/v1/dashboard/me` melalui route browser. State kosong Notifikasi dibuat dengan mengembalikan `{"items":[]}` untuk `GET /api/v1/notifications/me`. Kedua route dihapus setelah tangkapan layar.
- Permukaan auth dicapai lewat interaksi UI nyata: tombol “Daftar akun” dan “Lupa sandi?” dari halaman masuk; profil lewat tombol akun di sidebar; Manajemen Akun lewat item navigasi sidebar setelah login sebagai admin. Pada 375 px sidebar berada di luar layar, sehingga dibuka dulu dengan tombol “Buka bilah navigasi”.
- Elemen dekoratif `blur-3xl` yang terklip oleh wadah `overflow-hidden` dan `<aside>` sidebar yang sengaja berada di luar layar saat tertutup (`-translate-x-full`, `pointer-events-none`) tidak dihitung sebagai limpahan halaman selama `document.scrollWidth` tetap sama dengan lebar viewport.

## Matriks halaman × peramban

| Halaman | Chromium 375 | Chromium 768 | Chromium 1280 | WebKit 375 | WebKit 768 | WebKit 1280 | Firefox |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Dashboard | Lulus | Lulus | Lulus | Lulus | Lulus | Lulus | Tidak tersedia |
| Course Finder | Lulus | Lulus | Lulus | Lulus | Lulus | Lulus | Tidak tersedia |
| Degree Planner (Roadmap) | Lulus | Lulus | Lulus | Lulus | Lulus | Lulus | Tidak tersedia |
| Degree Planner (Jadwal Aktif) | Lulus | tidak diuji terpisah | tidak diuji terpisah | tidak diuji terpisah | tidak diuji terpisah | tidak diuji terpisah | Tidak tersedia |
| Compass AI | Lulus | Lulus | Lulus | Lulus | Lulus | Lulus | Tidak tersedia |
| Registrasi — Daftar Akun Baru | Lulus | Lulus | Lulus | Lulus | Lulus | Lulus | Tidak tersedia |
| Pemulihan — Ganti Kata Sandi | Lulus | Lulus | Lulus | Lulus | Lulus | Lulus | Tidak tersedia |
| Profil — Ganti Kata Sandi | Lulus† | Lulus† | Lulus† | Lulus† | Lulus† | Lulus† | Tidak tersedia |
| Manajemen Akun (admin) | Lulus | Lulus | Lulus | Lulus | Lulus | Lulus | Tidak tersedia |

“Lulus” berarti tidak ada limpahan horizontal dokumen, tidak ada kontrol yang terpotong atau tidak dapat dicapai pada level halaman, dan tidak ada error konsol.

† Semula lulus secara visual tetapi menyisakan kontrol di bawah 44×44 px empat (375 px) atau tiga (768/1280 px) dan fokus keyboard sempat masuk ke sidebar tertutup pada 375 px. T14-A1 dan T14-A2 telah diperbaiki dan diverifikasi ulang; lihat bagian "Tindak lanjut koreksi T14-A1 dan T14-A2" di bawah.

Catatan T14-A3: daftar akun semula gagal (404) karena container gateway lama belum memuat rute; setelah gateway di-build ulang, `GET /api/v1/admin/accounts` mengembalikan 200 dan tabel akun termuat. Lihat bagian “Tindak lanjut koreksi T14-A3”.

## Hasil per viewport

| Viewport | Dashboard | Course Finder | Degree Planner | Compass AI |
| --- | --- | --- | --- | --- |
| 375 | `scrollWidth` 375; 0 limpahan; kontrol halaman minimal 44 px; fokus terlihat | `scrollWidth` 375; bilah program bergulir horizontal di dalam wadahnya; fokus terlihat | `scrollWidth` 375; tab dan kontrol minimal 44 px; tab Jadwal Aktif juga bebas limpahan | `scrollWidth` 375; header satu baris; 0 target sentuh kecil; fokus terlihat |
| 768 | `scrollWidth` 768; 0 limpahan | `scrollWidth` 768; kartu dua kolom, filter dalam wadah bergulir | `scrollWidth` 768; kolom roadmap dalam wadah `overflow-x-auto` | `scrollWidth` 768; 0 target sentuh kecil; label Reset Chat tidak terpotong |
| 1280 | `scrollWidth` 1280; 0 limpahan | `scrollWidth` 1280; 0 limpahan dokumen | `scrollWidth` 1280; 0 limpahan dokumen | `scrollWidth` 1280; 0 target sentuh kecil |

Hasil WebKit identik untuk lebar dokumen dan target sentuh pada keempat halaman. Tidak ada perbedaan perilaku yang teramati antara Chromium dan WebKit.

Keadaan fokus diverifikasi dengan navigasi keyboard: tombol menampilkan outline 3 px padat dan kolom input menampilkan outline 2 px padat ketika menerima `:focus-visible`.

### Hasil per viewport — permukaan auth sprint 9

| Viewport | Registrasi | Pemulihan | Profil — Ganti Kata Sandi | Manajemen Akun (admin) |
| --- | --- | --- | --- | --- |
| 375 | `scrollWidth` 375; 0 target <44 px; fokus terlihat (outline 3 px Chromium / 2 px WebKit); 0 error konsol | `scrollWidth` 375; 0 target <44 px; fokus terlihat; 0 error konsol | `scrollWidth` 375; 0 limpahan dokumen; form “Ganti Kata Sandi” (3 input + tombol) terverifikasi; 4 kontrol <44 px di luar form; fokus masuk sidebar tertutup | `scrollWidth` 375; 0 target <44 px; tabel melebar di dalam wadah bergulir; daftar 200, akun termuat; 0 error konsol |
| 768 | `scrollWidth` 768; 0 limpahan; fokus terlihat | `scrollWidth` 768; 0 limpahan; fokus terlihat | `scrollWidth` 768; 3 kontrol <44 px; fokus terlihat | `scrollWidth` 768; 0 target <44 px; daftar 200, akun termuat; 0 error konsol |
| 1280 | `scrollWidth` 1280; blur dekoratif terklip tidak dihitung; fokus terlihat | `scrollWidth` 1280; blur dekoratif terklip tidak dihitung; fokus terlihat | `scrollWidth` 1280; 3 kontrol <44 px; fokus terlihat | `scrollWidth` 1280; 0 target <44 px; daftar 200, akun termuat; 0 error konsol |

Pada keempat permukaan auth, Chromium dan WebKit sama-sama menghasilkan `scrollWidth` yang sama dengan lebar viewport, 0 target sentuh kecil pada registrasi/pemulihan/Manajemen Akun, dan 0 error konsol. Perbedaan yang teramati hanya ketebalan outline `:focus-visible` — 3 px padat di Chromium, 2 px padat di WebKit — dan titik awal Tab di 375 px; kedua peramban tetap mencapai kontrol sidebar yang tertutup (T14-A2).

## Perbaikan yang diterapkan

Putaran pertama berada di `src/features/chatbot/ChatbotPage.tsx`:

1. Header pada layar sempit memakai judul “Compass AI” dan label status “Mode aturan”, subtitle dan status panjang hanya tampil pada `sm` ke atas. Judul tidak lagi terpotong atau bertabrakan dengan status.
2. Avatar header diperkecil pada layar sempit dan diberi `flex-shrink-0`; blok judul diberi `min-w-0` agar tidak mendorong kontrol status keluar dari header.
3. Tombol Reset Chat diberi `min-h-11 min-w-11`, perataan tengah, dan ring fokus gold yang kontras pada latar navy. Label diberi `whitespace-nowrap` agar tidak terlipat menjadi dua baris pada 768 px.
4. Tombol prompt cepat diberi `min-h-11` dan ring fokus; tinggi wadah disesuaikan agar baris tidak memakan ruang berlebih.
5. Tombol kirim diberi `min-h-11 min-w-11`, perataan tengah, dan ring fokus; ruang kanan input diperlebar menjadi `pr-14` agar teks tidak tertutup tombol.
6. Gelembung pesan diberi `min-w-0` dan `break-words` agar teks panjang tidak meluber pada 375 px; lebar gelembung loading disamakan dengan gelembung pesan.

Putaran koreksi menambahkan perbaikan pada lima komponen anak:

1. `CourseFilterBar.tsx`: input pencarian, chip program, tombol tipe/parity, tiga select, “Paling Diminati”, dan “Reset” dinaikkan ke `min-h-11`/`h-11`; tombol juga memakai `min-w-11`. Chip program diberi `flex-shrink-0` agar label “Semua Program” tidak terpotong di dalam wadah yang dapat digulir.
2. `DashboardMainPanel.tsx`: header timetable diberi `flex-wrap gap-2` dan tombol “Buka di Degree Planner” memakai `min-h-11 min-w-11 px-3 whitespace-nowrap`, sehingga tidak lagi terlipat menjadi tiga baris pada 375 px.
3. `PollingPanel.tsx`: tombol “Pilih MK di Course Finder”, “Mulai Memilih MK Pilihan”, “Export CSV”, dan select prodi dinaikkan ke 44 px.
4. `TimetableGrid.tsx`: nama ruang pada sel jadwal diberi `title={item.room}` dan `break-words`, sehingga nama panjang tetap dapat dibaca melalui tooltip tanpa menambah limpahan horizontal.
5. `CourseResultsList.tsx`: tombol vote/wishlist pada kartu mata kuliah diberi `min-h-11 min-w-11`; tombol Edit Mata Kuliah (admin) juga diberi `min-h-11 min-w-11` beserta perataan tengah. Kedua kontrol mempertahankan `stopPropagation` dan perilaku aslinya.

Tidak ada perubahan pada `DashboardPage.tsx`, `CourseFinderPage.tsx`, `DegreePlannerPage.tsx`, atau `ChatbotPage.tsx` dalam putaran koreksi ini.

Pembaruan bukti T14 untuk empat permukaan auth tidak mengubah kode sumber. Temuan T14-A1/A2/A3 tercatat di bawah dan diserahkan kepada pemilik komponen terkait; tidak ada perbaikan yang diterapkan pada putaran ini agar bukti tetap merepresentasikan keadaan aplikasi yang diuji.

### Verifikasi ulang setelah koreksi

- 375 px, Chromium, Dashboard: `scrollWidth` 375; 0 elemen yang keluar dari viewport selain blur dekoratif yang memang terklip; 0 target sentuh di bawah 44 px. Tombol “Buka di Degree Planner” kini berada pada baris tersendiri dengan tinggi 44 px.
- 375 px, Chromium, Course Finder: `scrollWidth` 375; seluruh kontrol pada `CourseFilterBar` dan `CourseResultsList` kini minimal 44×44 px (tombol vote terukur 105×44 px); chip program yang melewati lebar layar berada di dalam wadah `overflow-x-auto` dan dapat digulir. Screenshot `dashboard-375.png`, `course-finder-375.png`, dan `course-finder-vote-375.png` diperbarui setelah perbaikan.
- Nama ruang seperti “Lab Komputasi A (Gedung Nano Lt. 2)” terverifikasi memiliki atribut `title` lengkap pada sel timetable Dashboard.
- 768 px dan 1280 px: `scrollWidth` masing-masing 768 dan 1280; tidak ada limpahan dokumen pada Dashboard maupun Course Finder.

## Temuan pada permukaan auth sprint 9

T14-A1 — Target sentuh di bawah 44×44 px pada halaman Profil (Chromium dan WebKit, semua viewport):

- “Edit Preferensi” 135×34 px (375 px),
- “Sinkronkan” 114×34 px (375/768/1280 px),
- “Keluar dari Akun” 293×36 px (375 px), 398×36 px (768 px), 254×36 px (1280 px),
- “Edit” 38×16 px (semua viewport).

Kontrol-kontrol ini berada di luar formulir “Ganti Kata Sandi”; formulir itu sendiri tidak memiliki target di bawah 44 px.

T14-A2 — Fokus keyboard masuk ke sidebar yang tertutup pada 375 px. `<aside>` memakai `-translate-x-full ... pointer-events-none`, tetapi tombol di dalamnya tetap menerima Tab. Baik Chromium maupun WebKit menempatkan fokus pada tombol “Dashboard”, “Course Management”, “Manajemen Akun”, profil, “Keluar / Logout dari Sesi”, atau “Buka Sidebar” sebelum mencapai konten halaman; outline tidak terlihat karena elemennya berada di luar layar. Perilaku ini teramati pada halaman Profil dan Manajemen Akun. Perbaikan yang disarankan: tandai sidebar sebagai `inert`/`aria-hidden` dan hapus dari urutan tab saat tertutup.

T14-A3 — Daftar Manajemen Akun semula gagal dimuat karena container gateway yang terdeploy sudah usang (stale artifact), bukan cacat aplikasi. `GET /api/v1/admin/accounts?page=1&page_size=20` mengembalikan 404 pada semua viewport dan peramban; UI merender “Not Found”, “Tidak ada akun yang cocok dengan filter.”, dan “Menampilkan 0 dari 0 akun”, tanpa error konsol. Rute sudah didefinisikan di `backend/api/auth.py:487`, tetapi image gateway yang berjalan belum menyertakannya. Setelah `docker compose build -q gateway && docker compose up -d gateway`, container sehat, `DATABASE_URL` mengarah ke `postgres:5432`, permintaan tanpa autentikasi mengembalikan 401 (bukan 404), dan permintaan dengan sesi admin mengembalikan 200 berikut daftar akun. **Status: teratasi.** Lihat “Tindak lanjut koreksi T14-A3”.

Bukan defect: pada 1280 px form masuk/registrasi/pemulihan, div dekoratif `blur-3xl` melampaui batas kiri viewport tetapi terklip oleh wadah `overflow-hidden`; `document.scrollWidth` tetap 1280. Sisa `<aside>` yang ditranslas keluar layar pada 375 px juga tidak menaikkan `scrollWidth` (375). Tabel Manajemen Akun melebar di dalam wadah yang dapat digulir, sehingga tidak dihitung sebagai limpahan halaman.

## Status kontrol di bawah 44 px

Tidak ada kontrol di bawah 44×44 px yang tersisa pada `CourseResultsList.tsx`. Tombol vote/wishlist dan tombol Edit Mata Kuliah keduanya memakai `min-h-11 min-w-11`; kartu mata kuliah yang dapat diklik memiliki luas jauh di atas 44×44 px. Pada permukaan auth sprint 9, registrasi, pemulihan, dan Manajemen Akun juga bebas target <44 px; pengecualian ada pada halaman Profil (T14-A1).

## Error konsol

Setelah perbaikan dan setelah route uji dihapus, pemeriksaan ulang pada keempat halaman di Chromium dan WebKit menunjukkan **0 error konsol**. Dua entri `net::ERR_FAILED` untuk `/api/v1/dashboard/me` yang sempat muncul berasal dari route abort yang memang disengaja untuk menghasilkan `dashboard-error.png`; entri tersebut dibersihkan sebelum verifikasi akhir.

Pemeriksaan keempat permukaan auth di Chromium dan WebKit menunjukkan **0 error konsol**. Respons 403 pada `/api/v1/me/course-records` untuk peran admin teramati pada jaringan tetapi tidak menghasilkan entri error konsol. 404 lama pada `/api/v1/admin/accounts` tidak lagi teramati setelah gateway di-build ulang; permintaan kini mengembalikan 200 (T14-A3).

## Bukti tangkapan layar

Semua berkas berada di `.scratch/sprint9-ui-repo-execution/evidence/`:

- `dashboard-375.png`, `dashboard-768.png`, `dashboard-1280.png`
- `course-finder-375.png`, `course-finder-vote-375.png`, `course-finder-768.png`, `course-finder-1280.png`
- `degree-planner-375.png`, `degree-planner-768.png`, `degree-planner-1280.png`, `degree-planner-timetable-375.png`
- `chatbot-375.png`, `chatbot-768.png`, `chatbot-1280.png`
- `dashboard-error.png` — pesan “Gagal memuat data dashboard. Coba lagi.” beserta tombol Coba lagi, dengan angka statistik disembunyikan menjadi `-`.
- `notifications-empty.png` — pesan “Tidak ada notifikasi saat ini.” ketika layanan mengembalikan senarai kosong.
- Registrasi: `register-375.png`, `register-768.png`, `register-1280.png`
- Pemulihan: `recover-375.png`, `recover-768.png`, `recover-1280.png`
- Profil — Ganti Kata Sandi: `profile-password-375.png`, `profile-password-768.png`, `profile-password-1280.png`
- Manajemen Akun: `admin-accounts-375.png`, `admin-accounts-768.png`, `admin-accounts-1280.png`
- Padanan WebKit untuk kedua belas berkas di atas dengan akhiran `-webkit.png` (mis. `register-375-webkit.png`, `admin-accounts-1280-webkit.png`)

## Catatan lingkungan

Kontainer gateway pada awalnya berjalan dengan `DATABASE_URL` yang mengarah ke `localhost:5432` di dalam kontainer sehingga basis data tidak dapat dijangkau dan login mengembalikan 500. Kontainer tersebut dibuat ulang hanya dengan override environment runtime ke `postgres:5432`; tidak ada berkas repositori, compose, atau proses lokal yang diubah.

Permukaan auth diverifikasi dengan akun admin seed `admin@ftmm.unair.ac.id`; kata sandi demo tidak dicatat di dokumen ini dan formulir yang memutasi data tidak disubmit saat pengambilan bukti. Container gateway semula belum menyertakan rute `/api/v1/admin/accounts` (T14-A3); setelah di-build ulang dan di-deploy ulang (`docker compose build -q gateway && docker compose up -d gateway`) rute tersedia kembali dan daftar akun termuat.

## Tindak lanjut koreksi T14-A1 dan T14-A2

Tanggal: 2026-11-17. Bukti di atas merekam keadaan sebelum perbaikan; bagian ini mencatat keadaan setelah perbaikan.

Perubahan sumber:

1. `src/features/profile/ProfilePage.tsx`: wadah utama halaman profil kini memaksa `min-h-11`/`min-w-11` pada seluruh tombol (kecuali kartu modul yang memang memakai `group` dan sudah jauh lebih besar), serta `min-h-11` pada input, select, dan textarea. Aturan ini juga berlaku ketika dialog "Edit Preferensi Profil" terbuka. Perilaku dan struktur komponen anak tidak diubah.
2. `src/app/App.tsx`: `<aside>` kini menerima `inert` dan `aria-hidden` ketika `isSidebarOpen` bernilai false. Saat sidebar terbuka kedua atribut hilang, sehingga tombol di dalamnya kembali dapat diklik dan menerima Tab. Tombol pembuka di header berada di luar `<aside>` dan tetap berfungsi.

Verifikasi ulang dengan akun `mahasiswa.testing@ftmm.unair.ac.id`, halaman Profil, tanpa perubahan buatan pada halaman:

| Pemeriksaan | Chromium | WebKit |
| --- | --- | --- |
| 375 px: kontrol interaktif terlihat di bawah 44×44 px | 0 dari 13 | 0 dari 13 |
| 375 px: `document.documentElement.scrollWidth` | 375 | 375 |
| 375 px: Tab dari awal dokumen (18 kali) masuk ke `<aside>` | 0 kali | 0 kali (16 kali Tab) |
| 375 px: sidebar tertutup memiliki `inert` dan `aria-hidden="true"` | Ya | Ya |
| 375 px: buka sidebar, `inert` hilang, lalu tutup lewat tombol pembuka, `inert` kembali | Lulus | tidak diuji terpisah |
| 375 px: dialog Edit Preferensi, kontrol di bawah 44 px | 0 dari 6 | tidak diuji terpisah |
| 768 px dan 1280 px: kontrol di bawah 44 px / `scrollWidth` | 0 / 768 dan 0 / 1280 | tidak diuji terpisah |

Ukuran yang semula tercatat kini terukur 135×44 px ("Edit Preferensi"), 114×44 px ("Sinkronkan"), 293×44 px ("Keluar dari Akun" pada 375 px), dan 44×44 px ("Edit"). Fokus keyboard pada kelima belas kontrol pertama berada di header, kartu akses cepat, kartu keamanan, dan formulir "Ganti Kata Sandi"; tidak ada yang masuk ke sidebar tersembunyi. Tidak ada error konsol baru yang teramati.

T14-A3 (rute admin 404 pada gateway yang terdeploy) semula tidak termasuk perbaikan kode; temuan itu teratasi oleh rebuild/redeploy container gateway dan diverifikasi ulang di bagian “Tindak lanjut koreksi T14-A3”.

## Tindak lanjut koreksi T14-A3 (gateway rebuild)

Tanggal: 2026-11-17. Bagian ini mencatat verifikasi ulang setelah gateway di-build ulang; tidak ada perubahan berkas sumber pada putaran ini.

Koreksi lingkungan: `docker compose build -q gateway && docker compose up -d gateway`. Container sehat, `DATABASE_URL` mengarah ke `postgres:5432`. Sebelum perbaikan `GET /api/v1/admin/accounts` mengembalikan 404 tanpa autentikasi; sesudahnya mengembalikan 401 tanpa autentikasi dan 200 dengan sesi admin.

Verifikasi di browser sungguhan memakai `admin@ftmm.unair.ac.id`, halaman Manajemen Akun, tanpa interaksi mutasi:

| Pemeriksaan | Chromium 375 / 768 / 1280 | WebKit 375 / 768 / 1280 |
| --- | --- | --- |
| `GET /api/v1/admin/accounts?page=1&page_size=20` | 200 / 200 / 200 | 200 / 200 / 200 |
| Banner “Not Found” / “Tidak ada akun” | tidak ada / tidak ada / tidak ada | tidak ada / tidak ada / tidak ada |
| Baris akun termuat | Ya (mis. “Mahasiswa Pemilih 02”, `student.voter02@ftmm.unair.ac.id`) | Ya (entri yang sama) |
| `document.documentElement.scrollWidth` | 375 / 768 / 1280 | 375 / 768 / 1280 |
| Kontrol interaktif di bawah 44×44 px | 0 / 0 / 0 | 0 / 0 / 0 |
| Error konsol | 0 / 0 / 0 | 0 / 0 / 0 |

Fokus keyboard `:focus-visible` terlihat pada tombol dan kolom filter (outline 3 px di Chromium, 2 px di WebKit). Tabel melebar di dalam wadah yang dapat digulir pada 375 px tanpa menaikkan `scrollWidth` dokumen. Screenshot `admin-accounts-375.png`, `admin-accounts-768.png`, `admin-accounts-1280.png` beserta padanan `-webkit.png` diperbarui setelah rebuild dan kini menampilkan daftar akun yang termuat.

Catatan: pada WebKit 768/1280, percobaan login berturut-turut sempat terkena rate limit autentikasi T07 (pesan “Terlalu banyak permintaan autentikasi. Coba lagi dalam 60 detik.”) karena banyak percobaan dalam satu sesi uji; setelah jeda, verifikasi berhasil dengan hasil seperti tabel di atas. Ini bukan defect T14.
