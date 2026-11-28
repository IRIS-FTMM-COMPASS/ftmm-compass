// Repo package.json sets "type": "module"; load the CommonJS build through createRequire.
import { createRequire } from "node:module"
import { fileURLToPath } from "node:url"

const require = createRequire(import.meta.url)
const path = require("path")
const os = require("node:os")
const { execFileSync } = require("node:child_process")
const __dirname = path.dirname(fileURLToPath(import.meta.url))
const pptxgen = require("/home/primarizki/.npm-global/lib/node_modules/pptxgenjs")
const PptxGenJS = pptxgen.default || pptxgen

const asset = (f) => path.join(__dirname, "assets", f)
const shot = (f) => path.join(__dirname, "assets", "screens", f)

const WHITE = "FFFFFF"
const LIME = "D3FC72"
const ORANGE = "F59E0B"

const DISPLAY = "Inter Heavy"
const LIGHT = "Anantason Light"
const REG = "Anantason"
const BOLD = "Anantason Bold"
const SEMI = "Anantason Semi-Bold"
const WORDMARK = "Helvetica Now Bold"

const TOTAL = 14
const MX = 1.12 // left margin
const CW = 17.76 // content width

const pres = new PptxGenJS()
pres.defineLayout({ name: "DECK", width: 20, height: 11.25 })
pres.layout = "DECK"
pres.author = "Tim FTMM COMPASS"
pres.title = "FTMM Compass"

pres.defineSlideMaster({
  title: "DECK_MASTER",
  objects: [
    {
      image: {
        path: asset("image1.png"),
        x: 0,
        y: 0,
        w: 20,
        h: 11.25,
        altText: "Latar belakang hijau-biru FTMM Compass",
      },
    },
    {
      image: {
        path: asset("image2.png"),
        x: 1.12,
        y: 0.85,
        w: 0.54,
        h: 0.54,
        altText: "Logo FTMM Compass",
      },
    },
    {
      text: {
        text: "FTMM Compass",
        options: {
          x: 1.9,
          y: 0.88,
          w: 5.2,
          h: 0.5,
          fontFace: WORDMARK,
          fontSize: 32,
          color: WHITE,
          bold: true,
          valign: "middle",
          margin: 0,
        },
      },
    },
    {
      text: {
        text: "Tanggal:",
        options: {
          x: 15.3,
          y: 0.95,
          w: 1.7,
          h: 0.4,
          fontFace: SEMI,
          fontSize: 22,
          color: LIME,
          align: "right",
          margin: 0,
        },
      },
    },
    {
      text: {
        text: "November 2026",
        options: {
          x: 17.15,
          y: 0.95,
          w: 2.4,
          h: 0.4,
          fontFace: REG,
          fontSize: 22,
          color: WHITE,
          margin: 0,
        },
      },
    },
  ],
})

// ---------- helpers ----------

function kickerSize(text, override) {
  if (override) return override
  const n = text.length
  if (n <= 14) return 108
  if (n <= 20) return 92
  if (n <= 28) return 78
  return 64
}

function addKicker(slide, text, y = 1.55, size) {
  slide.addText(text, {
    x: MX,
    y,
    w: 17.5,
    h: 2.2,
    fontFace: DISPLAY,
    fontSize: kickerSize(text, size),
    color: WHITE,
    bold: true,
    charSpacing: -4,
    valign: "top",
    margin: 0,
    lineSpacingMultiple: 0.95,
  })
}

function addSubtitle(slide, text, y = 3.85) {
  slide.addText(text, {
    x: MX,
    y,
    w: 16.5,
    h: 1.25,
    fontFace: LIGHT,
    fontSize: 27,
    color: WHITE,
    valign: "top",
    margin: 0,
    lineSpacingMultiple: 1.08,
  })
}

