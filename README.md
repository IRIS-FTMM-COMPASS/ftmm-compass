# FTMM Compass — Academic Advisor & Agentic Study Planner

Academic-advisor web app and AI study planner for **FTMM (Fakultas Teknologi Maju dan Multidisiplin), Universitas Airlangga**.

FTMM Compass helps students plan their degree journey across 8 semesters, explore official course catalogs, visualize prerequisite DAGs, manage weekly class timetables, and consult with **Compass AI** — an agentic study planner that personalizes course roadmaps based on student backgrounds, career interests, and strict FTMM academic constraints.

---

## System Architecture

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                   FTMM COMPASS 3-TIER GATEWAY ARCHITECTURE                     │
└────────────────────────────────────────────────────────────────────────────────┘

 ┌──────────────────────────────────────────────────────────────────────────────┐
 │                     Tier 1: Modular Frontend (React 19)                      │
 │                                                                              │
 │   ┌───────────────┐   ┌────────────────┐   ┌─────────────────────────────┐   │
 │   │   Dashboard   │   │  CourseFinder  │   │        DegreePlanner        │   │
 │   │ (Stats & Grid)│   │ (Detail/Modal/ │   │ (PlannerHeader, Semester-    │  │
 │   └───────────────┘   │ Prerequisite-  │   │ Column, CoursePicker-        │  │
 │                      │ Diagram)       │   │ Modal, ElectiveCourse-       │   │
 │                      └────────────────┘   │ Bank)                        │   │
 │                                          └──────────────▲──────────────┘     │
 │                                                           │                  │
 │                                    [Apply AI Plan] ─────┘                    │
 │                                                           │                  │
 │                                          ┌──────────────┴──────────────┐     │
 │                                          │   Compass AI Chatbot        │     │
 │                                          │ (SSE Stream & Action Cards) │     │
 │                                          └──────────────▲──────────────┘     │
 └───────────────────────────────────────────────────────────┼──────────────────┘
                                                             │
                               Vite Dynamic Proxy (/api/v1/* & /api/* via .backend-port)
                                                             │
 ┌───────────────────────────────────────────────────────────▼──────────────────┐
 │                     Tier 2: Backend Gateway Service (FastAPI)                │
 │                                                                              │
 │   ┌──────────────────────────────────────────────────────────────────────┐   │
 │   │                 Dual-Router Gateway (/api/v1 & /api)                 │   │
 │   │        Chat/stream: 503 saat offline; /plans: fallback lokal         │   │
 │   └───────────────────────┬──────────────────────────────┬───────────────┘   │
 │                           │                              │                   │
 │        [HTTP / SSE Forward /api/v1/chat*]   [Local Engine (/api/v1/plans)]   │
 │                           │                              │                   │
 │                           ▼                              ▼                   │
 │ ┌──────────────────────────────────┐   ┌───────────────────────────────────┐ │
 │ │ Tier 3: AI Microservice (Docker) │   │     Deterministic Tools Layer     │ │
 │ │• Repo: ftmm-compass-chatbot      │   │• Prerequisite DAG Validator       │ │
 │ │• Port: 8000 (repo sibling)       │   │• Semester Parity Validator        │ │
 │ │• Model & embedding: repo sibling │   │• 5-Prodi FTMM Curriculum Loader   │ │
 │ │• RAG-CAG: di repo chatbot        │   │• 8-Semester Plan Synthesizer      │ │
 │ └──────────────────────────────────┘   └───────────────────────────────────┘ │
 └──────────────────────────────────────────────────────────────────────────────┘
```
Komponen yang dirujuk di diagram: `PlannerHeader`, `SemesterColumn`, `CoursePickerModal`, `ElectiveCourseBank`, `PrerequisiteDiagram`. Nama di dalam kotak ASCII dipecah baris agar lebar kotak tetap konsisten.

---

## Key Features

### 1. Dashboard
- Ringkasan statistik akademik dari `/api/v1/dashboard/me`: SKS kumulatif, semester aktif, dan IPK (data PostgreSQL, tanpa angka demo; tampilan kosong bila DB belum di-seed). Angka **Direncanakan** dihitung dari item skenario rencana studi `active` yang belum lulus, bukan dari `record_status='taking'`.
- Widget jadwal mingguan interaktif (*Timetable*) dengan deteksi bentrok jadwal (*conflict highlighting*).

### 2. Course Finder
- Pencarian dan filter katalog mata kuliah berdasarkan prodi, paritas, kategori, ketersediaan, SKS, dan tipe (Wajib/Pilihan). Katalog dibaca dari database lewat `/api/v1/courses`.
- Modal detail mata kuliah dilengkapi **Prerequisite Flow Diagram (SVG)** untuk melihat rantai mata kuliah prasyarat.

### 3. Degree Planner
- Papan visual rencana studi 8 semester (*Roadmap*):
  - Mata kuliah **Wajib** otomatis terkunci di semesternya.
  - Mata kuliah **Pilihan** dapat dipindah-pindah via *drag and drop*.
  - Menegakkan aturan paritas semester (**Ganjil/Odd** $\rightarrow$ Semester 1, 3, 5, 7; **Genap/Even** $\rightarrow$ Semester 2, 4, 6, 8).
  - Mata kuliah yang sudah **lulus** di transkrip (`/api/v1/me/course-records`) tampil terkunci di semester kurikulumnya dan otomatis dikeluarkan dari payload skenario; MK yang sedang ditempuh dapat ditandai selesai (beserta nilai) atau dibatalkan dari modal detail.
- Rencana disimpan di server (`degree_plans` / `degree_plan_items` via `/api/v1/degree-plans`), bukan di `localStorage`: data bertahan setelah ganti perangkat atau membersihkan browser, dan status simpan ditampilkan di header.
- Beberapa skenario rencana per mahasiswa (maksimal 10, satu `active`) dengan aksi salin dan hapus skenario.
- Tab **Jadwal Aktif** untuk melihat distribusi kelas per semester.
- Banner rencana personalisasi saat rencana dari Compass AI diterapkan.

### 4. Compass AI (Agentic Study Planner)
- **Slot-Filling Conversational Flow** (di microservice `ftmm-compass-chatbot`, lihat README sibling): mengumpulkan profil mahasiswa (Prodi, Semester, Riwayat Kelulusan, Minat Karir, Target Kelulusan) melalui percakapan alami.
- **Anti-Assumption Guardrails** (di microservice `ftmm-compass-chatbot`): tidak menebak data mahasiswa yang belum jelas; agen meminta klarifikasi bila data kurang.
- **Deterministic DAG & Parity Validation**: Menguji validitas rencana secara deterministik dengan aturan resmi kurikulum FTMM sebelum diserahkan ke mahasiswa.
- **One-Click UI Transfer**: Hasil rencana studi dilengkapi kartu aksi interaktif **[Terapkan Rencana Ini ke Degree Planner]** yang langsung mengisi papan visual roadmap.

---

## Tech Stack

### Frontend
- **React 19** + **TypeScript 5.7**
- **Vite 8** dev server & production bundler
- **Tailwind CSS v4** via `@tailwindcss/vite` (desain sistem dengan palet Navy, Gold, Teal)
- **Lucide React** untuk icon UI

### Backend & AI Services
- **Python 3.10+** (managed via **[Astral UV](https://docs.astral.sh/uv/)**)
- **FastAPI Gateway** + **Uvicorn** (RESTful API, dynamic port auto-discovery 8001–8050, & CORS; port 8000 dipakai microservice chatbot)
- **HTTPX** (Asynchronous client with timeout; fallback deterministik hanya untuk `/api/v1/plans`, bukan chat/stream)
- **Pydantic v2** (Strict data validation schemas & DegreePlanPayload contracts)
- **AI Microservice (Docker)**: engine RAG-CAG di repo `ftmm-compass-chatbot` (Port 8000; detail model dan embedding di README sibling)
- **Local LLM & Embeddings**: konfigurasi Ollama dan embedding berada di repo `ftmm-compass-chatbot` (Port 11434; lihat `.env.example` sibling)

## Cara Menjalankan Project

> **Panduan Pengembang Lengkap:** Untuk panduan onboarding mendalam, diagnosa toolchain, arsitektur lingkungan pengembang, dan referensi automasi `Makefile`, baca [**`docs/ONBOARDING.md`**](./docs/ONBOARDING.md).

### 1. Prasyarat & Instalasi Toolchain

Sebelum memulai, pastikan perangkat Anda telah terpasang:

1. **Node.js (v22 LTS)**:
   - Unduh dari situs resmi [nodejs.org](https://nodejs.org/) (pilih versi 22 LTS), atau pasang lewat version manager seperti `nvm` / `fnm`.
   - Verifikasi: `node -v` (harus `v22.x.x`).

2. **pnpm (Package Manager Frontend)**:
   - Versi pnpm dipatok di `package.json` (`packageManager: pnpm@10.18.3`). Corepack memakai nilai itu secara otomatis:
     ```bash
     corepack enable pnpm
     ```
   - Atau via npm global (pasang versi yang sama dengan pin):
     ```bash
     npm install -g pnpm@10.18.3
     ```
   - Verifikasi: `pnpm -v` (harus `10.18.3`). Jangan mendeklarasikan versi pnpm di tempat lain (mis. input `version` pada `pnpm/action-setup` di CI); dua nilai yang berbeda membuat action gagal.

3. **Python (v3.10+, direkomendasikan 3.12 sesuai CI) & Astral UV (Package Manager Backend)**:
   - **Python:** Unduh dari [python.org](https://www.python.org/) atau via package manager bawaan OS.
   - **Astral UV** (pengelola virtual environment & paket Python super cepat):
     - *Linux & macOS:*
       ```bash
       curl -LsSf https://astral.sh/uv/install.sh | sh
       ```
     - *Windows (PowerShell):*
       ```powershell
       powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
       ```
     - *Atau via pip / winget:*
       ```bash
       pip install uv
       # atau di Windows:
       winget install astral-sh.uv
       ```
     - Verifikasi: `uv --version`.

4. **Docker Engine & Docker Compose**:
   - Pastikan Docker Daemon aktif untuk PostgreSQL lokal (`make db-up`) atau full stack container (`make docker-up`).

5. **Ollama (Opsional — untuk LLM Lokal)**:
   - Unduh installer dari [ollama.com](https://ollama.com).
   - Model embedding: `ollama pull nomic-embed-text-v2-moe`. Generator default saat ini adalah `ag/gemini-3.8-flash-low` via 9router; fallback Ollama dinonaktifkan secara default (lihat `.env.example` repo sibling).
   - *(Chat/stream memerlukan microservice aktif; bila offline gateway mengembalikan HTTP 503, bukan fallback lokal.)*

6. **AI Chatbot Microservice (Opsional — untuk Inferensi Hybrid RAG-CAG Penuh)**:
   - Microservice AI berjalan di repositori sibling `ftmm-compass-chatbot`:
     ```bash
     cd ../ftmm-compass-chatbot
     # Ingest index kurikulum FAISS (hanya sekali di awal)
     uv run python scripts/ingest_faiss.py
     # Jalankan kontainer Docker
     docker compose up -d
     ```
   - Microservice akan aktif di `http://localhost:8000` dan terhubung langsung ke Ollama host.
   - *(Jika kontainer Docker tidak diaktifkan, endpoint chat/stream mengembalikan HTTP 503. Tidak ada fallback slot-filling di gateway.)*

---

### 2. Quick Start Automasi (`Makefile` — Direkomendasikan)

Jika Anda menggunakan sistem berbasis POSIX (Linux, macOS, atau Windows WSL2), seluruh alur inisialisasi lingkungan pengembang dan eksekusi server dapat dijalankan secara instan via `Makefile`:

```bash
# 1. Setup otomatis: verifikasi toolchain, buat .env, pasang pnpm/uv, jalankan DB; migrasi + seed sudah termasuk
make setup

# 2. Jalankan Frontend & Backend secara bersamaan (Mode Hybrid: DB di Docker, App di host)
make dev
```

Perintah pembantu lainnya:
- `make doctor` — Memeriksa kesiapan toolchain (Node, pnpm, Python, uv, Docker).
- `make db-up` / `make db-down` — Menyalakan/menghentikan container PostgreSQL 16.
- `make db-wait` — Menunggu PostgreSQL siap menerima koneksi sebelum langkah berikutnya.
- `make migrate` — Menjalankan migrasi Alembic skema database ke versi terbaru (`alembic upgrade head`).
- `make seed` — Mengisi database: `seed_full_catalog.py` lalu `seed.py` (urutan ini wajib).
- `make db-reset` — Mereset database dari nol (recreate volume, migrasi Alembic, & seeding).
- `make help` — Menampilkan seluruh daftar perintah automasi yang tersedia.

---

### 3. Dua Mode Menjalankan Aplikasi: Hybrid vs Full Docker

Terdapat dua mode eksekusi yang didukung:

#### Mode A: Hybrid Mode (Sangat Direkomendasikan untuk Daily Coding)
- **Database**: PostgreSQL 16 berjalan di container Docker (`make db-up` atau `docker compose up -d postgres`).
- **Frontend & Backend**: Berjalan langsung di host OS (`make dev` atau `pnpm dev:all`).
- **Keuntungan**:
  - **Hot Module Replacement (Vite HMR) instan (<50 ms)**: setiap perubahan kode frontend maupun backend langsung tersinkronisasi tanpa lag.
  - Sangat hemat RAM (<300 MB).
  - Integrasi LSP, typechecking, dan autocomplete IDE bekerja optimal secara native.

#### Mode B: Full Docker Mode (Untuk QA, Reviewer, atau Deployment Server)
- Menjalankan seluruh stack (`postgres`, `gateway`, dan `frontend`) terisolasi di dalam container Docker (`make docker-up` berjalan di foreground):
  ```bash
  make docker-up
  # atau manual: docker compose up --build
  # varian detached: docker compose up -d --build
  ```
- **Catatan Penting Sinkronisasi Kode**:
  Karena `Dockerfile.backend` dan `Dockerfile.frontend` menyalin (*COPY*) berkas kode sumber ke dalam image saat build time (tanpa host volume bind mount di `docker-compose.yml`), **perubahan kode di host tidak otomatis tersinkronisasi ke dalam kontainer yang sedang berjalan**. Setiap perubahan kode di tengah jalan memerlukan proses rebuild:
  ```bash
  docker compose up -d --build
  # atau hentikan dan nyalakan ulang:
  make docker-down && make docker-up
  ```

---

### 4. Menjalankan Manual (Alternatif Tanpa `Makefile`)

#### A. Menjalankan Sekaligus (Frontend + Backend)
Jalankan perintah berikut untuk mengaktifkan frontend dan backend secara bersamaan lintas OS (Linux, macOS, Windows):

```bash
# 1. Install dependencies frontend
pnpm install

# 2. Sinkronisasi dependencies backend (otomatis membuat venv via uv)
uv sync --directory backend

# 3. Jalankan database PostgreSQL, tunggu siap, migrasi, lalu seed
make db-up db-wait migrate seed
```

### Akun Demo

Buka **`http://localhost:8443`** di browser. Login memakai salah satu akun hasil seeding berikut:

| Role | Email | NIM | Password | Prodi |
| --- | --- | --- | --- | --- |
| student | mahasiswa.tsd@ftmm.unair.ac.id | 164231062 | Mahasiswa2026! | TSD |
| student | mahasiswa.trkb@ftmm.unair.ac.id | 163231062 | Mahasiswa2026! | TRKB |
| student | mahasiswa.rn@ftmm.unair.ac.id | 162231062 | Mahasiswa2026! | RN |
| student | mahasiswa.ti@ftmm.unair.ac.id | 165231062 | Mahasiswa2026! | TI |
| student | mahasiswa.te@ftmm.unair.ac.id | 166231062 | Mahasiswa2026! | TE |
| student | mahasiswa.testing@ftmm.unair.ac.id | 164231001 | Mahasiswa2026! | TSD |
| PJ Prodi / lecturer | pj.tsd@ftmm.unair.ac.id | - | PjProdi2026! | TSD |
| PJ Prodi / lecturer | pj.trkb@ftmm.unair.ac.id | - | PjProdi2026! | TRKB |
| PJ Prodi / lecturer | pj.rn@ftmm.unair.ac.id | - | PjProdi2026! | RN |
| PJ Prodi / lecturer | pj.ti@ftmm.unair.ac.id | - | PjProdi2026! | TI |
| PJ Prodi / lecturer | pj.te@ftmm.unair.ac.id | - | PjProdi2026! | TE |
| admin | admin@ftmm.unair.ac.id | - | AdminFTMM2026! | - |

Identifier menerima NIM atau email. `backend/scripts/seed.py` adalah sumber kebenaran untuk kredensial akun-akun ini.
- Database harus sudah di-migrate dan di-seed (make db-up db-wait migrate seed); make seed menjalankan seed_full_catalog.py lalu seed.py, urutan ini wajib.

```bash
# 4. Jalankan frontend + backend bersamaan
pnpm dev:all
```

- **Cross-Platform**: Menggunakan `concurrently` yang mendukung signal terminate (Ctrl+C) bersih di Linux maupun Windows.
- **Dynamic Port Auto-Discovery**: Backend memindai port kosong pada rentang 8001–8050 (port 8000 disediakan untuk microservice chatbot) dan menuliskan port aktif ke `.backend-port`. Vite dev proxy membaca berkas itu dan meneruskan request `/api` ke port tersebut.

#### B. Menjalankan Terpisah (2 Tab Terminal)
Jika Anda lebih menyukai tab terminal terpisah untuk memantau log masing-masing service:

- **Terminal 1 — Backend FastAPI**:
  ```bash
  pnpm dev:backend
  # atau manual:
  uv run --directory backend python -u app.py
  ```
  Backend aktif di `http://localhost:<PORT>` (Swagger interactive docs di `/docs`).

- **Terminal 2 — Frontend Vite**:
  ```bash
  pnpm dev
  ```
  Vite aktif di `http://localhost:8443`.

*(Opsional)* Jalankan model LLM lokal di terminal terpisah:
```bash
ollama pull nomic-embed-text-v2-moe
# Generator default: ag/gemini-3.8-flash-low via 9router (lihat .env.example repo chatbot)
```

---

### 5. Pengujian Remote Chatbot via Cloudflare Tunnel (Tanpa Backend/LLM Lokal)

Jika rekan tim atau tester ingin menguji respons dan streaming Chatbot AI tanpa perlu menginstal backend FastAPI atau model Ollama lokal:

1. Salin template `.env.example` ke `.env`:
   ```bash
   cp .env.example .env
   ```
2. Masukkan base URL Cloudflare Tunnel yang dibagikan tim backend ke `VITE_API_BASE`:
   ```bash
   VITE_API_BASE=https://<subdomain>.trycloudflare.com
   ```
   *(Kosongkan bila backend berjalan lokal; request `/api` otomatis lewat proxy Vite. Nilai ini hanya base URL, tanpa akhiran endpoint.)*
3. Jalankan frontend:
   ```bash
   pnpm dev
   ```
4. Akses halaman **Compass AI** di `http://localhost:8443`. Indikator status di header otomatis menyala hijau (**Live • `<model>`**), menandakan koneksi langsung ke remote backend tunnel berhasil.

---

### 6. Menjalankan via Docker Compose (Multi-Container `ftmm-network`)

Untuk deployment terisolasi berbasis kontainer atau setup di server/VPS baru:

#### A. Inisialisasi Jaringan Host (Hanya 1x di Server/Host Baru)
```bash
# 1. Buat bridge network eksternal yang dipakai docker-compose.yml
docker network create ftmm-network 2>/dev/null || true
```

#### B. Menjalankan Layanan Kontainer
```bash
# 1. Jalankan Chatbot Microservice (port 8000)
cd ../ftmm-compass-chatbot && docker compose up -d

# 2. Jalankan Gateway (port 8001) dan Frontend UI (port 8443)
# Chatbot memakai network_mode: host, jadi hostname default compose tidak resolvable
export CHATBOT_SERVICE_URL=http://host.docker.internal:8000
cd ../ftmm-compass-ui && docker compose up -d
```

#### C. Verifikasi Konektivitas
- **Frontend Web UI**: `http://localhost:8443`
- **Gateway Health**: `curl -s http://localhost:8001/api/v1/health | jq .` (memverifikasi status `chatbot_service_online: true` dan `ollama_online: true`).
- **Chatbot Direct Health**: `curl -s http://localhost:8000/api/v1/health | jq .`
- **Hentikan Seluruh Layanan**:
  ```bash
  docker compose down && docker compose -f ../ftmm-compass-chatbot/docker-compose.yml down
  ```

---

### 7. Ekspor Peta Alur Web (docu.md — WSL/Linux & Windows)

`docs/web-flow-viewer.md` berisi figur inline (HTML/CSS + PlantUML) yang bisa dibaca langsung lewat ekstensi **docu.md Markdown Viewer** di VS Code/Cursor. Untuk menghasilkan HTML statis tanpa server, gunakan `documd` CLI. Versi paket di-pin ke `6.1.1` (bukan `@latest`) agar render reproducible; `-y` hanya melewati prompt instal. Akses jaringan mencakup npm registry dan aset CSS eksternal (KaTeX) saat render; `playwright install chromium` bila diperlukan adalah unduhan terpisah. Output ditulis ke direktori temp, bukan ke repo, sehingga working tree tetap bersih. Tidak ada kredensial, push, atau perubahan kode aplikasi.

Prasyarat: Node.js v22 (lihat bagian 1). Jika Chrome/Chromium belum tersedia, jalankan sekali `npx -y playwright@latest install chromium` untuk mengunduh biner browser; ini opsional dan bukan bagian dari ekspor.

**WSL/Linux** — deteksi Chromium dari cache Playwright, fallback ke Chrome/Chromium sistem:

```bash
CHROME=$(find "$HOME/.cache/ms-playwright" -type f -path '*/chrome-linux64/chrome' 2>/dev/null | sort -V | tail -n 1)
if [ -z "$CHROME" ]; then CHROME=$(command -v google-chrome || command -v chromium || true); fi
if [ -z "$CHROME" ]; then echo "Jalankan dulu: npx -y playwright@latest install chromium"; exit 1; fi
DOCUMD_CHROME_PATH="$CHROME" npx -y @markdown-viewer/documd@6.1.1 docs/web-flow-viewer.md /tmp/web-flow-viewer.html
```

Buka hasilnya dengan `xdg-open /tmp/web-flow-viewer.html`.

**Windows (PowerShell)** — deteksi Chromium dari `%LOCALAPPDATA%\ms-playwright`, fallback ke Chrome sistem:

```powershell
$chrome = Get-ChildItem "$env:LOCALAPPDATA\ms-playwright" -Filter chrome.exe -Recurse -ErrorAction SilentlyContinue |
  Where-Object { $_.FullName -like '*chrome-win*' } |
  Sort-Object FullName | Select-Object -Last 1 -ExpandProperty FullName
if (-not $chrome) { $chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe" }
if (-not (Test-Path $chrome)) { throw "Jalankan: npx -y playwright@latest install chromium" }
$env:DOCUMD_CHROME_PATH = $chrome
npx -y @markdown-viewer/documd@6.1.1 docs\web-flow-viewer.md "$env:TEMP\web-flow-viewer.html"
```

Buka hasilnya dengan `Invoke-Item "$env:TEMP\web-flow-viewer.html"`.

Verifikasi: CLI mencetak `Rendered ...` dan keluar dengan status `0`; HTML memuat tiga figur tertanam sebagai `data:image/png;base64`. Jalur biner browser diberikan lewat env var `DOCUMD_CHROME_PATH`; di WSL pakai Chromium Linux, bukan biner Chrome Windows di `/mnt/c/...`.

## Testing & QA Audit

Suite backend berjalan terhadap PostgreSQL yang sudah di-migrate. Fixture `tests/conftest.py` menanam pengguna demo sendiri, tetapi tes katalog dan degree-plan membaca katalog 5 prodi, sehingga database harus sudah dijalankan `make seed` (yang menjalankan `seed_full_catalog.py` lalu `seed.py`, urutan ini wajib). CI melakukan urutan yang sama: job `database` memuat schema baseline, menjalankan `alembic upgrade head`, menguji rollback dengan `alembic downgrade -1` lalu upgrade lagi (`ci.yml:101-106`), lalu menjalankan seeder dua kali berturut-turut lewat `python -m scripts.seed` untuk membuktikan idempotensi; setelah itu job `backend` menjalankan `pytest`.

```bash
# ----------------------------------------------------
# A. Menggunakan Makefile (Cepat & Terintegrasi)
# ----------------------------------------------------
make test          # Typecheck TypeScript + suite pytest backend
make lint          # oxfmt + typecheck + Ruff (backend)
make format        # Auto-format frontend via oxfmt (tidak memformat backend)

# ----------------------------------------------------
# B. Perintah Manual / Spesifik Sub-Sistem
# ----------------------------------------------------
# 1. Seed database (idempoten; urutan wajib: katalog 5 prodi dulu, lalu akun/transkrip demo)
make seed

#    Manual untuk urutan yang sama:
uv run --directory backend python -m scripts.seed_full_catalog
uv run --directory backend python -m scripts.seed

# 2. Jalankan seluruh suite backend (domain + endpoint + polling + chat + degree-plan)
uv run --directory backend python -m pytest tests -q

# 3. Jalankan build test & type check frontend
pnpm build

# 4. Verifikasi format code (oxfmt)
pnpm format:check
# atau auto-format in-place:
pnpm format
```

---

## Struktur Direktori

```
ftmm-compass-ui/
├── .github/workflows/ci.yml       # Automated CI pipeline (Node 22 + Python 3.12)
├── Makefile                       # Developer automation interface (setup, dev, db, test)
├── AI_PLANNER_PIPELINE.md         # Dokumentasi detail arsitektur Study Planner Agent
├── DESIGN.md                      # Spesifikasi sistem desain & token visual FTMM
├── Dockerfile.frontend            # Container image definition untuk React + Vite
├── Dockerfile.backend             # Multi-stage container image untuk FastAPI (uv)
├── docker-compose.yml             # Orkestrasi multi-container (ftmm-network)
├── backend/                       # Python FastAPI Backend Gateway
│   ├── README.md                  # Dokumentasi API, setup uv, & arsitektur backend
│   ├── app.py                     # Mount router (/api/v1 kanonik + /api legacy), lifespan, error handler
│   ├── settings.py                # Satu-satunya pembaca environment (DSN, port, Ollama, CORS)
│   ├── database.py                # Engine & session SQLAlchemy untuk koneksi PostgreSQL
│   ├── models.py                  # Pemetaan ORM SQLAlchemy (termasuk degree_plans & degree_plan_items)
│   ├── schemas.py                 # Pydantic v2 data models & payload contracts
│   ├── academics.py               # Batas SKS, total kredit, konversi nilai, parity
│   ├── auth.py                    # Autentikasi pengguna & otorisasi peran
│   ├── catalog.py                 # Pipeline katalog: baca DB → normalisasi → list/get course
│   ├── plan_storage.py            # Persistensi degree-plan & exception domain
│   ├── audit.py                   # Audit trail perubahan data akademik
│   ├── prodi_access.py            # Pembatasan akses data per prodi
│   ├── rate_limit.py              # Pembatasan laju request API
│   ├── stream_control.py          # Kontrol aliran & state respons SSE
│   ├── api/                       # Modul lintas-endpoint (dipasang di /api/v1 dan /api)
│   │   ├── __init__.py            # Marker paket api
│   │   └── errors.py              # Envelope error & handler terpusat
│   ├── features/                  # Router & logika bisnis per domain
│   │   ├── course_records/        # Transkrip mahasiswa: baca, tandai lulus, batalkan
│   │   ├── scheduling/            # Penjadwalan kelas & deteksi bentrok
│   │   ├── planning/              # Degree-plan, planner.py, & prerequisite_validator.py
│   │   ├── catalog/               # Endpoint katalog mata kuliah
│   │   ├── admin/                 # Endpoint administrasi & rekonsiliasi data
│   │   ├── auth/                  # Endpoint login, sesi, & profil
│   │   ├── academic_periods/      # Endpoint periode akademik aktif
│   │   ├── dashboard/             # Endpoint statistik dashboard
│   │   ├── chat/                  # Endpoint chat & stream Compass AI
│   │   ├── polling/               # Endpoint polling & voting
│   │   ├── timetable/             # Endpoint jadwal mingguan
│   │   ├── class_sections/        # Endpoint kelas per mata kuliah
│   │   └── health/                # Endpoint health check gateway
│   ├── scripts/                   # Seed & utilitas katalog (modul Python dijalankan lewat uv run)
│   │   ├── seed.py                # Seed pengguna demo, transkrip, polling, notifikasi
│   │   ├── seed_full_catalog.py   # Seed katalog 5 prodi dari database/seed
│   │   ├── build_catalog.py       # Build data katalog ter-normalisasi dari sumber
│   │   ├── reconcile_catalog.py   # Rekonsiliasi katalog dengan sumber resmi
│   │   └── verify_catalog_sources.py  # Verifikasi konsistensi sumber katalog
│   ├── migrations/                # Revisi Alembic (baseline skema + perubahan berikutnya)
│   ├── pyproject.toml             # Konfigurasi dependensi uv (Astral)
│   ├── uv.lock                    # Deterministic lockfile backend
│   ├── .env.example               # Template konfigurasi environment backend
│   └── tests/                     # Suite pytest (domain, endpoint, polling, chat, degree-plan)
├── src/                           # React 19 + TypeScript + Tailwind v4 SPA
│   ├── app/                       # Shell aplikasi & komposisi global
│   │   ├── App.tsx                # Navigasi halaman & komposisi provider state
│   │   ├── main.tsx               # React DOM entrypoint
│   │   └── components/            # Komponen shell (menu toggle, notifikasi, error boundary)
│   ├── features/                  # Modul per domain bisnis
│   │   ├── auth/                  # LoginPage, authService, session provider
│   │   ├── catalog/               # catalog provider & fetchCatalog()
│   │   ├── dashboard/             # DashboardPage, dashboardService, komponen widget, hooks
│   │   ├── course-finder/         # CourseFinderPage, filter/list/modal, hooks
│   │   ├── polling/               # Polling provider & pollingService
│   │   ├── degree-planner/        # DegreePlannerPage, komponen, services, state planner
│   │   ├── chatbot/               # ChatbotPage, chatService, MarkdownRenderer
│   │   └── profile/               # ProfilePage, header/body/modal, hooks
│   ├── shared/                    # Kode lintas-fitur tanpa dependensi ke features
│   │   ├── api/                   # client.ts & session.ts
│   │   ├── domain/                # models, academics, course, plan, prerequisites, timetable
│   │   ├── academic-period/       # Provider & service periode akademik
│   │   ├── timetable/             # TimetableGrid, ekspor ICS, share URL
│   │   ├── ui/                    # BrandLogo & komponen UI kursus bersama
│   │   └── utils.ts               # cn() class merger helper
│   ├── assets/                    # Logo & aset statis
│   ├── index.css                  # Tailwind v4 @theme design tokens (Navy, Gold, Teal)
│   └── vite-env.d.ts              # Tipe environment Vite
├── database/                      # Canonical Database Baseline V2.1 RC1
│   ├── schema_v2_1_rc1.sql        # PostgreSQL 16+ DDL (38 tabel = 36 baseline + 2 polling, 26 functions, 44 triggers)
│   ├── schema_v2_1_rc1.dbml       # DBML diagram definition
│   ├── seed/                      # Input seed katalog 5 prodi (canonical + reconciliation)
│   └── README.md                  # Ringkasan paket skema database
├── docs/                          # Dokumentasi teknis & onboarding
│   ├── ONBOARDING.md              # Developer Onboarding & Local Setup Guide (Makefile DX)
│   ├── web-flow-viewer.md         # Peta alur web tanpa chatbot (figur inline docu.md)
│   ├── plans/                     # Plan & decision log refactor (low-level, per fase)
│   └── database/                  # Dokumentasi & Audit Skema Database V2.1 RC1
│       ├── DATABASE_SCHEMA_V2_1_RC1.md    # Spesifikasi arsitektur tabel & rule tree
│       ├── SCHEMA_VALIDATION_V2_1_RC1.md  # Laporan 97/97 static release audit checks
│       └── CHANGELOG_V2_TO_V2_1_RC1.md    # Catatan migrasi dari v2 ke v2.1 RC1
├── RANCANGAN DIAGRAM AWAL.sql     # Arsip baseline awal PostgreSQL 16 (v2)
└── SCHEMA_REVIEW.md               # Arsip catatan tinjauan skema v2
```

---

## Database Baseline — V2.1 RC1

`database/schema_v2_1_rc1.sql` adalah canonical baseline PostgreSQL 16+ untuk arsitektur basis data akademik FTMM (**38 tabel — 36 baseline + 2 tabel polling —, 26 fungsi PL/pgSQL, 44 trigger, 2 read views**, dan lulus **97/97 static audit checks**). Dokumentasi lengkap keputusan desain tersedia di [`docs/database/DATABASE_SCHEMA_V2_1_RC1.md`](./docs/database/DATABASE_SCHEMA_V2_1_RC1.md) dan laporan validasinya di [`docs/database/SCHEMA_VALIDATION_V2_1_RC1.md`](./docs/database/SCHEMA_VALIDATION_V2_1_RC1.md).
