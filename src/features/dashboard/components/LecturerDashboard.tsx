import { RefreshCw } from "lucide-react"
import { cn } from "@/shared/utils"
import type {
  DashboardAssignedClass,
  DashboardMeResponse,
  DashboardScheduleItem,
  LecturerDashboardStats,
} from "@/features/dashboard/dashboardService"

interface LecturerDashboardProps {
  dashboardData: DashboardMeResponse | null
  isLoading: boolean
  error: string | null
  retry: () => void
  onNavigate: (page: string) => void
}

const dateFormatter = new Intl.DateTimeFormat("id-ID", {
  weekday: "long",
  day: "numeric",
  month: "long",
  year: "numeric",
})

const deadlineFormatter = new Intl.DateTimeFormat("id-ID", {
  dateStyle: "long",
  timeStyle: "short",
})

const actionClass =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border px-4 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"

function ScheduleState({ state }: { state: "draft" | "final" }) {
  return (
    <span
      className={cn(
        "inline-flex w-fit items-center rounded-md border px-2 py-1 text-xs font-semibold",
        state === "final"
          ? "border-teal/50 bg-teal/15 text-navy"
          : "border-gold/40 bg-gold/10 text-navy",
      )}
    >
      {state === "final" ? "Final" : "Draf"}
    </span>
  )
}

function ScheduleRow({ item }: { item: DashboardScheduleItem }) {
  return (
    <li className="flex flex-col gap-3 px-4 py-4 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="font-mono text-sm font-semibold text-navy">
            {item.course_code}
          </span>
          <span className="text-sm font-semibold text-foreground">
            Kelas {item.class_name || "-"}
          </span>
          <span className="text-xs text-muted">{item.credits} SKS</span>
        </div>
        <p className="mt-1 text-sm font-medium text-foreground">
          {item.course_name}
        </p>
        <p className="mt-1 text-xs text-muted">
          {item.study_program_codes.length > 0
            ? item.study_program_codes.join(", ")
            : "Program studi belum tersedia"}
        </p>
      </div>
      <div className="flex shrink-0 flex-wrap items-center gap-x-4 gap-y-2 sm:justify-end">
        <div className="text-left sm:text-right">
          <p className="text-xs font-semibold text-muted">{item.day}</p>
          <p className="mt-1 font-mono text-sm font-semibold text-navy">
            {item.start_time} - {item.end_time}
          </p>
          <p className="mt-1 text-xs text-muted">
            {item.room || "Ruang belum ditentukan"}
          </p>
        </div>
        <ScheduleState state={item.schedule_state} />
      </div>
    </li>
  )
}

function ScheduleSection({
  id,
  title,
  description,
  items,
  emptyMessage,
}: {
  id: string
  title: string
  description: string
  items: DashboardScheduleItem[]
  emptyMessage: string
}) {
  return (
    <section
      aria-labelledby={id}
      className="overflow-hidden rounded-xl border border-border bg-surface"
    >
      <div className="border-b border-border px-4 py-4">
        <h2 id={id} className="font-heading text-lg font-bold text-navy">
          {title}
        </h2>
        <p className="mt-1 text-sm text-muted">{description}</p>
      </div>
      {items.length > 0 ? (
        <ul className="divide-y divide-border">
          {items.map((item) => (
            <ScheduleRow key={item.id} item={item} />
          ))}
        </ul>
      ) : (
        <p className="px-4 py-6 text-sm text-muted">{emptyMessage}</p>
      )}
    </section>
  )
}

function UnscheduledClass({ item }: { item: DashboardAssignedClass }) {
  return (
    <li className="px-4 py-4">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="font-mono text-sm font-semibold text-navy">
          {item.course_code}
        </span>
        <span className="text-sm font-semibold text-foreground">
          Kelas {item.class_name || "-"}
        </span>
        <span className="text-xs text-muted">{item.credits} SKS</span>
      </div>
      <p className="mt-1 text-sm font-medium text-foreground">
        {item.course_name}
      </p>
      <p className="mt-1 text-xs text-muted">
        {item.study_program_codes.length > 0
          ? item.study_program_codes.join(", ")
          : "Program studi belum tersedia"}
      </p>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted">
          Belum memiliki hari, jam, dan ruang.
        </p>
        <ScheduleState state={item.schedule_state} />
      </div>
    </li>
  )
}