// Glass card; label/num on top, optional title, body, optional status badge.
function addCard(slide, o) {
  const { x, y, w, h } = o
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x,
    y,
    w,
    h,
    rectRadius: 0.14,
    fill: { color: "07120F", transparency: 35 },
    line: { color: WHITE, transparency: 55, width: 1 },
  })

  const pad = 0.38
  const iw = w - pad * 2
  let ty = y + 0.28

  if (o.num) {
    const size = o.numSize || 44
    slide.addText(String(o.num), {
      x: x + pad,
      y: ty,
      w: iw,
      h: size / 72 + 0.12,
      fontFace: BOLD,
      fontSize: size,
      color: o.numColor || LIME,
      bold: true,
      margin: 0,
      valign: "top",
    })
    ty += size / 72 + 0.2
  }

  if (o.badge) {
    const bw = 1.25
    const risk = o.badge === "RISIKO"
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: x + pad,
      y: ty,
      w: bw,
      h: 0.42,
      rectRadius: 0.2,
      fill: risk ? { color: ORANGE } : { color: "07120F", transparency: 45 },
      line: {
        color: risk ? ORANGE : WHITE,
        transparency: risk ? 0 : 45,
        width: 1,
      },
    })
    slide.addText(o.badge, {
      x: x + pad,
      y: ty,
      w: bw,
      h: 0.42,
      fontFace: SEMI,
      fontSize: 16,
      color: WHITE,
      align: "center",
      valign: "middle",
      charSpacing: 1,
      margin: 0,
    })
    ty += 0.62
  }

  if (o.title) {
    const size = o.titleSize || 26
    const titleH = o.titleH || size / 72 + 0.3
    slide.addText(o.title, {
      x: x + pad,
      y: ty,
      w: iw,
      h: titleH,
      fontFace: BOLD,
      fontSize: size,
      color: o.titleColor || WHITE,
      bold: true,
      margin: 0,
      valign: "top",
    })
    ty += titleH + 0.02
  }

  if (o.body) {
    slide.addText(o.body, {
      x: x + pad,
      y: ty,
      w: iw,
      h: Math.max(0.5, y + h - ty - 0.28),
      fontFace: LIGHT,
      fontSize: o.bodySize || 19,
      color: WHITE,
      margin: 0,
      valign: "top",
      lineSpacingMultiple: 1.12,
    })
  }
}

function addShot(slide, file, o) {
  const { x, y, w, h } = o
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: x - 0.12,
    y: y - 0.12,
    w: w + 0.24,
    h: h + 0.24,
    rectRadius: 0.14,
    fill: { color: "07120F", transparency: 72 },
    line: { color: WHITE, transparency: 45, width: 1 },
  })
  slide.addImage({
    path: shot(file),
    x,
    y,
    w,
    h,
    altText: `Tangkapan layar ${file.replace(".png", "")}`,
  })
}

function addTag(slide, label, x, y) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x,
    y: y + 0.05,
    w: 0.05,
    h: 0.28,
    fill: { color: LIME },
    line: { color: LIME, width: 0 },
  })
  slide.addText(label, {
    x: x + 0.16,
    y,
    w: 6.0,
    h: 0.38,
    fontFace: SEMI,
    fontSize: 15,
    color: WHITE,
    bold: true,
    valign: "middle",
    margin: 0,
  })
}

function chrome(slide, n, left = false) {
  slide.addText(`${String(n).padStart(2, "0")} / ${TOTAL}`, {
    x: left ? 1.12 : 17.6,
    y: 10.6,
    w: 1.3,
    h: 0.3,
    fontFace: REG,
    fontSize: 14,
    color: WHITE,
    transparency: 40,
    align: left ? "left" : "right",
    margin: 0,
  })
}

function newSlide(n, notes, under, chromeLeft = false) {
  const slide = pres.addSlide({ masterName: "DECK_MASTER" })
  if (under) under(slide)
  chrome(slide, n, chromeLeft)
  slide.addNotes(notes)
  return slide
}

function bullets(slide, items, o) {
  slide.addText(
    items.map((t) => ({ text: t, options: { bullet: true, breakLine: true } })),
    {
      x: o.x,
      y: o.y,
      w: o.w,
      h: o.h,
      fontFace: LIGHT,
      fontSize: o.size || 21,
      color: WHITE,
      margin: 0,
      valign: "top",
      lineSpacingMultiple: 1.12,
      paraSpaceAfter: 10,
      bullet: { indent: 20 },
    },
  )
}

