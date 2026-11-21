import {
  Activity,
  AlertTriangle,
  BookOpen,
  Calendar,
  CheckCircle2,
  ChevronRight,
  Database,
  Server,
} from "lucide-react"
import type { AuthUser } from "@/features/auth/authService"
import type {
  AdminDashboardStats,
  DashboardMeResponse,
} from "@/features/dashboard/dashboardService"
import TimetableGrid from "@/shared/timetable/TimetableGrid"
import { TIMETABLE_DAYS, type ScheduleItem } from "@/shared/domain/models"
import type { AcademicPeriod } from "@/shared/academic-period/academicService"

interface DashboardMainPanelProps {
  user: AuthUser | null
  dashboardData: DashboardMeResponse | null
  adminStats: AdminDashboardStats | null
  period: AcademicPeriod | null
  displayedSchedule: ScheduleItem[]
  hasConflict: boolean
  onNavigate: (page: string) => void
}

export default function DashboardMainPanel({
  user,
  dashboardData,
  adminStats,
  period,
  displayedSchedule,
  hasConflict,
  onNavigate,
}: DashboardMainPanelProps) {
  const scheduleStatus =
    dashboardData?.schedule_status &&
    dashboardData.schedule_status !== "Jadwal final"
      ? dashboardData.schedule_status
      : null
  return (
    <>
      {user?.role === "admin" ? (
        <div className="bg-surface rounded-xl border border-border shadow-sm overflow-hidden p-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border/80 pb-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-navy/10 text-navy flex-shrink-0">
                <Activity className="w-5 h-5 text-navy" />
              </div>
              <div>
                <h3 className="font-heading font-bold text-lg text-navy">
                  Monitoring Operasional &amp; Layanan Akademik FTMM
                </h3>
                <p className="text-xs text-muted mt-0.5">
                  Status infrastruktur basis data kurikulum, gateway dual-tier,
                  dan kesiapan sistem 5 program studi.
                </p>
              </div>
            </div>
            <span className="text-xs font-mono text-emerald-800 bg-emerald-100 border border-emerald-300 px-3 py-1 rounded-full flex items-center gap-1.5 font-semibold self-start sm:self-center">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              {dashboardData?.stats.type === "admin"
                ? dashboardData.stats.system_status
                : "Status tidak tersedia"}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="p-4 rounded-xl bg-background border border-border space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-navy flex items-center gap-1.5">
                  <Database className="w-4 h-4 text-gold" />
                  Mahasiswa Aktif
                </span>
                <span className="h-2 w-2 rounded-full bg-teal"></span>
              </div>
              <p className="text-xl font-heading font-bold text-navy">
                {adminStats?.total_active_students ?? 0}
              </p>
              <p className="text-[11px] text-muted">
                Mahasiswa terdaftar pada program studi FTMM.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-background border border-border space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-navy flex items-center gap-1.5">
                  <Server className="w-4 h-4 text-teal" />
                  Dosen
                </span>
                <span className="h-2 w-2 rounded-full bg-teal"></span>
              </div>
              <p className="text-xl font-heading font-bold text-navy">
                {adminStats?.total_lecturers ?? 0}
              </p>
              <p className="text-[11px] text-muted">
                Dosen aktif yang tercatat di basis data.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-background border border-border space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-navy flex items-center gap-1.5">
                  <BookOpen className="w-4 h-4 text-navy-light" />
                  Mata Kuliah Aktif
                </span>
                <span className="h-2 w-2 rounded-full bg-teal"></span>
              </div>
              <p className="text-xl font-heading font-bold text-navy">
                {adminStats?.total_courses ?? 0}
              </p>
              <p className="text-[11px] text-muted">
                {adminStats?.total_study_programs ?? 0} program studi aktif.
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-surface rounded-xl border border-border shadow-sm overflow-hidden">
          <div className="p-5 border-b border-border flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-3">
              <Calendar className="w-5 h-5 text-navy" />
              <h3 className="font-heading font-bold text-lg text-navy">
                {dashboardData?.stats?.type === "lecturer"
                  ? "Jadwal Mengajar Dosen Minggu Ini"
                  : "Jadwal Perkuliahan Minggu Ini"}
              </h3>
              {scheduleStatus && (
                <span
                  role="status"
                  className="inline-flex items-center gap-1.5 whitespace-nowrap shrink-0 px-2 py-0.5 rounded-full text-xs font-medium text-navy bg-gold/10 border border-gold/30"
                >
                  <span
                    aria-hidden="true"
                    className="h-1.5 w-1.5 rounded-full bg-gold"
                  />
                  {scheduleStatus}
                </span>
              )}
              <span className="text-xs font-mono text-muted bg-background border border-border px-2 py-0.5 rounded">
                {period?.label ?? "—"} · {period?.week_label ?? ""}
              </span>
              {hasConflict && (
                <span className="flex items-center gap-1 text-xs font-medium text-danger bg-danger/8 px-2 py-0.5 rounded-full border border-danger/20">
                  <AlertTriangle className="w-3 h-3" /> Bentrok
                </span>
              )}
            </div>
            {user?.role === "student" && (
              <button
                onClick={() => onNavigate("degree-planner")}
                className="min-h-11 min-w-11 px-3 whitespace-nowrap shrink-0 text-sm font-medium text-navy hover:text-gold transition-colors flex items-center gap-1 cursor-pointer"
              >
                Buka di Degree Planner <ChevronRight className="w-4 h-4" />
              </button>
            )}
          </div>

          <TimetableGrid
            schedule={displayedSchedule}
            days={TIMETABLE_DAYS}
            compact
            onNavigate={onNavigate}
          />
        </div>
      )}
    </>
  )
}