function PreferencePanel({
  preference,
  onNavigate,
}: {
  preference: DashboardMeResponse["preference"]
  onNavigate: (page: string) => void
}) {
  const filled = preference?.status === "filled"
  const deadline = preference?.deadline
    ? deadlineFormatter.format(new Date(preference.deadline))
    : null

  return (
    <section
      aria-labelledby="lecturer-preference-title"
      className="rounded-xl border border-border bg-surface p-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2
            id="lecturer-preference-title"
            className="font-heading text-lg font-bold text-navy"
          >
            Preferensi Jadwal
          </h2>
          <p className="mt-1 text-sm text-muted">
            {filled
              ? `${preference?.preferred_count ?? 0} slot preferensi, ${preference?.unavailable_count ?? 0} slot tidak tersedia.`
              : "Preferensi periode aktif belum diisi."}
          </p>
        </div>
        <span
          className={cn(
            "inline-flex w-fit items-center rounded-md border px-2 py-1 text-xs font-semibold",
            filled
              ? "border-teal/50 bg-teal/15 text-navy"
              : "border-gold/40 bg-gold/10 text-navy",
          )}
        >
          {filled ? "Sudah diisi" : "Belum diisi"}
        </span>
      </div>
      <dl className="mt-4 border-t border-border pt-4">
        <dt className="text-xs font-semibold text-muted">
          Deadline preferensi
        </dt>
        <dd className="mt-1 text-sm font-medium text-foreground">
          {deadline || "Deadline belum ditetapkan."}
        </dd>
      </dl>
      <button
        type="button"
        onClick={() => onNavigate("preferences")}
        className={cn(
          actionClass,
          "mt-4 w-full bg-navy text-white hover:bg-navy-light",
        )}
      >
        Atur Preferensi Jadwal
      </button>
    </section>
  )
}