// ---------- 01 Judul ----------

{
  const s = newSlide(
    1,
    'Buka dengan satu kalimat: "Hari ini saya menunjukkan bagaimana mahasiswa FTMM bisa menyusun rencana studi tanpa menebak." Jangan baca judul.',
    (sl) =>
      sl.addImage({
        path: asset("image4.png"),
        x: 13.8,
        y: 3.2,
        w: 7.8,
        h: 9.0,
        altText: "Pita hijau 3D",
      }),
    true,
  )
  addKicker(s, "FTMM Compass", 2.0)
  s.addText("Satu platform untuk merencanakan studi 8 semester", {
    x: MX,
    y: 4.15,
    w: 12.5,
    h: 2.5,
    fontFace: DISPLAY,
    fontSize: 54,
    color: LIME,
    bold: true,
    charSpacing: -1,
    margin: 0,
    valign: "top",
    lineSpacingMultiple: 0.95,
  })
  s.addText("Katalog, planner, jadwal, dan AI di satu tempat", {
    x: MX,
    y: 6.95,
    w: 12,
    h: 1.0,
    fontFace: LIGHT,
    fontSize: 26,
    color: WHITE,
    margin: 0,
    valign: "top",
    lineSpacingMultiple: 1.08,
  })
  s.addText(
    "Tim FTMM COMPASS, Fakultas Teknologi Maju dan Multidisiplin, UNAIR, November 2026",
    {
      x: MX,
      y: 9.7,
      w: 12.5,
      h: 0.5,
      fontFace: REG,
      fontSize: 20,
      color: WHITE,
      transparency: 20,
      margin: 0,
      valign: "middle",
    },
  )
}

// ---------- 02 Daftar Isi ----------

{
  const s = newSlide(2, "20 detik. Peta jalan, bukan daftar materi.")
  addKicker(s, "Daftar Isi")
  addSubtitle(
    s,
    "Enam bagian: masalah, solusi, fitur, cara pakai, progres, penutup.",
  )

  const items = [
    "Latar Belakang",
    "Solusi",
    "Fitur",
    "Cara Pakai",
    "Progres & Batasan",
    "Penutup",
  ]
  items.forEach((label, i) => {
    const col = i % 2
    const row = Math.floor(i / 2)
    const x = col === 0 ? MX : 10.4
    const y = 5.1 + row * 1.8
    s.addText(String(i + 1).padStart(2, "0"), {
      x,
      y,
      w: 1.4,
      h: 0.9,
      fontFace: BOLD,
      fontSize: 50,
      color: LIME,
      bold: true,
      margin: 0,
      valign: "top",
    })
    s.addText(label, {
      x: x + 1.55,
      y: y + 0.12,
      w: 6.6,
      h: 0.7,
      fontFace: REG,
      fontSize: 28,
      color: WHITE,
      margin: 0,
      valign: "middle",
    })
    s.addShape(pres.shapes.LINE, {
      x,
      y: y + 1.35,
      w: col === 0 ? 8.2 : 7.6,
      h: 0,
      line: { color: WHITE, transparency: 75, width: 1 },
    })
  })
}

// ---------- 03 Dalam Satu Menit ----------

{
  const s = newSlide(
    3,
    "Angka 411 berasal dari katalog database, bukan tebakan. Tekankan: ini bukan mockup, aplikasinya berjalan.",
  )
  addKicker(s, "Dalam Satu Menit")
  addSubtitle(
    s,
    "FTMM Compass menyatukan katalog 5 prodi, 411 mata kuliah, dan planner 8 semester dalam satu platform.",
  )

  const stats = [
    ["5", "Prodi"],
    ["411", "Mata kuliah"],
    ["8", "Semester"],
    ["144", "SKS"],
  ]
  const cw = 4.25
  const gap = (CW - cw * 4) / 3
  stats.forEach(([num, label], i) => {
    const x = MX + i * (cw + gap)
    addCard(s, { x, y: 5.9, w: cw, h: 2.6 })
    s.addText(num, {
      x: x + 0.35,
      y: 6.05,
      w: cw - 0.7,
      h: 1.3,
      fontFace: BOLD,
      fontSize: 72,
      color: LIME,
      bold: true,
      margin: 0,
      valign: "middle",
    })
    s.addText(label, {
      x: x + 0.35,
      y: 7.55,
      w: cw - 0.7,
      h: 0.5,
      fontFace: LIGHT,
      fontSize: 20,
      color: WHITE,
      margin: 0,
      valign: "top",
    })
  })

  s.addText("Dashboard di Fitur 01 memakai akun uji: 44 SKS, IPK 3,78.", {
    x: MX,
    y: 9.15,
    w: 17,
    h: 0.45,
    fontFace: SEMI,
    fontSize: 18,
    color: LIME,
    bold: true,
    margin: 0,
    valign: "middle",
  })
}

