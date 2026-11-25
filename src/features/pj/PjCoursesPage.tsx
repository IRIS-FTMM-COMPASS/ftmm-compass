import { useEffect, useState } from "react"
import {
  AlertCircle,
  CheckCircle2,
  Lock,
  RefreshCw,
  Settings2,
} from "lucide-react"
import { useSession } from "@/features/auth/session"
import { usePolling } from "@/features/polling/polling"
import {
  pjService,
  type PjAvailabilityItem,
  type PjAvailabilityMeta,
} from "@/features/polling/pollingService"
import { schedulingService } from "@/features/scheduling/schedulingService"
import { useDemandAnalytics } from "@/features/dashboard/hooks/useDemandAnalytics"
import PollingPanel from "@/features/dashboard/components/PollingPanel"
import PjCourseManageModal from "@/features/pj/components/PjCourseManageModal"
import {
  SortableTh,
  TablePager,
  TableSearchInput,
} from "@/shared/ui/TableControls"
import { useTableControls } from "@/shared/hooks/useTableControls"
import { apiErrorMessage } from "@/shared/api/client"
import { cn } from "@/shared/utils"

interface PjCoursesPageProps {
  onNavigate: (page: string) => void
}

const LOCK_REASON_LABELS: Record<string, string> = {
  semester_berjalan: "Semester berjalan — perubahan terkunci",
  bukan_pilihan: "Bukan MK Pilihan",
  dinonaktifkan: "MK sudah dinonaktifkan",
  prodi_lain: "Dikelola program studi lain",
}

const SCOPE_LABELS: Record<string, string> = {
  program_studi: "Program Studi",
  fakultas: "Fakultas",
  universitas: "Universitas",
}

function lockReasonLabel(reason: string | null | undefined): string {
  if (!reason) return ""
  return LOCK_REASON_LABELS[reason] ?? reason.replace(/_/g, " ")
}

