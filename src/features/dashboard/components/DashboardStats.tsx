import {
  Award,
  BookOpen,
  Calendar,
  CheckCircle2,
  Clock,
  GraduationCap,
  TrendingUp,
  Users,
} from "lucide-react"
import type { DashboardMeResponse } from "@/features/dashboard/dashboardService"
import type { PollingPeriod } from "@/features/polling/pollingService"
import type { AcademicPeriod } from "@/shared/academic-period/academicService"

interface DashboardStatsProps {
  dashboardData: DashboardMeResponse | null
  pollingPeriod: PollingPeriod | null
  period: AcademicPeriod | null
}

export default function DashboardStats({
  dashboardData,
  pollingPeriod,
  period,
}: DashboardStatsProps) {
  return (
    <>
      {dashboardData?.stats?.type === "lecturer" ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-surface rounded-xl p-5 border border-border shadow-sm flex flex-col relative overflow-hidden group">
            <div className="absolute -right-6 -top-6 w-24 h-24 bg-navy-light/10 rounded-full blur-2xl group-hover:bg-navy-light/20 transition-colors" />
            <h3 className="text-muted text-xs font-medium mb-1 flex items-center gap-2">
              <BookOpen className="w-3.5 h-3.5 text-navy" /> Mata Kuliah Diampu
            </h3>
            <div className="flex items-end gap-2 mt-2">
              <span className="text-3xl font-heading font-bold text-navy">
                {dashboardData.stats.courses_taught}
              </span>
              <span className="text-muted text-xs mb-1">Matakuliah</span>
            </div>
            <p className="text-[10px] text-muted mt-3 font-mono">
              3 Kelas Paralel Aktif
            </p>
          </div>

          <div className="bg-surface rounded-xl p-5 border border-border shadow-sm flex flex-col relative overflow-hidden group">
            <div className="absolute -right-6 -top-6 w-24 h-24 bg-gold/10 rounded-full blur-2xl group-hover:bg-gold/20 transition-colors" />
            <h3 className="text-muted text-xs font-medium mb-1 flex items-center gap-2">
              <Clock className="w-3.5 h-3.5 text-gold" /> Beban Mengajar (BKD)
            </h3>
            <div className="flex items-end gap-2 mt-2">
              <span className="text-3xl font-heading font-bold text-navy">
                {dashboardData.stats.sks_taught}
              </span>
              <span className="text-muted text-xs mb-1">
                / 12 SKS Standar BKD
              </span>
            </div>
            <div className="w-full bg-border h-1.5 rounded-full mt-3 overflow-hidden">
              <div
                className="bg-gold h-full rounded-full transition-all"
                style={{
                  width: `${Math.min(100, (dashboardData.stats.sks_taught / 12) * 100)}%`,
                }}
              />
            </div>
            <p className="text-[10px] text-muted mt-1.5 font-mono">
              Pemenuhan:{" "}
              {Math.round((dashboardData.stats.sks_taught / 12) * 100)}%
              tridharma pengajaran
            </p>
          </div>

          <div className="bg-surface rounded-xl p-5 border border-border shadow-sm flex flex-col relative overflow-hidden group">
            <div className="absolute -right-6 -top-6 w-24 h-24 bg-teal/10 rounded-full blur-2xl group-hover:bg-teal/20 transition-colors" />
            <h3 className="text-muted text-xs font-medium mb-1 flex items-center gap-2">
              <Users className="w-3.5 h-3.5 text-teal" /> Total Mahasiswa
            </h3>
            <div className="flex items-end gap-2 mt-2">
              <span className="text-3xl font-heading font-bold text-navy">
                {dashboardData.stats.total_students}
              </span>
              <span className="text-muted text-xs mb-1">Mahasiswa</span>
            </div>
            <p className="text-[10px] text-muted mt-3 font-mono">
              Bimbingan Wali: {dashboardData.stats.advisee_students} Mahasiswa
            </p>
          </div>

          <div className="bg-surface rounded-xl p-5 border border-border shadow-sm flex flex-col relative overflow-hidden group">
            <div className="absolute -right-6 -top-6 w-24 h-24 bg-teal-dark/10 rounded-full blur-2xl group-hover:bg-teal-dark/20 transition-colors" />
            <h3 className="text-muted text-xs font-medium mb-1 flex items-center gap-2">
              <Award className="w-3.5 h-3.5 text-teal-dark" /> Status Penugasan
            </h3>
            <div className="flex items-end gap-1.5 mt-2">
              <span className="text-2xl font-heading font-bold text-navy">
                {dashboardData.stats.status}
              </span>
            </div>
            <p className="text-[10px] text-muted mt-3 font-mono">
              Program Studi: Teknologi Sains Data
            </p>
          </div>
        </div>
      ) : dashboardData?.stats?.type === "admin" ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-surface rounded-xl p-5 border border-border shadow-sm flex flex-col relative overflow-hidden group">
            <div className="absolute -right-6 -top-6 w-24 h-24 bg-teal/10 rounded-full blur-2xl group-hover:bg-teal/20 transition-colors" />
            <h3 className="text-muted text-xs font-medium mb-1 flex items-center gap-2">
              <Users className="w-3.5 h-3.5 text-teal" /> Mahasiswa Aktif
            </h3>
            <div className="flex items-end gap-2 mt-2">
              <span className="text-3xl font-heading font-bold text-navy">
                {dashboardData.stats.total_active_students.toLocaleString(
                  "id-ID",
                )}
              </span>
              <span className="text-muted text-xs mb-1">Mahasiswa</span>
            </div>
            <p className="text-[10px] text-muted mt-3 font-mono">
              Tersebar di 5 Program Studi
            </p>
          </div>

          <div className="bg-surface rounded-xl p-5 border border-border shadow-sm flex flex-col relative overflow-hidden group">
            <div className="absolute -right-6 -top-6 w-24 h-24 bg-gold/10 rounded-full blur-2xl group-hover:bg-gold/20 transition-colors" />
            <h3 className="text-muted text-xs font-medium mb-1 flex items-center gap-2">
              <GraduationCap className="w-3.5 h-3.5 text-gold" /> Dosen Pengajar
            </h3>
            <div className="flex items-end gap-2 mt-2">
              <span className="text-3xl font-heading font-bold text-navy">
                {dashboardData.stats.total_lecturers}
              </span>
              <span className="text-muted text-xs mb-1">Dosen</span>
            </div>
            <p className="text-[10px] text-muted mt-3 font-mono">
              Dosen Tetap &amp; LB FTMM
            </p>
          </div>

          <div className="bg-surface rounded-xl p-5 border border-border shadow-sm flex flex-col relative overflow-hidden group">
            <div className="absolute -right-6 -top-6 w-24 h-24 bg-navy-light/10 rounded-full blur-2xl group-hover:bg-navy-light/20 transition-colors" />
            <h3 className="text-muted text-xs font-medium mb-1 flex items-center gap-2">
              <BookOpen className="w-3.5 h-3.5 text-navy" /> Kurikulum &amp; MK
            </h3>
            <div className="flex items-end gap-2 mt-2">
              <span className="text-3xl font-heading font-bold text-navy">
                {dashboardData.stats.total_courses}
              </span>
              <span className="text-muted text-xs mb-1">Mata Kuliah</span>
            </div>
            <p className="text-[10px] text-muted mt-3 font-mono">
              {dashboardData.stats.total_study_programs} Program Studi Aktif
            </p>
          </div>

          <div className="bg-surface rounded-xl p-5 border border-border shadow-sm flex flex-col relative overflow-hidden group">
            <div className="absolute -right-6 -top-6 w-24 h-24 bg-teal-dark/10 rounded-full blur-2xl group-hover:bg-teal-dark/20 transition-colors" />
            <h3 className="text-muted text-xs font-medium mb-1 flex items-center gap-2">
              <Calendar className="w-3.5 h-3.5 text-teal-dark" /> Periode Aktif
            </h3>
            <div className="flex items-end gap-1.5 mt-2">
              <span className="text-xl font-heading font-bold text-navy">
                {pollingPeriod
                  ? `${pollingPeriod.academic_year} ${
                      pollingPeriod.term === "ganjil" ? "Ganjil" : "Genap"
                    }`
                  : "Tidak ada polling aktif"}
              </span>
            </div>
            <p className="text-[10px] text-muted mt-3 font-mono">
              Status: {dashboardData.stats.system_status}
            </p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-surface rounded-xl p-5 border border-border shadow-sm flex flex-col relative overflow-hidden group">
            <div className="absolute -right-6 -top-6 w-24 h-24 bg-teal-light/10 rounded-full blur-2xl group-hover:bg-teal-light/20 transition-colors" />
            <h3 className="text-muted text-xs font-medium mb-1 flex items-center gap-2">
              <BookOpen className="w-3.5 h-3.5 text-teal" /> SKS Ditempuh
            </h3>
            <div className="flex items-end gap-2 mt-2">
              <span className="text-3xl font-heading font-bold text-navy">
                {dashboardData?.stats?.type === "student"
                  ? dashboardData.stats.sks_completed
                  : 0}
              </span>
              <span className="text-muted text-xs mb-1">
                /{" "}
                {dashboardData?.stats?.type === "student"
                  ? dashboardData.stats.sks_target
                  : 0}{" "}
                SKS
              </span>
            </div>
            <div className="w-full bg-border h-1.5 rounded-full mt-3 overflow-hidden">
              <div
                className="bg-teal h-full rounded-full transition-all"
                style={{
                  width: `${
                    dashboardData?.stats?.type === "student"
                      ? dashboardData.stats.completion_percentage
                      : 0
                  }%`,
                }}
              />
            </div>
            <p className="text-[10px] text-muted mt-1.5 font-mono">
              {dashboardData?.stats?.type === "student"
                ? `${dashboardData.stats.completion_percentage.toFixed(1)}% selesai`
                : ""}
            </p>
          </div>

          <div className="bg-surface rounded-xl p-5 border border-border shadow-sm flex flex-col relative overflow-hidden group">
            <div className="absolute -right-6 -top-6 w-24 h-24 bg-gold/10 rounded-full blur-2xl group-hover:bg-gold/20 transition-colors" />
            <h3 className="text-muted text-xs font-medium mb-1 flex items-center gap-2">
              <Clock className="w-3.5 h-3.5 text-gold" /> Semester Aktif
            </h3>
            <div className="flex items-end gap-2 mt-2">
              <span className="text-3xl font-heading font-bold text-navy">
                {dashboardData?.stats?.type === "student"
                  ? dashboardData.stats.current_semester
                  : 0}
              </span>
              <span className="text-muted text-xs mb-1">
                {dashboardData?.stats?.type === "student"
                  ? (period?.term_label ?? "")
                  : ""}
              </span>
            </div>
            <p className="text-[10px] text-muted mt-3 font-mono">
              Status: Mahasiswa Aktif
            </p>
          </div>

          <div className="bg-surface rounded-xl p-5 border border-border shadow-sm flex flex-col relative overflow-hidden group">
            <div className="absolute -right-6 -top-6 w-24 h-24 bg-navy-light/5 rounded-full blur-2xl group-hover:bg-navy-light/10 transition-colors" />
            <h3 className="text-muted text-xs font-medium mb-1 flex items-center gap-2">
              <CheckCircle2 className="w-3.5 h-3.5 text-navy-light" />{" "}
              Direncanakan
            </h3>
            <div className="flex items-end gap-2 mt-2">
              <span className="text-3xl font-heading font-bold text-navy">
                {dashboardData?.stats?.type === "student"
                  ? dashboardData.stats.courses_planned
                  : 0}
              </span>
              <span className="text-muted text-xs mb-1">Matakuliah</span>
            </div>
            <p className="text-[10px] text-muted mt-3 font-mono">
              Total:{" "}
              {dashboardData?.stats?.type === "student"
                ? dashboardData.stats.sks_planned
                : 0}{" "}
              SKS
            </p>
          </div>

          <div className="bg-surface rounded-xl p-5 border border-border shadow-sm flex flex-col relative overflow-hidden group">
            <div className="absolute -right-6 -top-6 w-24 h-24 bg-teal/10 rounded-full blur-2xl group-hover:bg-teal/20 transition-colors" />
            <h3 className="text-muted text-xs font-medium mb-1 flex items-center gap-2">
              <TrendingUp className="w-3.5 h-3.5 text-teal-dark" /> IPK
              Kumulatif
            </h3>
            <div className="flex items-end gap-1.5 mt-2">
              <span className="text-3xl font-heading font-bold text-navy">
                {dashboardData?.stats?.type === "student"
                  ? dashboardData.stats.gpa.toFixed(2)
                  : "0.00"}
              </span>
              <span className="text-muted text-xs mb-1">/ 4.00</span>
            </div>
            <div className="w-full bg-border h-1.5 rounded-full mt-3 overflow-hidden">
              <div
                className="bg-teal h-full rounded-full"
                style={{
                  width: `${
                    dashboardData?.stats?.type === "student"
                      ? (dashboardData.stats.gpa / 4.0) * 100
                      : 0
                  }%`,
                }}
              />
            </div>
            <p className="text-[10px] text-muted mt-1.5 font-mono">
              Predikat:{" "}
              {dashboardData?.stats?.type === "student"
                ? dashboardData.stats.predicate
                : "Dengan Pujian (Cumlaude)"}
            </p>
          </div>
        </div>
      )}
    </>
  )
}