// ---------- 04 Latar Belakang ----------

{
  const s = newSlide(
    4,
    "Beri satu contoh konkret: mahasiswa baru tahu syarat prasyarat setelah KRS dibuka, padahal urutan MK menentukan semester berikutnya.",
  )
  addKicker(s, "Latar Belakang")
  addSubtitle(
    s,
    "Informasi akademik datang terlambat dan tersebar, jadi mahasiswa menyusun KRS dengan menebak.",
  )

  const cards = [
    [
      "01",
      "Terlambat",
      "Silabus, jadwal, dan MK baru tersedia mendekati KRS. Waktu menyusun rencana tinggal hitungan hari.",
    ],
    [
      "02",
      "Tersebar",
      "Informasi ada di silabus PDF, portal akademik, grup angkatan, dan pengalaman senior. Tidak ada satu titik akses.",
    ],
    [
      "03",
      "Tidak terpadu",
      "Belum ada alat yang menggabungkan pencarian MK, jadwal visual, rencana per semester, dan rekomendasi personal.",
    ],
  ]
  const cw = 5.55
  const gap = 0.6
  cards.forEach(([num, title, body], i) => {
    addCard(s, {
      x: MX + i * (cw + gap),
      y: 5.7,
      w: cw,
      h: 3.4,
      num,
      title,
      body,
      bodySize: 19,
    })
  })

  s.addShape(pres.shapes.LINE, {
    x: MX,
    y: 9.45,
    w: CW,
    h: 0,
    line: { color: LIME, width: 2 },
  })
  s.addText(
    [
      { text: "Akibatnya: ", options: { fontFace: SEMI, color: LIME } },
      {
        text: "salah ambil, prasyarat terlewat, jadwal bentrok, dan lulus lebih lama.",
        options: { fontFace: LIGHT, color: WHITE },
      },
    ],
    {
      x: MX,
      y: 9.55,
      w: 15.8,
      h: 0.45,
      fontSize: 20,
      margin: 0,
      valign: "top",
    },
  )
}

// ---------- 05 Solusi ----------

{
  const s = newSlide(
    5,
    "Bedakan dari chatGPT biasa: validasi planner tidak diserahkan ke LLM; aturan kampus dijalankan sebagai kode deterministik.",
  )
  addKicker(s, "Solusi")
  addSubtitle(
    s,
    "Empat alat memakai satu data: katalog, planner, jadwal, dan AI.",
  )

  const cards = [
    ["01", "Katalog resmi", "5 prodi, filter, detail MK, diagram prasyarat."],
    [
      "02",
      "Planner tervalidasi",
      "8 semester; prasyarat, paritas, dan batas SKS dicek deterministik.",
    ],
    [
      "03",
      "Jadwal visual",
      "Bentrok terdeteksi sebelum KRS; kelas dipilih sesuai preferensi.",
    ],
    [
      "04",
      "Compass AI",
      "Menjawab pertanyaan akademik dengan konteks profil dan rencana pengguna.",
    ],
  ]
  const cw = 4.15
  const gap = 0.5
  cards.forEach(([num, title, body], i) => {
    addCard(s, {
      x: MX + i * (cw + gap),
      y: 5.7,
      w: cw,
      h: 3.4,
      num,
      title,
      body,
      bodySize: 18,
      titleColor: LIME,
      titleSize: 24,
    })
  })

  s.addText("Validasi berjalan sebagai kode deterministik.", {
    x: MX,
    y: 9.55,
    w: 17,
    h: 0.5,
    fontFace: SEMI,
    fontSize: 20,
    color: LIME,
    bold: true,
    margin: 0,
    valign: "middle",
  })
}