export default function PjCoursesPage({ onNavigate }: PjCoursesPageProps) {
  const { user } = useSession()
  const { period: pollingPeriod, myVotes, error: pollingError } = usePolling()
  const {
    selectedProdi,
    setSelectedProdi,
    demandAnalytics,
    items: demandItems,
    isLoadingAnalytics,
    handleExportCSV,
  } = useDemandAnalytics(user)

  const [items, setItems] = useState<PjAvailabilityItem[]>([])
  const [meta, setMeta] = useState<PjAvailabilityMeta | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [manageItem, setManageItem] = useState<PjAvailabilityItem | null>(null)
  const [pjmkByCourse, setPjmkByCourse] = useState<Record<string, string>>({})
  const [academicPeriodId, setAcademicPeriodId] = useState("")

  useEffect(() => {
    let active = true
    schedulingService
      .listPreferencePeriods()
      .then((response) => {
        if (active)
          setAcademicPeriodId(response.meta.current_academic_period_id ?? "")
      })
      .catch(() => {
        if (active) setAcademicPeriodId("")
      })
    return () => {
      active = false
    }
  }, [])
  useEffect(() => {
    let active = true
    if (!academicPeriodId) {
      setPjmkByCourse({})
      return () => {
        active = false
      }
    }
    schedulingService
      .listInstructorReferences({
        role: "pjmk",
        academic_period_id: academicPeriodId,
      })
      .then((references) => {
        if (!active) return
        const next: Record<string, string> = {}
        for (const reference of references) {
          if (!reference.curriculum_course_id) continue
          const name =
            reference.lecturer_name?.trim() || reference.instructor_name.trim()
          if (name) next[reference.curriculum_course_id] = name
        }
        setPjmkByCourse(next)
      })
      .catch(() => {
        if (active) setPjmkByCourse({})
      })
    return () => {
      active = false
    }
  }, [academicPeriodId])

  useEffect(() => {
    let active = true
    setIsLoading(true)
    setLoadError(null)
    pjService
      .getAvailability()
      .then((result) => {
        if (!active) return
        setItems(result.data)
        setMeta(result.meta)
      })
      .catch((cause) => {
        if (active) {
          setLoadError(
            apiErrorMessage(cause, "Daftar mata kuliah tidak dapat dimuat."),
          )
        }
      })
      .finally(() => {
        if (active) setIsLoading(false)
      })
    return () => {
      active = false
    }
  }, [reloadKey])

  const table = useTableControls<PjAvailabilityItem>(items, {
    searchFields: (item) => [
      item.course_code,
      item.course_name,
      pjmkByCourse[item.curriculum_course_id] ?? "",
      meta?.study_program ?? "",
    ],
    sorters: {
      course_code: (item) => item.course_code,
      course_name: (item) => item.course_name,
      pjmk: (item) => pjmkByCourse[item.curriculum_course_id] ?? "",
      study_program: () => meta?.study_program ?? "",
      semester: (item) => item.semester,
      status: (item) => (item.is_active ? 0 : 1),
    },
    initialSort: { key: "course_name", order: "asc" },
  })

  const handleSaved = (updated: PjAvailabilityItem) => {
    setItems((previous) =>
      previous.map((item) =>
        item.curriculum_course_id === updated.curriculum_course_id
          ? updated
          : item,
      ),
    )
    setManageItem(null)
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <section aria-labelledby="pj-rekap-title" className="space-y-3">
        <div>
          <h2
            id="pj-rekap-title"
            className="font-heading text-lg font-bold text-navy md:text-xl"
          >
            Rekap Peminatan
          </h2>
          <p className="text-xs text-muted">
            Analisis peminatan MK Pilihan untuk program studi yang Anda kelola
            sebagai PJ Prodi.
          </p>
        </div>
        {pollingError && (
          <div
            role="status"
            className="rounded-xl border border-orange/30 bg-orange/10 px-4 py-2.5 text-xs text-navy"
          >
            {pollingError}
          </div>
        )}
        <PollingPanel
          user={user}
          studentVotes={myVotes}
          pollingPeriod={pollingPeriod}
          onNavigate={onNavigate}
          selectedProdi={selectedProdi}
          setSelectedProdi={setSelectedProdi}
          items={demandItems}
          demandAnalytics={demandAnalytics}
          isLoadingAnalytics={isLoadingAnalytics}
          handleExportCSV={handleExportCSV}
        />
      </section>

      <section aria-labelledby="pj-kelola-title" className="space-y-3">
        <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <div>
            <h2
              id="pj-kelola-title"
              className="font-heading text-lg font-bold text-navy md:text-xl"
            >
              Kelola Ketersediaan Mata Kuliah
            </h2>
            <p className="text-xs text-muted">
              Tentukan MK Pilihan yang dapat dipilih mahasiswa pada periode
              polling berikutnya.
            </p>
          </div>
          {meta && (
            <p className="text-xs text-muted md:text-right">
              {meta.study_program}, semester target {meta.target_semester},{" "}
              {meta.total} mata kuliah
            </p>
          )}
        </div>

        {isLoading && (
          <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-border bg-surface py-12 text-muted">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-gold/30 border-t-gold" />
            <p className="font-mono text-xs">Memuat daftar mata kuliah...</p>
          </div>
        )}

        {!isLoading && loadError && (
          <div
            role="alert"
            className="flex flex-col gap-3 rounded-xl border border-orange/30 bg-orange/10 px-4 py-3 text-sm text-navy sm:flex-row sm:items-center sm:justify-between"
          >
            <span className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 text-orange" />
              {loadError}
            </span>
            <button
              type="button"
              onClick={() => setReloadKey((key) => key + 1)}
              className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-lg border border-orange/40 px-3 text-xs font-semibold text-orange transition-colors hover:bg-orange/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-offset-2 cursor-pointer"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Coba lagi
            </button>
          </div>
        )}

        {!isLoading && !loadError && (
          <div className="space-y-3">
            <TableSearchInput
              id="pj-course-search"
              value={table.search}
              onChange={table.setSearch}
              label="Cari mata kuliah"
              placeholder="Kode MK, nama MK, PJMK, atau program studi"
            />

            <div className="overflow-hidden rounded-xl border border-border bg-surface">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[100rem] table-fixed text-left text-xs">
                  <colgroup>
                    <col className="w-[7rem]" />
                    <col className="w-[18rem]" />
                    <col className="w-[14rem]" />
                    <col className="w-[12rem]" />
                    <col className="w-[6rem]" />
                    <col className="w-[7rem]" />
                    <col className="w-[13rem]" />
                    <col className="w-[16rem]" />
                    <col className="w-[7rem]" />
                  </colgroup>
                  <thead className="border-b border-border bg-background text-muted">
                    <tr>
                      <SortableTh
                        label="Kode MK"
                        sortKey="course_code"
                        sort={table.sort}
                        onSort={table.toggleSort}
                      />
                      <SortableTh
                        label="Mata Kuliah"
                        sortKey="course_name"
                        sort={table.sort}
                        onSort={table.toggleSort}
                      />
                      <SortableTh
                        label="PJMK"
                        sortKey="pjmk"
                        sort={table.sort}
                        onSort={table.toggleSort}
                      />
                      <SortableTh
                        label="Prodi / Cakupan"
                        sortKey="study_program"
                        sort={table.sort}
                        onSort={table.toggleSort}
                      />
                      <SortableTh
                        label="Semester"
                        sortKey="semester"
                        sort={table.sort}
                        onSort={table.toggleSort}
                        align="center"
                      />
                      <SortableTh
                        label="Status"
                        sortKey="status"
                        sort={table.sort}
                        onSort={table.toggleSort}
                      />
                      <th
                        scope="col"
                        className="px-3 py-3 font-mono text-[10px] font-semibold uppercase tracking-wider"
                      >
                        Alasan Terkunci
                      </th>
                      <th
                        scope="col"
                        className="px-3 py-3 font-mono text-[10px] font-semibold uppercase tracking-wider"
                      >
                        Kuota
                      </th>
                      <th
                        scope="col"
                        className="px-3 py-3 text-center font-mono text-[10px] font-semibold uppercase tracking-wider"
                      >
                        Aksi
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {table.pageItems.length === 0 ? (
                      <tr>
                        <td
                          colSpan={9}
                          className="px-4 py-10 text-center text-muted"
                        >
                          {items.length === 0
                            ? "Tidak ada mata kuliah untuk ditampilkan pada periode ini."
                            : "Tidak ada mata kuliah yang cocok dengan pencarian."}
                        </td>
                      </tr>
                    ) : (
                      table.pageItems.map((item) => {
                        const reason = lockReasonLabel(item.lock_reason)
                        const isLocked = !item.can_toggle
                        const reasonId = `pj-lock-reason-${item.curriculum_course_id}`
                        const pjmkName =
                          pjmkByCourse[item.curriculum_course_id] ?? ""
                        const quotaText = `${item.class_count ?? "—"} kelas, ${
                          item.capacity_per_class ?? "—"
                        }/kelas, total ${item.total_quota ?? "—"}, terdaftar ${
                          item.enrolled_count ?? "—"
                        }`
                        return (
                          <tr
                            key={item.curriculum_course_id}
                            className={cn(
                              "transition-colors hover:bg-background/60",
                              isLocked && "bg-background/40",
                            )}
                          >
                            <td
                              className="truncate px-3 py-3 font-mono font-bold text-navy"
                              title={item.course_code}
                            >
                              {item.course_code}
                            </td>
                            <td
                              className="px-3 py-3"
                              title={`${item.course_name}, ${item.credits} SKS, ${item.type || "Pilihan"}`}
                            >
                              <p className="line-clamp-2 font-medium text-foreground">
                                {item.course_name}
                              </p>
                              <p className="mt-0.5 truncate text-[11px] text-muted">
                                {item.credits} SKS, {item.type || "Pilihan"}
                              </p>
                            </td>
                            <td
                              className="truncate px-3 py-3"
                              title={pjmkName || "Belum ada PJ MK"}
                            >
                              {pjmkName ? (
                                <span className="flex min-w-0 items-center gap-1.5">
                                  <span className="inline-flex shrink-0 items-center rounded-full border border-gold/40 bg-gold/15 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-navy">
                                    PJ MK
                                  </span>
                                  <span className="truncate text-foreground">
                                    {pjmkName}
                                  </span>
                                </span>
                              ) : (
                                <span className="text-muted">—</span>
                              )}
                            </td>
                            <td
                              className="truncate px-3 py-3"
                              title={`${meta?.study_program ?? "Program Studi"}, ${
                                SCOPE_LABELS[item.course_scope] ??
                                item.course_scope.replace(/_/g, " ")
                              }`}
                            >
                              <p className="truncate text-foreground">
                                {meta?.study_program ?? "Program Studi"}
                              </p>
                              <p className="mt-0.5 truncate text-[11px] text-muted">
                                {SCOPE_LABELS[item.course_scope] ??
                                  item.course_scope.replace(/_/g, " ")}
                              </p>
                            </td>
                            <td className="px-3 py-3 text-center font-mono text-foreground">
                              {item.semester ?? "—"}
                            </td>
                            <td className="px-3 py-3">
                              <span
                                className={cn(
                                  "inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider",
                                  item.is_active
                                    ? "border-gold/40 bg-gold/15 text-navy"
                                    : "border-border bg-secondary text-muted",
                                )}
                              >
                                {item.is_active ? (
                                  <CheckCircle2 className="h-3 w-3" />
                                ) : (
                                  <Lock className="h-3 w-3" />
                                )}
                                {item.is_active ? "Aktif" : "Nonaktif"}
                              </span>
                            </td>
                            <td
                              id={reasonId}
                              className="truncate px-3 py-3 text-muted"
                              title={reason || "—"}
                            >
                              {reason ? (
                                <span className="flex min-w-0 items-center gap-1.5 text-orange">
                                  <Lock className="h-3.5 w-3.5 shrink-0" />
                                  <span className="truncate">{reason}</span>
                                </span>
                              ) : (
                                "—"
                              )}
                            </td>
                            <td className="px-3 py-3" title={quotaText}>
                              <p className="line-clamp-2 font-mono text-[11px] text-foreground">
                                {quotaText}
                              </p>
                            </td>
                            <td className="px-3 py-3 text-center">
                              <button
                                type="button"
                                aria-describedby={
                                  isLocked ? reasonId : undefined
                                }
                                title={
                                  isLocked
                                    ? reason || "MK ini tidak dapat diubah"
                                    : "Kelola kuota, status, dan tim pengajar"
                                }
                                onClick={() => setManageItem(item)}
                                className="inline-flex min-h-11 items-center justify-center gap-1.5 whitespace-nowrap rounded-lg border border-navy/30 bg-navy/5 px-3 text-xs font-semibold text-navy transition-colors hover:bg-navy/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-offset-2 cursor-pointer"
                              >
                                <Settings2 className="h-3.5 w-3.5" />
                                Kelola
                              </button>
                            </td>
                          </tr>
                        )
                      })
                    )}
                  </tbody>
                </table>
              </div>
              <TablePager
                idPrefix="pj-courses"
                page={table.page}
                pageCount={table.pageCount}
                pageSize={table.pageSize}
                total={table.total}
                from={table.from}
                to={table.to}
                onPage={table.setPage}
                onPageSize={table.setPageSize}
              />
            </div>
          </div>
        )}
      </section>

      {manageItem && (
        <PjCourseManageModal
          key={manageItem.curriculum_course_id}
          item={manageItem}
          studyProgram={meta?.study_program ?? null}
          academicPeriodId={academicPeriodId}
          onClose={() => setManageItem(null)}
          onSaved={handleSaved}
        />
      )}
    </div>
  )
}
