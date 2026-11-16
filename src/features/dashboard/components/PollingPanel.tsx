import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  ChevronRight,
  Download,
  Filter,
  Flame,
  GraduationCap,
  Sparkles,
  Users,
} from "lucide-react"
import type { AuthUser } from "@/features/auth/authService"
import type {
  CourseDemandItem,
  DemandAnalyticsResponse,
  PollingPeriod,
  StudentVote,
} from "@/features/polling/pollingService"

interface PollingPanelProps {
  user: AuthUser | null
  studentVotes: StudentVote[]
  pollingPeriod: PollingPeriod | null
  onNavigate: (page: string) => void
  selectedProdi: string
  setSelectedProdi: (value: string) => void
  items: CourseDemandItem[]
  demandAnalytics: DemandAnalyticsResponse | undefined
  isLoadingAnalytics: boolean
  handleExportCSV: () => void
}

export default function PollingPanel({
  user,
  studentVotes,
  pollingPeriod,
  onNavigate,
  selectedProdi,
  setSelectedProdi,
  items,
  demandAnalytics,
  isLoadingAnalytics,
  handleExportCSV,
}: PollingPanelProps) {
  return (
    <>
      {user?.role === "student" ? (
        <div className="bg-surface rounded-xl border border-border shadow-sm overflow-hidden space-y-4 p-5">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-border/70 pb-4">
            <div className="flex items-start gap-3">
              <div className="p-2.5 rounded-xl bg-gold/15 text-navy flex-shrink-0">
                <Sparkles className="w-5 h-5 text-gold" />
              </div>
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="font-heading font-bold text-lg text-navy">
                    Status Partisipasi Polling Pre-KRS Saya
                  </h3>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-gold/15 text-navy border border-gold/30">
                    {pollingPeriod
                      ? `Semester ${
                          pollingPeriod.term === "genap" ? "Genap" : "Ganjil"
                        } ${pollingPeriod.academic_year}`
                      : "Periode belum tersedia"}
                  </span>
                </div>
                <p className="text-xs text-muted mt-0.5">
                  {pollingPeriod
                    ? `Pilihlah hingga ${pollingPeriod.max_votes_per_student} mata kuliah pilihan untuk menentukan pembukaan kelas pada semester mendatang.`
                    : "Periode polling belum tersedia."}
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={() => onNavigate("course-finder")}
              className="h-9 px-4 rounded-lg bg-navy hover:bg-navy-light text-white text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer shadow-xs self-start md:self-center"
            >
              <span>Pilih MK di Course Finder</span>
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          {studentVotes.length === 0 ? (
            <div className="p-6 rounded-xl bg-background border border-dashed border-border text-center space-y-2">
              <p className="text-sm font-semibold text-navy">
                Anda belum memilih mata kuliah pilihan pada periode ini.
              </p>
              <p className="text-xs text-muted max-w-md mx-auto">
                Partisipasi voting Anda sangat penting agar Program Studi dapat
                mengakomodasi kuota dan membuka kelas paralel yang Anda
                butuhkan.
              </p>
              <button
                type="button"
                onClick={() => onNavigate("course-finder")}
                className="mt-2 inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-gold/15 hover:bg-gold/25 text-navy border border-gold/40 text-xs font-semibold transition-colors cursor-pointer"
              >
                Mulai Memilih MK Pilihan
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs text-muted">
                <span>
                  Mata Kuliah Pilihan yang Anda Prioritaskan (
                  {studentVotes.length}/
                  {pollingPeriod?.max_votes_per_student || 3}):
                </span>
                <span className="font-mono text-[11px] text-teal-dark font-medium">
                  Tersimpan di Akun Anda
                </span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {studentVotes.map((v) => (
                  <div
                    key={v.vote_id || v.course_id}
                    className="p-4 rounded-xl bg-background border border-border space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-gold/15 text-navy border border-gold/30">
                        Prioritas {v.priority}
                      </span>
                      <span className="font-mono text-xs font-bold text-navy">
                        {v.course_code || v.course_id}
                      </span>
                    </div>
                    <p className="text-xs font-semibold text-navy line-clamp-2">
                      {v.course_name || v.course_id}
                    </p>
                    <p className="text-[10px] text-muted font-mono">
                      Waktu Vote:{" "}
                      {new Date(v.created_at).toLocaleDateString("id-ID", {
                        day: "numeric",
                        month: "short",
                        year: "numeric",
                      })}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="bg-surface rounded-xl border border-border shadow-sm overflow-hidden space-y-4 p-5">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-border/70 pb-4">
            <div className="flex items-start gap-3">
              <div className="p-2.5 rounded-xl bg-navy/10 text-navy flex-shrink-0">
                <BarChart3 className="w-5 h-5 text-navy" />
              </div>
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="font-heading font-bold text-lg text-navy">
                    Rekap Analitik Peminatan MK Pilihan (Pre-KRS)
                  </h3>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-gold/15 text-navy border border-gold/30">
                    {pollingPeriod
                      ? `Semester ${
                          pollingPeriod.term === "genap" ? "Genap" : "Ganjil"
                        } ${pollingPeriod.academic_year}`
                      : "Periode belum tersedia"}
                  </span>
                  {user?.role && (
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider bg-navy/10 text-navy border border-navy/20">
                      Role: {user.role}
                    </span>
                  )}
                </div>
                <p className="text-xs text-muted mt-0.5">
                  Monitoring kuota real-time dan proyeksi pembukaan kelas untuk
                  Kaprodi &amp; Dosen FTMM UNAIR.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 self-start md:self-center">
              <div className="relative">
                <select
                  value={selectedProdi}
                  onChange={(e) => setSelectedProdi(e.target.value)}
                  className="h-9 pl-8 pr-8 rounded-lg border border-border bg-background text-xs font-semibold text-foreground hover:border-gold focus:border-gold focus:ring-1 focus:ring-gold outline-hidden cursor-pointer appearance-none transition-colors"
                  aria-label="Filter Program Studi Analitik"
                >
                  <option value="all">Semua Prodi FTMM</option>
                  <option value="Teknologi Sains Data">
                    Teknologi Sains Data (TSD)
                  </option>
                  <option value="Rekayasa Nanoteknologi">
                    Rekayasa Nanoteknologi (RN)
                  </option>
                  <option value="Teknik Industri">Teknik Industri (TI)</option>
                  <option value="Teknik Elektro">Teknik Elektro (TE)</option>
                  <option value="TRKB">TRKB</option>
                </select>
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-2.5 text-muted">
                  <Filter className="w-3.5 h-3.5" />
                </div>
              </div>

              <button
                type="button"
                onClick={handleExportCSV}
                disabled={!items.length || isLoadingAnalytics}
                className="h-9 px-3.5 rounded-lg bg-navy hover:bg-navy-light text-white text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer shadow-xs disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Export CSV</span>
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            <div className="p-3 rounded-xl bg-background border border-border">
              <span className="text-muted block text-[11px]">
                Total Mahasiswa Partisipan
              </span>
              <span className="text-xl font-heading font-bold text-navy flex items-center gap-1.5 mt-0.5">
                <Users className="w-4 h-4 text-teal" />
                {demandAnalytics?.total_students_voted || 0}
              </span>
            </div>
            <div className="p-3 rounded-xl bg-background border border-border">
              <span className="text-muted block text-[11px]">
                Mata Kuliah Qualified (&ge; 15)
              </span>
              <span className="text-xl font-heading font-bold text-emerald-700 flex items-center gap-1.5 mt-0.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                {items.filter((i) => i.status === "QUALIFIED").length}
              </span>
            </div>
            <div className="p-3 rounded-xl bg-background border border-border">
              <span className="text-muted block text-[11px]">
                Mata Kuliah Borderline (10–14)
              </span>
              <span className="text-xl font-heading font-bold text-amber-700 flex items-center gap-1.5 mt-0.5">
                <AlertTriangle className="w-4 h-4 text-amber-600" />
                {items.filter((i) => i.status === "BORDERLINE").length}
              </span>
            </div>
            <div className="p-3 rounded-xl bg-background border border-border">
              <span className="text-muted block text-[11px]">
                Total Proyeksi Kelas
              </span>
              <span className="text-xl font-heading font-bold text-navy flex items-center gap-1.5 mt-0.5">
                <GraduationCap className="w-4 h-4 text-gold" />
                {items.reduce((acc, curr) => acc + curr.projected_classes, 0)}{" "}
                Kelas
              </span>
            </div>
          </div>

          <div className="overflow-x-auto border border-border rounded-xl">
            <table className="w-full text-left text-xs">
              <thead className="bg-background text-muted uppercase font-mono text-[10px] tracking-wider border-b border-border">
                <tr>
                  <th className="px-3.5 py-3 font-semibold">Kode MK</th>
                  <th className="px-3.5 py-3 font-semibold">Mata Kuliah</th>
                  <th className="px-3.5 py-3 font-semibold">Prodi</th>
                  <th className="px-3.5 py-3 font-semibold text-center">SKS</th>
                  <th className="px-3.5 py-3 font-semibold text-center">
                    Total Peminat
                  </th>
                  <th className="px-3.5 py-3 font-semibold text-center">
                    Prioritas 1
                  </th>
                  <th className="px-3.5 py-3 font-semibold text-center">
                    Status
                  </th>
                  <th className="px-3.5 py-3 font-semibold text-center">
                    Proyeksi Kelas
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60 font-sans">
                {items.length === 0 ? (
                  <tr>
                    <td
                      colSpan={8}
                      className="px-4 py-8 text-center text-muted"
                    >
                      Tidak ada data analitik untuk filter prodi ini.
                    </td>
                  </tr>
                ) : (
                  items.map((row) => (
                    <tr
                      key={row.course_id}
                      className="hover:bg-background/60 transition-colors"
                    >
                      <td className="px-3.5 py-3 font-mono font-bold text-navy">
                        {row.course_code}
                      </td>
                      <td className="px-3.5 py-3 font-medium text-foreground">
                        {row.course_name}
                      </td>
                      <td className="px-3.5 py-3 text-muted">
                        <span className="inline-block px-1.5 py-0.5 bg-background border border-border rounded font-mono text-[10px]">
                          {row.program_code || row.study_program}
                        </span>
                      </td>
                      <td className="px-3.5 py-3 text-center font-mono">
                        {row.credits}
                      </td>
                      <td className="px-3.5 py-3 text-center">
                        <span className="font-bold font-mono text-navy inline-flex items-center gap-1">
                          <Flame className="w-3.5 h-3.5 text-orange" />
                          {row.total_votes}
                        </span>
                      </td>
                      <td className="px-3.5 py-3 text-center font-mono font-semibold text-navy">
                        {row.priority_1_votes}
                      </td>
                      <td className="px-3.5 py-3 text-center">
                        {row.status === "QUALIFIED" && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-emerald-100 text-emerald-800 border border-emerald-200">
                            QUALIFIED
                          </span>
                        )}
                        {row.status === "BORDERLINE" && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-amber-100 text-amber-800 border border-amber-200">
                            BORDERLINE
                          </span>
                        )}
                        {row.status === "UNQUALIFIED" && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-red-100 text-red-800 border border-red-200">
                            UNQUALIFIED
                          </span>
                        )}
                      </td>
                      <td className="px-3.5 py-3 text-center">
                        <span className="font-mono font-bold text-navy px-2 py-0.5 rounded bg-background border border-border">
                          {row.projected_classes > 0
                            ? `${row.projected_classes} Kelas`
                            : "-"}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  )
}