// ---------- 06 Fitur 01 ----------

{
  const s = newSlide(
    6,
    'Tunjukkan bahwa dashboard memakai data akun nyata (44 SKS, IPK 3,78) dan diagram prasyarat menjawab "MK ini boleh diambil kapan?".',
  )
  addKicker(s, "Fitur 01")
  addSubtitle(
    s,
    "Dashboard dan Course Finder menunjukkan posisi studi dan prasyarat tanpa pindah aplikasi.",
    3.85,
  )
  bullets(
    s,
    [
      "SKS kumulatif, IPK, semester aktif, dan jadwal mingguan dalam satu tampilan.",
      "Katalog 5 prodi dengan filter prodi, semester, SKS, tipe, dan paritas.",
      "Detail MK menampilkan diagram alur prasyarat; satu klik tambah ke planner.",
    ],
    { x: MX, y: 5.05, w: 8.2, h: 2.7, size: 21 },
  )
  addShot(s, "01-dashboard.png", { x: 9.7, y: 4.75, w: 9.3, h: 5.23 })
  addShot(s, "03-course-detail.png", { x: 1.12, y: 8.0, w: 4.4, h: 2.475 })
  addTag(s, "Data akun nyata", 9.7, 10.05)
}

// ---------- 07 Fitur 02 ----------

{
  const s = newSlide(
    7,
    "Tekankan persistensi server: rencana tidak hilang saat browser di-reset atau ganti perangkat.",
  )
  addKicker(s, "Fitur 02")
  addSubtitle(
    s,
    "Degree Planner dan Timetable menyusun 8 semester serta mendeteksi bentrok sebelum KRS.",
    3.85,
  )
  bullets(
    s,
    [
      "Board 8 semester; MK wajib terkunci, MK pilihan bisa diseret.",
      "Validasi otomatis: prasyarat, paritas ganjil/genap, dan batas SKS per IPS.",
      "Sampai 10 skenario tersimpan di server; satu skenario aktif dipakai dashboard.",
      "Jadwal mingguan menandai bentrok dan kelas yang dipilih.",
    ],
    { x: MX, y: 5.05, w: 8.2, h: 2.7, size: 20 },
  )
  addShot(s, "04-degree-planner.png", { x: 9.7, y: 4.75, w: 9.3, h: 5.23 })
  addTag(s, "Validasi otomatis", 9.7, 10.05)

  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 1.12,
    y: 8.0,
    w: 5.4,
    h: 1.95,
    rectRadius: 0.14,
    fill: { color: "07120F", transparency: 55 },
    line: { color: LIME, width: 2 },
  })
  s.addText("Rencana tersimpan di server, bukan localStorage.", {
    x: 1.5,
    y: 7.95,
    w: 4.6,
    h: 1.35,
    fontFace: BOLD,
    fontSize: 21,
    color: LIME,
    margin: 0,
    valign: "middle",
    lineSpacingMultiple: 1.1,
  })
}

// ---------- 08 Fitur 03 ----------

{
  const s = newSlide(
    8,
    "Jujur: di mesin lokal, layanan chatbot sedang offline; UI menampilkan status dan fallback. Fitur tetap dirancang untuk tersambung ke microservice.",
  )
  addKicker(s, "Fitur 03")
  addSubtitle(
    s,
    "Compass AI menyusun rekomendasi; polling membuka kelas yang dipilih mahasiswa.",
    3.85,
  )
  bullets(
    s,
    [
      "Compass AI menjawab pertanyaan akademik dan merekomendasikan KRS.",
      "Jawaban bisa langsung diterapkan ke Degree Planner lewat kartu rencana.",
      "Polling MK pilihan: maksimal 3 vote prioritas per mahasiswa.",
      "Kuorum minimum menentukan kelas pilihan dibuka; fakultas melihat jumlah peminat.",
    ],
    { x: MX, y: 5.05, w: 8.2, h: 2.9, size: 18 },
  )
  addShot(s, "05-compass-ai.png", { x: 9.7, y: 4.75, w: 9.3, h: 5.23 })
  addShot(s, "06-polling.png", { x: 1.12, y: 8.15, w: 4.2, h: 2.36 })
  addTag(s, "Tanya rencana studi", 9.7, 10.05)
}