export default function LecturerDashboard({
  dashboardData,
  isLoading,
  error,
  retry,
  onNavigate,
}: LecturerDashboardProps) {
  if (isLoading && !dashboardData) {
    return (
      <section
        role="status"
        aria-live="polite"
        className="rounded-xl border border-border bg-surface p-8"
      >
        <h1 className="font-heading text-2xl font-bold text-navy">
          Dashboard Dosen
        </h1>
        <p className="mt-3 text-sm text-muted">
          Memuat penugasan, jadwal, dan status preferensi Anda...
        </p>
      </section>
    )
  }

  if (error && !dashboardData) {
    return (
      <section
        role="alert"
        className="rounded-xl border border-orange/30 bg-orange/10 p-6"
      >
        <h1 className="font-heading text-2xl font-bold text-navy">
          Dashboard Dosen
        </h1>
        <p className="mt-3 text-sm text-foreground">{error}</p>
        <button
          type="button"
          onClick={retry}
          className={cn(
            actionClass,
            "mt-4 border-orange bg-surface text-orange hover:bg-orange/10",
          )}
        >
          <RefreshCw aria-hidden="true" /> Coba lagi
        </button>
      </section>
    )
  }

  const stats =
    dashboardData?.stats.type === "lecturer"
      ? dashboardData.stats as LecturerDashboardStats
      : null
  const todaySchedule = dashboardData?.today_schedule ?? []
  const weekSchedule = dashboardData?.schedule ?? []
  const unscheduled = dashboardData?.unscheduled_classes ?? []
  const assigned = dashboardData?.assigned_classes ?? []
  const todayLabel = dashboardData?.today
    ? dateFormatter.format(new Date(`${dashboardData.today}T00:00:00`))
    : "Hari ini"

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 className="font-heading text-2xl font-bold text-navy">
            Dashboard Dosen
          </h1>
          <p className="mt-1 text-sm text-foreground">
            {dashboardData?.full_name}
          </p>
          {dashboardData?.study_program && (
            <p className="mt-1 text-sm text-muted">
              {dashboardData.study_program}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={retry}
            disabled={isLoading}
            className={cn(
              actionClass,
              "border-border bg-surface text-navy hover:bg-background",
            )}
          >
            <RefreshCw aria-hidden="true" /> Muat ulang
          </button>
          <button
            type="button"
            onClick={() => onNavigate("scheduling")}
            className={cn(
              actionClass,
              "border-border bg-surface text-navy hover:bg-background",
            )}
          >
            Jadwal Bersama
          </button>
        </div>
      </header>

      {error && (
        <div
          role="alert"
          className="flex flex-col gap-3 rounded-xl border border-orange/30 bg-orange/10 p-4 sm:flex-row sm:items-center sm:justify-between"
        >
          <p className="text-sm text-foreground">
            Data terbaru belum dapat dimuat. {error}
          </p>
          <button
            type="button"
            onClick={retry}
            className={cn(
              actionClass,
              "shrink-0 border-orange bg-surface text-orange hover:bg-orange/10",
            )}
          >
            Coba lagi
          </button>
        </div>
      )}

      {stats && (
        <section
          aria-label="Ringkasan penugasan"
          className="grid grid-cols-1 overflow-hidden rounded-xl border border-border bg-surface sm:grid-cols-3"
        >
          {[
            ["Kelas ditugaskan", stats.assigned_classes],
            ["Kelas terjadwal", stats.scheduled_classes],
            ["Belum terjadwal", stats.unscheduled_classes],
          ].map(([label, value]) => (
            <div
              key={label}
              className="border-b border-border px-4 py-4 last:border-b-0 sm:border-b-0 sm:border-r sm:last:border-r-0"
            >
              <p className="text-sm text-muted">{label}</p>
              <p className="mt-1 font-heading text-2xl font-semibold text-navy tabular-nums">
                {value}
              </p>
            </div>
          ))}
        </section>
      )}

      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(20rem,1fr)]">
        <div className="min-w-0 space-y-6">
          <ScheduleSection
            id="lecturer-today-title"
            title="Jadwal Hari Ini"
            description={todayLabel}
            items={todaySchedule}
            emptyMessage="Tidak ada kelas hari ini. Jadwal mingguan tetap tampil di bawah."
          />
          <ScheduleSection
            id="lecturer-week-title"
            title="Jadwal Minggu Ini"
            description={`${weekSchedule.length} sesi pada periode aktif.`}
            items={weekSchedule}
            emptyMessage="Belum ada jadwal minggu ini. Kelas yang ditugaskan tetap tampil di daftar belum terjadwal."
          />
        </div>
        <div className="min-w-0 space-y-6">
          {dashboardData?.preference && (
            <PreferencePanel
              preference={dashboardData.preference}
              onNavigate={onNavigate}
            />
          )}
          <section
            aria-labelledby="lecturer-unscheduled-title"
            className="overflow-hidden rounded-xl border border-border bg-surface"
          >
            <div className="border-b border-border px-4 py-4">
              <h2
                id="lecturer-unscheduled-title"
                className="font-heading text-lg font-bold text-navy"
              >
                Kelas Belum Terjadwal
              </h2>
              <p className="mt-1 text-sm text-muted">
                Penugasan yang menunggu penetapan hari, jam, dan ruang.
              </p>
            </div>
            {unscheduled.length > 0 ? (
              <ul className="divide-y divide-border">
                {unscheduled.map((item) => (
                  <UnscheduledClass key={item.assignment_id} item={item} />
                ))}
              </ul>
            ) : (
              <p className="px-4 py-6 text-sm text-muted">
                {assigned.length === 0
                  ? "Belum ada kelas yang ditugaskan pada periode aktif."
                  : "Semua kelas yang ditugaskan sudah memiliki jadwal."}
              </p>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}
