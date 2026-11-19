# Peta Alur Web FTMM Compass — tanpa Compass AI

Dokumen ini menjawab satu pertanyaan: **bagaimana alur aplikasi web dari login sampai rencana studies tersimpan, tanpa libatan chatbot**. Lingkupnya dibatasi pada SPA React, provider state, Vite proxy, FastAPI gateway, dan PostgreSQL. Rute `/api/chat`, `/api/chat/stream`, sesi chat, transfer rencana dari asisten, serta layanan Ollama sengaja dikeluarkan.

Baca tiga gambar berikut berurutan: peta lapisan, alur navigasi, lalu alur data saat menyimpan rencana. Tabel di bagian akhir dipakai sebagai indeks endpoint.

## 1. Peta lapisan: siapa berbicara dengan siapa

Gambar ini menjawab: *apa saja lapisan yang dilalui permintaan web, dan mana yang berlaku untuk semua lapisan*. Warna menandakan lapisan, bukan dekorasi. Dua kolom samping membentang penuh karena aturan akses dan penanganan gagal berlaku di setiap lapisan, bukan sebagai lapisan tambahan.

<div style="max-width: 1100px; box-sizing: border-box;">
<style>
.wf-arch { background: #f4f4f4; padding: 22px; color: #1e1e1e; }
.wf-arch-title { margin: 0 0 4px; font-size: 22px; font-weight: 700; text-align: center; }
.wf-arch-sub { margin: 0 0 16px; font-size: 12px; color: #565656; text-align: center; }
.wf-arch-body { display: grid; grid-template-columns: 190px 1fr 190px; gap: 10px; align-items: stretch; }
.wf-arch-wing { background: #e8e8e8; border: 2px solid #4a4a4a; padding: 10px; display: flex; flex-direction: column; }
.wf-arch-wing-head { font-size: 10px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; text-align: center; border-bottom: 1px solid #787878; padding-bottom: 6px; margin-bottom: 8px; }
.wf-arch-wing-items { display: grid; gap: 6px; align-content: start; }
.wf-arch-wing-item { background: #ffffff; border: 1px solid #787878; padding: 7px; font-size: 11px; line-height: 1.3; }
.wf-arch-wing-item small { display: block; color: #565656; font-size: 9px; margin-top: 2px; }
.wf-arch-core { display: grid; gap: 8px; }
.wf-arch-layer { border: 1px solid #787878; padding: 9px 10px; }
.wf-arch-layer.l1 { background: #c8d4ed; }
.wf-arch-layer.l2 { background: #cbd9cf; }
.wf-arch-layer.l3 { background: #dbcfeb; }
.wf-arch-layer.l4 { background: #c8d6d6; }
.wf-arch-layer.l5 { background: #d7d7d7; }
.wf-arch-head { font-size: 10px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 6px; }
.wf-arch-head span { color: #565656; font-weight: 400; letter-spacing: 0; text-transform: none; }
.wf-arch-grid { display: grid; gap: 6px; }
.wf-arch-grid.c3 { grid-template-columns: repeat(3, 1fr); }
.wf-arch-grid.c4 { grid-template-columns: repeat(4, 1fr); }
.wf-arch-box { background: #ffffff; border: 1px solid #787878; padding: 6px 7px; font-size: 11px; text-align: center; line-height: 1.25; }
.wf-arch-box small { display: block; color: #565656; font-size: 9px; margin-top: 2px; }
.wf-arch-box.entry { border: 2px solid #003bb5; }
.wf-arch-foot { margin-top: 12px; text-align: center; font-size: 11px; color: #565656; }
</style>
<section class="wf-arch">
<h1 class="wf-arch-title">Arsitektur web-only</h1>
<p class="wf-arch-sub">enam lapisan di tengah; dua kolom samping berlaku untuk seluruh lapisan</p>
<div class="wf-arch-body">
<aside class="wf-arch-wing">
<div class="wf-arch-wing-head">Aturan akses</div>
<div class="wf-arch-wing-items">
<div class="wf-arch-wing-item">SessionProvider<small> JWT + expires_at</small></div>
<div class="wf-arch-wing-item">canAccess(page)<small> role student / lecturer / admin</small></div>
<div class="wf-arch-wing-item">activePage ↔ pathname URL<small> pathname dan activePage selalu sinkron</small></div>
<div class="wf-arch-wing-item">STUDENT_ONLY_PAGES<small> degree-planner</small></div>
<div class="wf-arch-wing-item">LECTURER_ONLY_PAGES<small> pj-courses</small></div>
<div class="wf-arch-wing-item">ADMIN_ONLY_PAGES<small> admin-accounts</small></div>
</div>
</aside>
<div class="wf-arch-core">
<div class="wf-arch-layer l1">
<div class="wf-arch-head">Experience <span>— yang diklik pengguna</span></div>
<div class="wf-arch-grid c3">
<div class="wf-arch-box entry">AppShell + sidebar<small> src/app/App.tsx</small></div>
<div class="wf-arch-box">Login<small> masuk / daftar / pulihkan</small></div>
<div class="wf-arch-box">Dashboard<small> telemetri + polling</small></div>
<div class="wf-arch-box">Course Finder<small> katalog + voting MK pilihan</small></div>
<div class="wf-arch-box">Degree Planner<small> roadmap + timetable</small></div>
<div class="wf-arch-box">Profile + Admin Accounts<small> edit profil / kelola akun</small></div>
</div>
</div>
<div class="wf-arch-layer l2">
<div class="wf-arch-head">State providers <span>— hidup di atas semua halaman</span></div>
<div class="wf-arch-grid c3">
<div class="wf-arch-box">SessionProvider<small> peran &amp; sesi</small></div>
<div class="wf-arch-box">AcademicPeriodProvider<small> periode aktif</small></div>
<div class="wf-arch-box">CatalogProvider<small> katalog + program</small></div>
<div class="wf-arch-box">PollingProvider<small> periode, vote, demand</small></div>
<div class="wf-arch-box">PlannerProvider<small> draft, jadwal, pendingCourses</small></div>
<div class="wf-arch-box">ErrorBoundary<small> per halaman aktif</small></div>
</div>
</div>
<div class="wf-arch-layer l3">
<div class="wf-arch-head">Transport <span>— satu jalur untuk semua endpoint</span></div>
<div class="wf-arch-grid c3">
<div class="wf-arch-box">apiFetch / authService.request<small> path relatif /api/v1/*</small></div>
<div class="wf-arch-box">Bearer token<small> authHeaders()</small></div>
<div class="wf-arch-box">Vite /api proxy<small> port dari .backend-port</small></div>
</div>
</div>
<div class="wf-arch-layer l4">
<div class="wf-arch-head">Gateway <span>— dual tier /api/v1 dan /api</span></div>
<div class="wf-arch-grid c4">
<div class="wf-arch-box">auth + notifications</div>
<div class="wf-arch-box">courses + admin/courses</div>
<div class="wf-arch-box">dashboard/me</div>
<div class="wf-arch-box">degree-plans</div>
<div class="wf-arch-box">plans/validations</div>
<div class="wf-arch-box">class-sections</div>
<div class="wf-arch-box">me/course-records</div>
<div class="wf-arch-box">polling + academic-periods</div>
</div>
</div>
<div class="wf-arch-layer l5">
<div class="wf-arch-head">Data <span>— yang bertahan setelah request</span></div>
<div class="wf-arch-grid c3">
<div class="wf-arch-box">PostgreSQL 16<small> users, courses, plans, votes</small></div>
<div class="wf-arch-box">Cache katalog<small> refresh_from_db saat startup</small></div>
<div class="wf-arch-box">Alembic head<small> dijalankan saat lifespan</small></div>
</div>
</div>
</div>
<aside class="wf-arch-wing">
<div class="wf-arch-wing-head">Gagal &amp; pulih</div>
<div class="wf-arch-wing-items">
<div class="wf-arch-wing-item">ApiError 401<small> clearSession + logout</small></div>
<div class="wf-arch-wing-item">Proxy 502<small> Backend unavailable</small></div>
<div class="wf-arch-wing-item">Banner katalog / dashboard<small> tombol Coba lagi</small></div>
<div class="wf-arch-wing-item">PlanConflictDialog<small> konfirmasi timpa draf</small></div>
<div class="wf-arch-wing-item">Debounce save<small> revision + pending flush</small></div>
</div>
</aside>
</div>
<p class="wf-arch-foot">Kotak Compass AI tidak digambar: alur ini berhenti di browser dan gateway web.</p>
</section>
</div>

Ringkasan lapisan dalam bentuk teks:

| Lapisan | File / simbol kunci | Peran |
|---|---|---|
| Shell | `src/app/App.tsx` (`App`, `AppShell`) | `handleNavigate` menulis path halaman ke history; `popstate` membacanya untuk Back/Forward |
| Sesi | `src/features/auth/session.tsx` | `canAccess`, expiry timer, intercept `fetch` untuk 401 |
| Katalog | `src/features/catalog/catalog.tsx`, `courseData.ts` | `fetchCatalog` → `normalizeCourse`; `upsert`/`remove` untuk CRUD admin |
| Polling | `src/features/polling/polling.tsx`, `pollingService.ts` | periode aktif, vote mahasiswa, rekap demand |
| Rencana | `src/features/degree-planner/state/planner.tsx`, `degreeDrafts.ts` | draft tersimpan di server via `/api/v1/degree-plans`, bukan di localStorage |
| Transport | `src/shared/api/client.ts` | `apiFetch`, `ApiError`, `authHeaders`, penanganan 204 |
| Proxy | `vite.config.ts` (`backendApiProxyPlugin`) | meneruskan `/api` ke port di `.backend-port`; 502 bila gateway mati |
| Gateway | `backend/app.py` (`mount_resource`) | tiap router dipasang dua kali: `/api/v1` dan `/api` |
| Data | `backend/catalog.py`, Alembic di `lifespan` | katalog dimuat dari DB saat startup, fallback `Ekstrak/` |

## 2. Alur masuk dan pindah halaman

Gambar ini menjawab: *dari mana sesi berasal dan bagaimana peran menentukan halaman yang bisa dibuka*. Cabang Compass AI sengaja tidak diikutsertakan; tombolnya ada di sidebar mahasiswa, tetapi tidak termasuk alur ini.

```plantuml
@startuml
skinparam DefaultFontColor #1e1e1e
skinparam ArrowColor #787878
skinparam ArrowFontColor #1e1e1e
skinparam ActivityBackgroundColor #ffffff
skinparam ActivityBorderColor #787878
skinparam ActivityDiamondBackgroundColor #e8e8e8
title Alur sesi dan navigasi web (tanpa Compass AI)
start
:LoginPage kirim identifier + password;
:POST /api/v1/auth/login;
if (berhasil?) then (ya)
  :simpan token + expires_at di localStorage;
  :SessionProvider.login(user, expires_in);
else (gagal)
  :tampilkan AuthApiError di form;
  stop
endif
:AppShell aktif, replace history ke /dashboard;
:canAccess(activePage dari pathname) per role;
:menu dipilih → handleNavigate menulis path halaman ke history;
if (menu dipilih) then (dashboard)
  :GET /api/v1/dashboard/me;
else (course finder)
  :CatalogProvider GET /api/v1/courses;
  :PollingProvider GET polling periods + my-votes;
else (degree planner, student)
  :PlannerProvider GET /api/v1/degree-plans;
else (profile)
  :Profil menampilkan data auth/me;
else (admin accounts, admin)
  :GET /api/v1/admin/accounts;
endif
:ErrorBoundary key = activePage dari pathname merender halaman;
if (logout atau 401) then (ya)
  :clearSession, replace history ke /dashboard;
  stop
else (tidak)
  :tetap di halaman aktif;
  stop
endif
@enduml
```

Pathname URL kini menjadi identitas halaman aktif: `handleNavigate` menulis path saat menu dipilih dan `popstate` membacanya saat Back/Forward. Aturan akses tetap berasal dari `canAccess`; penolakan peran mengganti entri riwayat dengan `/dashboard`. Profil dibuka dari blok identitas di bawah sidebar, tersedia untuk semua peran.

| Peran | Menu sidebar (tanpa Compass AI) | Catatan akses |
|---|---|---|
| `student` | Dashboard, Course Finder, Degree Planner | Profil lewat blok identitas; Compass AI ada di UI tetapi di luar lingkup |
| `lecturer` | Dashboard, Rekap & Kelola MK | Degree Planner dan Compass AI ditolak `canAccess`; Course Finder tidak muncul di sidebar tetapi tetap bisa dibuka lewat URL/quick access |
| `admin` | Dashboard, Course Management, Manajemen Akun | Course Finder berubah judul menjadi Course Management; CRUD via `/api/v1/admin/courses` |

## 3. Alur data: katalog → planner → tersimpan

Gambar ini menjawab: *bagaimana satu mata kuliah bergerak dari katalog menjadi draft rencana di database, dan kapan validasi dijalankan*. Perhatikan bahwa penyimpanan terjadi dari `PlannerProvider` lewat debounce, bukan dari tombol simpan di halaman.

```plantuml
@startuml
skinparam DefaultFontColor #1e1e1e
skinparam ArrowColor #787878
skinparam ArrowFontColor #1e1e1e
skinparam ParticipantBackgroundColor #ffffff
skinparam ParticipantBorderColor #787878
skinparam ParticipantFontColor #1e1e1e
skinparam SequenceLifeLineBorderColor #787878
skinparam NoteBackgroundColor #e8e8e8
skinparam NoteBorderColor #787878
skinparam NoteFontColor #1e1e1e
title Tambah matkul lalu simpan dan validasi rencana
autonumber
actor M as Mahasiswa
participant A as AppShell
participant F as CourseFinder
participant C as CatalogProvider
participant X as apiFetch + Vite proxy
participant G as FastAPI /api/v1
database D as PostgreSQL
participant P as PlannerProvider
participant L as DegreePlanner
M -> A: klik Course Finder
A -> F: render(initialCourse, addedCourseIds)
F -> C: useCatalog()
C -> X: GET /api/v1/courses
X -> G: fetch /api, port dari .backend-port
G -> G: baca cache katalog (refresh_from_db saat startup)
G --> X: courses + programs
X --> C: normalizeCourse()
C --> F: courses, programs
F -> A: onAddToPlanner(course)
A -> P: addPendingCourse(course)
M -> A: buka Degree Planner
A -> L: render(pendingCourses)
L -> P: setPlan(updater)
P -> X: PUT /api/v1/degree-plans/{id}/items (debounce)
X -> G: simpan items
G -> D: update degree_plan_items
L -> X: POST /api/v1/plans/validations
X -> G: program_studi + riwayat + plan
G --> L: konflik prasyarat / SKS / paritas
note over X, G: Tidak ada panggilan /api/chat atau /api/chat/stream di alur ini
@enduml
```

Detail yang mudah terlewat:

- `PlannerProvider.addPendingCourse` hanya menambah ke `pendingCourses`; halaman Degree Planner yang memindahkannya ke `plan` aktif.
- `useDegreeDrafts.setPlan` menaikkan `revision`, menandai `pending`, lalu menjadwalkan flush. Bila revisi baru masuk sebelum flush selesai, flush berikutnya dikirim ulang.
- `POST /api/v1/plans/validations` dipanggil eksplisit dari tombol validasi dengan `AbortController`, bukan otomatis saat menyimpan.
- Jika salinan server berbeda dengan draf lokal, `PlanConflictDialog` muncul sebelum timpa atau muat versi server.

## 4. Indeks endpoint web (tanpa chat)

Semua path di bawah tersedia di `/api/v1/*`; `backend/app.py` memasang router yang sama di `/api/*` untuk backward compatibility.

| Domain | Method + path | Pemakai di frontend |
|---|---|---|
| Health | `GET /health` | Status gateway, DB, dan layanan eksternal |
| Auth | `POST /auth/login`, `POST /auth/register`, `POST /auth/recover`, `POST /auth/change-password`, `GET /auth/me`, `PATCH /auth/me/profile` | `LoginPage`, `authService`, `ProfilePage` |
| Admin accounts | `GET /admin/accounts`, `POST /admin/accounts`, `PATCH /admin/accounts/{user_id}` | `AdminAccounts` di `App.tsx` |
| Academic period | `GET /academic-periods/current` | `AcademicPeriodProvider`, header aplikasi |
| Courses | `GET /courses`, `GET /courses/search`, `GET /courses/{code}`, `POST /admin/courses`, `PUT /admin/courses/{course_id}`, `DELETE /admin/courses/{course_id}` | `fetchCatalog`, `CourseFinder`, `CourseFormModal` |
| Dashboard | `GET /dashboard/me` | `useDashboardData` |
| Notifications | `GET /notifications/me`, `PATCH /notifications/{id}/read`, `POST /notifications/mark-all-read` | `NotificationDropdown` |
| Polling | `GET /polling/periods/active`, `GET /polling/my-votes`, `POST /polling/votes`, `DELETE /polling/votes/{course_id}`, `GET /polling/demand-analytics`, `GET /admin/polling/demand-analytics` | `PollingProvider`, `useDemandAnalytics` |
| Degree plans | `GET /degree-plans`, `POST /degree-plans`, `GET /degree-plans/catalog`, `PUT /degree-plans/{id}/items`, `PATCH /degree-plans/{id}`, `DELETE /degree-plans/{id}` | `degreePlanService`, `useDegreeDrafts` |
| Validation | `POST /plans/validations`, `POST /plans` | `planValidationService`, tombol validasi planner |
| Schedule | `GET /class-sections`, `POST /class-sections/validations` | `classSectionService` |
| Records | `GET /me/course-records`, `POST /me/course-records`, `DELETE /me/course-records/{id}` | `courseRecordService` |

Dua endpoint chat (`POST /chat`, `POST /chat/stream`) dan `DELETE /chat/sessions/{id}` memang terdaftar di gateway yang sama, tetapi tidak dipanggil oleh alur di dokumen ini.