// ---------- 09 Fitur Pendukung ----------

{
  const s = newSlide(
    9,
    "Audiens mahasiswa cukup tahu bahwa dosen/PJ juga punya alur; jangan masuk detail operasional.",
  )
  addKicker(s, "Fitur Pendukung")
  addSubtitle(
    s,
    "Profil, preferensi, notifikasi, dan peran staf melengkapi alur mahasiswa.",
  )

  const cards = [
    [
      "Akun & profil",
      "Login NIM atau email, JWT, multi-peran (mahasiswa, dosen, PJ, admin).",
    ],
    [
      "Preferensi jadwal",
      "Jam dan hari yang dihindari dipakai saat memilih kelas.",
    ],
    ["Notifikasi", "Perubahan status rencana dan pengumuman akademik."],
    [
      "Peran staf",
      "PJ mengelola ketersediaan MK dan penjadwalan; admin mengelola akun dan katalog.",
    ],
  ]
  const cw = 8.6
  const ch = 2.1
  const gap = 0.35
  cards.forEach(([title, body], i) => {
    const x = MX + (i % 2) * (cw + 0.45)
    const y = 5.35 + Math.floor(i / 2) * (ch + gap)
    addCard(s, { x, y, w: cw, h: ch, title, body, bodySize: 19, titleSize: 24 })
  })
}

// ---------- 10 Cara Pakai ----------

{
  const s = newSlide(10, "Alur ini dipakai mahasiswa setiap awal semester.")
  addKicker(s, "Cara Pakai")
  addSubtitle(s, "Lima langkah dari login sampai rencana tersimpan.")

  const steps = [
    ["01", "Masuk", "NIM atau email institusi."],
    ["02", "Lihat posisi", "Dashboard: SKS, IPK, jadwal, status polling."],
    ["03", "Cari MK", "Filter, baca prasyarat, tambah ke planner."],
    [
      "04",
      "Susun rencana",
      "Drag-and-drop, validasi otomatis, simpan skenario.",
    ],
    ["05", "Tanya & vote", "Compass AI untuk rekomendasi; vote MK pilihan."],
  ]
  const cw = 3.27
  const gap = 0.35
  steps.forEach(([num, title, body], i) => {
    const x = MX + i * (cw + gap)
    addCard(s, { x, y: 5.9, w: cw, h: 4.2 })
    s.addText(num, {
      x: x + 0.35,
      y: 6.15,
      w: cw - 0.7,
      h: 0.75,
      fontFace: BOLD,
      fontSize: 44,
      color: LIME,
      bold: true,
      margin: 0,
      valign: "top",
    })
    s.addText(title, {
      x: x + 0.35,
      y: 7.0,
      w: cw - 0.7,
      h: 0.45,
      fontFace: BOLD,
      fontSize: 21,
      color: WHITE,
      bold: true,
      margin: 0,
      valign: "top",
      lineSpacingMultiple: 1.05,
    })
    s.addText(body, {
      x: x + 0.35,
      y: 7.55,
      w: cw - 0.7,
      h: 1.9,
      fontFace: LIGHT,
      fontSize: 18,
      color: WHITE,
      margin: 0,
      valign: "top",
      lineSpacingMultiple: 1.12,
    })
  })
}

// ---------- 11 Yang Sudah Berjalan ----------

