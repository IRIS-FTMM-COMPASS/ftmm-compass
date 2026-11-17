import {
  ArrowRight,
  Award,
  BookOpen,
  Calendar,
  Clock,
  Edit3,
  GraduationCap,
  KeyRound,
  Layers,
  LogOut,
  Phone,
  ShieldCheck,
} from "lucide-react"
import type { AuthUser, StudentProfile } from "@/features/auth/authService"
import type { AcademicPeriod } from "@/shared/academic-period/academicService"
import { isOddSemester, SKS_CAP_BY_IPS } from "@/shared/domain/academics"

interface ProfileBodyProps {
  user: AuthUser | null
  studentProfile: StudentProfile | undefined
  academicId: string
  period: AcademicPeriod | null
  onNavigate: (page: string) => void
  onRequestLogout: () => void
  onEditPreferences: () => void
}

export default function ProfileBody({
  user,
  studentProfile,
  academicId,
  period,
  onNavigate,
  onRequestLogout,
  onEditPreferences,
}: ProfileBodyProps) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2 space-y-6">
        {user?.role === "admin" ? (
          <div className="bg-surface rounded-2xl border border-border shadow-sm p-6 space-y-5">
            <div className="flex items-center justify-between border-b border-border/80 pb-3">
              <h2 className="font-heading font-bold text-lg text-navy flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-gold" />
                Identitas Pengelola Akademik FTMM
              </h2>
              <span className="text-xs font-mono text-muted bg-background px-2 py-0.5 rounded border border-border">
                Sistem Tata Kelola FTMM
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
              <div className="p-3.5 rounded-xl bg-background border border-border">
                <span className="text-xs text-muted block mb-1">
                  Unit Pengelola
                </span>
                <p className="font-semibold text-navy">
                  {user.unit_name || "Sub-Bagian Akademik & Kemahasiswaan FTMM"}
                </p>
                <p className="text-[11px] font-mono text-muted mt-0.5">
                  Kode Unit: FTMM-BAA
                </p>
              </div>

              <div className="p-3.5 rounded-xl bg-background border border-border">
                <span className="text-xs text-muted block mb-1">
                  Fakultas &amp; Kampus
                </span>
                <p className="font-semibold text-navy">
                  Fakultas Teknologi Maju dan Multidisiplin
                </p>
                <p className="text-[11px] text-muted mt-0.5">
                  Gedung Nano Lantai 1, Kampus C Mulyorejo, Surabaya
                </p>
              </div>

              <div className="p-3.5 rounded-xl bg-background border border-border">
                <span className="text-xs text-muted block mb-1">
                  NIP / ID Staf Administrator
                </span>
                <p className="font-semibold text-navy font-mono text-base">
                  {academicId}
                </p>
                <p className="text-[11px] text-muted mt-0.5">
                  Status: Pegawai Aktif UNAIR
                </p>
              </div>

              <div className="p-3.5 rounded-xl bg-background border border-border">
                <span className="text-xs text-muted block mb-1">
                  Lingkup Kewenangan
                </span>
                <p className="font-semibold text-navy text-base">
                  5 Program Studi FTMM
                </p>
                <p className="text-[11px] text-muted mt-0.5 font-mono">
                  TSD · TRKB · RN · TI · TE
                </p>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-navy/5 border border-navy/10 flex items-start gap-3">
              <Layers className="w-5 h-5 text-gold flex-shrink-0 mt-0.5" />
              <div className="text-xs text-navy/90 leading-relaxed">
                <p className="font-semibold text-navy">
                  Cakupan Hak Akses Super Administrator FTMM
                </p>
                <ul className="mt-1 space-y-1 text-muted list-disc list-inside">
                  <li>
                    Manajemen Master Kurikulum &amp; Silabus 5 Program Studi.
                  </li>
                  <li>
                    Monitoring Kuorum &amp; Rekapitulasi Polling MK Pilihan
                    Pre-KRS.
                  </li>
                  <li>
                    Validasi dan Pengawasan Alur Prasyarat Rencana Studi
                    Mahasiswa.
                  </li>
                </ul>
              </div>
            </div>
          </div>
        ) : user?.role === "lecturer" ? (
          <div className="bg-surface rounded-2xl border border-border shadow-sm p-6 space-y-5">
            <div className="flex items-center justify-between border-b border-border/80 pb-3">
              <h2 className="font-heading font-bold text-lg text-navy flex items-center gap-2">
                <GraduationCap className="w-5 h-5 text-gold" />
                Identitas Akademik Dosen FTMM
              </h2>
              <span className="text-xs font-mono text-muted bg-background px-2 py-0.5 rounded border border-border">
                Tenaga Pendidik UNAIR
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
              <div className="p-3.5 rounded-xl bg-background border border-border">
                <span className="text-xs text-muted block mb-1">
                  Program Studi Homebase
                </span>
                <p className="font-semibold text-navy">
                  {user.unit_name || "Teknologi Sains Data"}
                </p>
                <p className="text-[11px] font-mono text-muted mt-0.5">
                  Fakultas Teknologi Maju dan Multidisiplin
                </p>
              </div>

              <div className="p-3.5 rounded-xl bg-background border border-border">
                <span className="text-xs text-muted block mb-1">
                  Fakultas &amp; Kampus
                </span>
                <p className="font-semibold text-navy">
                  Fakultas Teknologi Maju dan Multidisiplin
                </p>
                <p className="text-[11px] text-muted mt-0.5">
                  Kampus C Mulyorejo, Surabaya
                </p>
              </div>

              <div className="p-3.5 rounded-xl bg-background border border-border">
                <span className="text-xs text-muted block mb-1">
                  NIP / NIDN
                </span>
                <p className="font-semibold text-navy font-mono text-base">
                  {academicId}
                </p>
                <p className="text-[11px] text-muted mt-0.5">
                  Homebase: {user.unit_name || "Teknologi Sains Data"}
                </p>
              </div>

              <div className="p-3.5 rounded-xl bg-background border border-border">
                <span className="text-xs text-muted block mb-1">
                  Beban Mengajar Semester Ini
                </span>
                <p className="font-semibold text-navy text-base">
                  3 Mata Kuliah · 9 SKS
                </p>
                <p className="text-[11px] text-muted mt-0.5 font-mono">
                  {period?.label ?? "—"}
                </p>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-navy/5 border border-navy/10 flex items-start gap-3">
              <Award className="w-5 h-5 text-gold flex-shrink-0 mt-0.5" />
              <div className="text-xs text-navy/90 leading-relaxed">
                <p className="font-semibold text-navy">
                  Tugas Pokok Pembimbingan Akademik (Dosen Wali &amp; Pengajar)
                </p>
                <p className="mt-1 text-muted">
                  Melakukan pembimbingan rencana studi mahasiswa perwalian,
                  memverifikasi kepatuhan prasyarat mata kuliah, dan meninjau
                  rekapitulasi kuorum peminatan MK pilihan program studi.
                </p>
              </div>
            </div>
          </div>
        ) : (
          <div className="bg-surface rounded-2xl border border-border shadow-sm p-6 space-y-5">
            <div className="flex items-center justify-between border-b border-border/80 pb-3">
              <h2 className="font-heading font-bold text-lg text-navy flex items-center gap-2">
                <GraduationCap className="w-5 h-5 text-gold" />
                Identitas Akademik FTMM
              </h2>
              <span className="text-xs font-mono text-muted bg-background px-2 py-0.5 rounded border border-border">
                Kurikulum Resmi UNAIR
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
              <div className="p-3.5 rounded-xl bg-background border border-border">
                <span className="text-xs text-muted block mb-1">
                  Program Studi
                </span>
                <p className="font-semibold text-navy">
                  {studentProfile?.study_program ||
                    user?.unit_name ||
                    "Teknologi Sains Data"}
                </p>
                <p className="text-[11px] font-mono text-muted mt-0.5">
                  Kode Prodi: {studentProfile?.program_code || "TSD"}
                </p>
              </div>

              <div className="p-3.5 rounded-xl bg-background border border-border">
                <span className="text-xs text-muted block mb-1">
                  Fakultas &amp; Kampus
                </span>
                <p className="font-semibold text-navy">
                  Fakultas Teknologi Maju dan Multidisiplin
                </p>
                <p className="text-[11px] text-muted mt-0.5">
                  Kampus C Mulyorejo, Surabaya
                </p>
              </div>

              <div className="p-3.5 rounded-xl bg-background border border-border">
                <span className="text-xs text-muted block mb-1">
                  Tahun Angkatan
                </span>
                <p className="font-semibold text-navy font-mono text-base">
                  {studentProfile?.admission_year || 2023}
                </p>
                <p className="text-[11px] text-muted mt-0.5">
                  Kurikulum Berlaku:{" "}
                  {(studentProfile?.admission_year || 2023) <= 2024
                    ? "Kurikulum 2021"
                    : "Kurikulum 2025"}
                </p>
              </div>

              <div className="p-3.5 rounded-xl bg-background border border-border">
                <span className="text-xs text-muted block mb-1">
                  Semester Aktif
                </span>
                <p className="font-semibold text-navy text-base">
                  Semester {studentProfile?.current_semester || 3}
                </p>
                <p className="text-[11px] text-muted mt-0.5 font-mono">
                  {isOddSemester(studentProfile?.current_semester || 3)
                    ? "Term Ganjil"
                    : "Term Genap"}{" "}
                  {period?.academic_year ?? "—"}
                </p>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-navy/5 border border-navy/10 flex items-start gap-3">
              <Award className="w-5 h-5 text-gold flex-shrink-0 mt-0.5" />
              <div className="text-xs text-navy/90 leading-relaxed">
                <p className="font-semibold text-navy">
                  Ketentuan Beban Studi Semester (SOP Akademik FTMM UNAIR)
                </p>
                <p className="mt-1 text-muted">
                  Batas maksimal SKS yang dapat diambil pada semester berikutnya
                  ditentukan oleh Indeks Prestasi Semester (IPS):
                </p>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-2 font-mono text-[11px]">
                  {SKS_CAP_BY_IPS.map((band) => (
                    <span
                      key={band.label}
                      className="bg-surface px-2 py-1 rounded border border-border"
                    >
                      {band.label}: <strong>{band.sks} SKS</strong>
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="bg-surface rounded-2xl border border-border shadow-sm p-6">
          <h2 className="font-heading font-bold text-base text-navy mb-4 flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-teal" />
            Akses Cepat Modul Perencanaan Studi
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <button
              type="button"
              onClick={() => onNavigate("degree-planner")}
              className="p-3.5 rounded-xl border border-border bg-background hover:border-gold/60 text-left transition-all group cursor-pointer"
            >
              <div className="text-xs font-semibold text-navy group-hover:text-gold flex items-center justify-between">
                Degree Planner
                <ArrowRight className="w-3.5 h-3.5 text-muted group-hover:text-gold group-hover:translate-x-0.5 transition-all" />
              </div>
              <p className="text-[11px] text-muted mt-1">
                {user?.role === "admin"
                  ? "Inspeksi kurikulum & master roadmap 8 semester"
                  : user?.role === "lecturer"
                    ? "Tinjau kurikulum mahasiswa bimbingan"
                    : "Atur roadmap 8 semester & jadwal mingguan"}
              </p>
            </button>

            <button
              type="button"
              onClick={() => onNavigate("course-finder")}
              className="p-3.5 rounded-xl border border-border bg-background hover:border-gold/60 text-left transition-all group cursor-pointer"
            >
              <div className="text-xs font-semibold text-navy group-hover:text-gold flex items-center justify-between">
                Course Finder
                <ArrowRight className="w-3.5 h-3.5 text-muted group-hover:text-gold group-hover:translate-x-0.5 transition-all" />
              </div>
              <p className="text-[11px] text-muted mt-1">
                Cari silabus &amp; pohon prasyarat matkul
              </p>
            </button>

            <button
              type="button"
              onClick={() => onNavigate("chatbot")}
              className="p-3.5 rounded-xl border border-border bg-background hover:border-gold/60 text-left transition-all group cursor-pointer"
            >
              <div className="text-xs font-semibold text-navy group-hover:text-gold flex items-center justify-between">
                Compass AI
                <ArrowRight className="w-3.5 h-3.5 text-muted group-hover:text-gold group-hover:translate-x-0.5 transition-all" />
              </div>
              <p className="text-[11px] text-muted mt-1">
                Konsultasi rencana studi cerdas &amp; kurikulum
              </p>
            </button>
          </div>
        </div>
      </div>

      <div className="space-y-6">
        <div className="bg-surface rounded-2xl border border-border shadow-sm p-6 space-y-4">
          <h2 className="font-heading font-bold text-base text-navy flex items-center gap-2 border-b border-border/80 pb-3">
            <ShieldCheck className="w-4 h-4 text-teal" />
            Keamanan &amp; Sesi Aktif
          </h2>

          <div className="space-y-3 text-xs">
            <div className="flex items-start gap-2.5 p-3 rounded-xl bg-background border border-border">
              <KeyRound className="w-4 h-4 text-gold flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-navy">Metode Autentikasi</p>
                <p className="text-muted mt-0.5">
                  {user?.auth_provider ||
                    "Cybercampus Single Sign-On (SSO) UNAIR"}
                </p>
              </div>
            </div>

            <div className="flex items-start gap-2.5 p-3 rounded-xl bg-background border border-border">
              <Clock className="w-4 h-4 text-navy-light flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-navy">Masa Berlaku Token</p>
                <p className="text-muted mt-0.5 font-mono">
                  JWT Session (8 Jam / 28.800 detik)
                </p>
              </div>
            </div>

            <div className="flex items-start gap-2.5 p-3 rounded-xl bg-background border border-border">
              <Calendar className="w-4 h-4 text-teal flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-navy">Status Hak Akses</p>
                <p className="text-muted mt-0.5">
                  Role Terverifikasi:{" "}
                  <span className="font-mono font-semibold text-navy">
                    {user?.role || "student"}
                  </span>
                </p>
              </div>
            </div>
          </div>

          <div className="pt-2 border-t border-border">
            <button
              type="button"
              onClick={onRequestLogout}
              className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-orange hover:bg-orange/90 text-white font-medium text-xs transition-colors cursor-pointer shadow-sm"
            >
              <LogOut className="w-4 h-4" />
              <span>Keluar dari Akun</span>
            </button>
          </div>
        </div>

        <div className="bg-surface rounded-2xl border border-border shadow-sm p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-border/80 pb-3">
            <h2 className="font-heading font-bold text-base text-navy flex items-center gap-2">
              <Phone className="w-4 h-4 text-gold" />
              Kontak &amp; Minat
            </h2>
            <button
              type="button"
              onClick={onEditPreferences}
              className="text-xs text-navy font-semibold hover:text-gold flex items-center gap-1 cursor-pointer"
            >
              <Edit3 className="w-3 h-3" />
              Edit
            </button>
          </div>

          <div className="space-y-3 text-xs">
            <div className="p-3 rounded-xl bg-background border border-border">
              <span className="text-muted block text-[11px] mb-0.5">
                No. Telepon / WhatsApp
              </span>
              <p className="font-mono text-navy font-medium">
                {user?.phone_number || "Belum diatur"}
              </p>
            </div>

            <div className="p-3 rounded-xl bg-background border border-border">
              <span className="text-muted block text-[11px] mb-0.5">
                Bio Singkat
              </span>
              <p className="text-navy leading-relaxed">
                {user?.bio || "Belum ada bio singkat."}
              </p>
            </div>

            {user?.career_interests && user.career_interests.length > 0 && (
              <div className="p-3 rounded-xl bg-background border border-border">
                <span className="text-muted block text-[11px] mb-1.5">
                  Bidang Minat &amp; Karir
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {user.career_interests.map((ci) => (
                    <span
                      key={ci}
                      className="px-2 py-0.5 rounded-md bg-teal/15 text-navy-dark border border-teal/30 text-[10px] font-medium"
                    >
                      {ci}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="bg-warm-bg/70 rounded-2xl border border-border p-5 text-xs text-muted space-y-2">
          <h3 className="font-semibold text-navy">Pusat Dukungan Akademik</h3>
          <p className="leading-relaxed">
            Jika terdapat ketidaksesuaian data identitas resmi, status
            kurikulum, atau NIM/NIP, hubungi Sub-Bagian Akademik FTMM di Gedung
            Nano Lantai 1 atau Helpdesk Cybercampus UNAIR.
          </p>
        </div>
      </div>
    </div>
  )
}