{
  const s = newSlide(
    11,
    "Jangan defensif. Sebut yang sudah: 38 tabel, 73 route, 411 MK, 5 prodi, aplikasi berjalan. Lalu sebut yang belum tanpa dibacakan semua.",
  )
  addKicker(s, "Yang Sudah Berjalan")
  addSubtitle(
    s,
    "Alur inti sudah berjalan. Compass AI dan deploy belum selesai.",
  )

  const rows = [
    ["Katalog & Course Finder", 95],
    ["Dashboard & Jadwal", 90],
    ["Degree Planner", 90],
    ["Polling MK Pilihan", 85],
    ["Peran PJ/Dosen & Admin", 80],
    ["Mobile & aksesibilitas", 70],
    ["Compass AI", 65],
  ]
  const barX = 7.0
  const barW = 9.6
  rows.forEach(([label, pct], i) => {
    const y = 4.95 + i * 0.76
    s.addText(label, {
      x: MX,
      y,
      w: 5.2,
      h: 0.5,
      fontFace: REG,
      fontSize: 20,
      color: WHITE,
      margin: 0,
      valign: "middle",
    })
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: barX,
      y: y + 0.11,
      w: barW,
      h: 0.28,
      rectRadius: 0.14,
      fill: { color: WHITE, transparency: 85 },
      line: { color: WHITE, transparency: 70, width: 1 },
    })
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: barX,
      y: y + 0.11,
      w: (barW * pct) / 100,
      h: 0.28,
      rectRadius: 0.14,
      fill: { color: LIME },
      line: { color: LIME, width: 0 },
    })
    s.addText(`${pct}%`, {
      x: 16.9,
      y,
      w: 1.6,
      h: 0.5,
      fontFace: BOLD,
      fontSize: 20,
      color: WHITE,
      bold: true,
      margin: 0,
      valign: "middle",
    })
  })

  s.addText(
    "Persentase adalah estimasi checklist internal, bukan metrik otomatis.",
    {
      x: MX,
      y: 10.55,
      w: 12,
      h: 0.3,
      fontFace: LIGHT,
      fontSize: 13,
      color: WHITE,
      transparency: 35,
      margin: 0,
      valign: "middle",
    },
  )
}

// ---------- 12 Batasan ----------

{
  const s = newSlide(12, "Sebutkan batasan apa adanya. Jangan sembunyikan 503.")
  addKicker(s, "Batasan")
  addSubtitle(
    s,
    "Compass AI butuh layanan aktif, produk belum publik, evaluasi belum final, dan mobile belum penuh.",
  )

  const cards = [
    [
      "RISIKO",
      "Compass AI",
      "Bergantung pada microservice chatbot + Ollama; jika mati, endpoint mengembalikan 503 dan UI memakai fallback lokal.",
    ],
    [
      "INFO",
      "Deploy",
      "Belum ada URL publik; saat ini berjalan lokal (Vite 8443, FastAPI 8001-8050, PostgreSQL).",
    ],
    [
      "INFO",
      "Evaluasi",
      "Perbandingan RAG/CAG/Hybrid masih berjalan; hasil belum final.",
    ],
    ["INFO", "Mobile", "Cakupan responsif dan aksesibilitas belum penuh."],
  ]
  const cw = 8.6
  const ch = 2.3
  const gap = 0.3
  cards.forEach(([badge, title, body], i) => {
    const x = MX + (i % 2) * (cw + 0.45)
    const y = 5.3 + Math.floor(i / 2) * (ch + gap)
    addCard(s, {
      x,
      y,
      w: cw,
      h: ch,
      badge,
      title,
      body,
      bodySize: 19,
      titleSize: 23,
    })
  })
}

// ---------- 13 Next Steps ----------

{
  const s = newSlide(
    13,
    "Hubungkan dengan batasan slide sebelumnya: setiap batasan punya langkah berikutnya.",
  )
  addKicker(s, "Selanjutnya")
  addSubtitle(s, "Empat langkah berikutnya menuju rilis kampus.")

  const cards = [
    ["01", "Deploy publik", "Domain kampus, HTTPS, monitoring."],
    ["02", "Finalisasi evaluasi", "Benchmark RAG/CAG/Hybrid dan paper."],
    ["03", "UAT mahasiswa", "Uji alur nyata dan ukur SUS."],
    [
      "04",
      "Perluas mobile & integrasi",
      "Aksesibilitas, responsif, integrasi SIAKAD.",
    ],
  ]
  s.addShape(pres.shapes.LINE, {
    x: MX,
    y: 5.62,
    w: 18.1,
    h: 0,
    line: { color: LIME, transparency: 40, width: 1 },
  })

  const cw = 4.15
  const gap = 0.5
  cards.forEach(([num, title, body], i) => {
    addCard(s, {
      x: MX + i * (cw + gap),
      y: 5.9,
      w: cw,
      h: 3.4,
      num,
      numSize: 40,
      title,
      titleSize: 22,
      titleH: 1.15,
      body,
      bodySize: 17,
    })
  })
}

// ---------- 14 Penutup ----------

{
  const s = newSlide(
    14,
    'Slide ini bertahan saat Q&A. Ajakan: "Silakan dicoba di lingkungan lokal; kami terbuka pada masukan alur."',
    (sl) =>
      sl.addImage({
        path: asset("image4.png"),
        x: 14.6,
        y: 5.2,
        w: 7.2,
        h: 8.3,
        altText: "Pita hijau 3D",
      }),
    true,
  )
  addKicker(s, "Penutup", 1.55, 92)
  s.addText("Satu platform, satu data, rencana yang dicek sebelum KRS.", {
    x: MX,
    y: 3.85,
    w: 12.5,
    h: 1.0,
    fontFace: LIGHT,
    fontSize: 26,
    color: WHITE,
    margin: 0,
    valign: "top",
  })

  const takeaways = [
    "FTMM Compass menyatukan katalog, planner, jadwal, dan AI.",
    "Validasi prasyarat, paritas, dan SKS berjalan deterministik.",
    "Alur inti berjalan; AI dan deploy menyusul.",
  ]
  takeaways.forEach((text, i) => {
    const y = 5.2 + i * 1.1
    s.addText(String(i + 1), {
      x: MX,
      y,
      w: 0.6,
      h: 0.85,
      fontFace: BOLD,
      fontSize: 30,
      color: LIME,
      bold: true,
      margin: 0,
      valign: "top",
    })
    s.addText(text, {
      x: MX + 0.75,
      y: y + 0.04,
      w: 11.4,
      h: 1.0,
      fontFace: LIGHT,
      fontSize: 24,
      color: WHITE,
      margin: 0,
      valign: "top",
      lineSpacingMultiple: 1.1,
    })
  })

  s.addText("Terima kasih", {
    x: MX,
    y: 8.9,
    w: 8,
    h: 0.75,
    fontFace: BOLD,
    fontSize: 40,
    color: LIME,
    bold: true,
    margin: 0,
    valign: "middle",
  })
  s.addText("Tim FTMM COMPASS, FTMM UNAIR, November 2026", {
    x: MX,
    y: 9.75,
    w: 12,
    h: 0.4,
    fontFace: REG,
    fontSize: 18,
    color: WHITE,
    transparency: 25,
    margin: 0,
    valign: "middle",
  })
}

const DECK = path.join(__dirname, "FTMM-Compass-Deck.pptx")
const PYTHON =
  process.env.PYTHON || (process.platform === "win32" ? "python" : "python3")
const SOFFICE = process.env.SOFFICE || "soffice"

async function main() {
  const file = await pres.writeFile({ fileName: DECK })
  console.log(`Wrote ${file}`)

  execFileSync(PYTHON, [path.join(__dirname, "embed_fonts.py")], {
    stdio: "inherit",
  })

  const profile = path.join(os.tmpdir(), `ftmm-deck-lo-${process.pid}`)
  execFileSync(
    SOFFICE,
    [
      "--headless",
      `-env:UserInstallation=file://${profile}`,
      "--convert-to",
      "pdf",
      "--outdir",
      __dirname,
      DECK,
    ],
    { stdio: "inherit" },
  )
  console.log(`Wrote ${path.join(__dirname, "FTMM-Compass-Deck.pdf")}`)
}

main().catch((error) => {
  console.error(`[ERROR] ${error.message}`)
  process.exit(1)
})
