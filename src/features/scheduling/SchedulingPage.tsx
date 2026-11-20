import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react"
import { AlertCircle, RefreshCw } from "lucide-react"
import { useSession } from "@/features/auth/session"
import { apiErrorMessage } from "@/shared/api/client"
import ConfirmDialog, {
  type ConfirmDialogValues,
} from "@/shared/ui/ConfirmDialog"
import { cn } from "@/shared/utils"
import BoardGrid, {
  conflictKindLabel,
  conflictMarkerLabel,
} from "./components/BoardGrid"
import RoomAdminPanel from "./components/RoomAdminPanel"
import InstructorMappingPanel from "./components/InstructorMappingPanel"
import AvailabilityPanel from "./components/AvailabilityPanel"
import { useSchedulingStatus } from "./hooks/useSchedulingStatus"
import {
  schedulingService,
  type BoardClassItem,
  type BoardResponse,
  type ClassMoveRequest,
  type CurriculumCourseOption,
  type RoomResponse,
  type UnassignedItem,
} from "./schedulingService"

const IN_PROGRESS_LABEL = "Jadwal masih dalam proses"
const FINAL_LABEL = "Jadwal final"
const BOARD_POLL_INTERVAL_MS = 5_000

const DAYS = [
  { day: 1, label: "Senin" },
  { day: 2, label: "Selasa" },
  { day: 3, label: "Rabu" },
  { day: 4, label: "Kamis" },
  { day: 5, label: "Jumat" },
] as const

const START_HOURS = Array.from({ length: 10 }, (_, index) => index + 7)

const TABS = [
  { id: "board", label: "Papan Jadwal" },
  { id: "rooms", label: "Ruangan" },
  { id: "instructors", label: "Pemetaan Dosen" },
  { id: "availability", label: "Ketersediaan Dosen" },
] as const

type TabId = typeof TABS[number]["id"]
type BusyAction = "fill_empty" | "full_reset" | "finalize" | "unlock" | "edit" | "class_count"
type ConfirmAction = "reset" | "unlock" | null

interface SchedulingPageProps {
  onNavigate?: (page: string) => void
}

interface EditDraft {
  item: BoardClassItem
  day_of_week: number
  start_hour: number
  room_id: string
  reason: string
}

interface ClassCountOption {
  key: string
  course_id: string
  study_program_id: string
  course_code: string
  course_name: string
  study_program_code: string
  currentCount: number
}

function formatHour(hour: number): string {
  return `${String(hour).padStart(2, "0")}:00`
}

export default function SchedulingPage({ onNavigate }: SchedulingPageProps) {
  const { user } = useSession()
  const isAdmin = user?.role === "admin"
  const isPjProdi =
    user?.role === "lecturer" && user.is_program_coordinator === true
  const { isFinal, retry: refreshSchedulingStatus } = useSchedulingStatus()

  const [board, setBoard] = useState<BoardResponse | null>(null)
  const [rooms, setRooms] = useState<RoomResponse[]>([])
  const [selectedProgramId, setSelectedProgramId] = useState("")
  const [activeTab, setActiveTab] = useState<TabId>("board")
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [actionNotice, setActionNotice] = useState<string | null>(null)
  const [busyAction, setBusyAction] = useState<BusyAction | null>(null)
  const [confirmAction, setConfirmAction] = useState<ConfirmAction>(null)
  const [editDraft, setEditDraft] = useState<EditDraft | null>(null)
  const [overrideCourseKey, setOverrideCourseKey] = useState("")
  const [overrideClassCount, setOverrideClassCount] = useState(1)
  const [curriculumCourses, setCurriculumCourses] =
    useState<CurriculumCourseOption[]>([])
  const [reloadKey, setReloadKey] = useState(0)
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([])
  const boardLoadCount = useRef(0)

  const loadBoard = useCallback(async (options?: { silent?: boolean }) => {
    const silent = options?.silent === true
    if (!silent) setIsLoading(true)
    boardLoadCount.current += 1
    try {
      const response = await schedulingService.getBoard()
      setBoard(response)
      setLoadError(null)
    } catch (cause) {
      if (!silent) {
        setLoadError(apiErrorMessage(cause, "Papan jadwal tidak dapat dimuat."))
      }
    } finally {
      boardLoadCount.current -= 1
      if (!silent) setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadBoard()
  }, [loadBoard, reloadKey])

  useEffect(() => {
    let active = true
    const intervalId = window.setInterval(() => {
      if (!active || boardLoadCount.current > 0) return
      void loadBoard({ silent: true })
    }, BOARD_POLL_INTERVAL_MS)
    return () => {
      active = false
      window.clearInterval(intervalId)
    }
  }, [loadBoard])

  useEffect(() => {
    let active = true
    schedulingService
      .listRooms()
      .then((items) => {
        if (active) setRooms(items)
      })
      .catch(() => {
        if (active) setRooms([])
      })
    return () => {
      active = false
    }
  }, [])
  useEffect(() => {
    let active = true
    schedulingService
      .listCurriculumCourses()
      .then((items) => {
        if (active) setCurriculumCourses(items)
      })
      .catch(() => {
        if (active) setCurriculumCourses([])
      })
    return () => {
      active = false
    }
  }, [])

  const data = board?.data
  const programs = data?.programs ?? []
  const selectedProgram = programs.find(
    (program) => program.study_program_id === selectedProgramId,
  )
  const statusLabel =
    selectedProgram?.state === "final" || isFinal
      ? FINAL_LABEL
      : IN_PROGRESS_LABEL
  const periodId = data?.academic_period_id ?? ""
  const allClasses = data?.classes ?? []
  const unassigned: UnassignedItem[] = data?.unassigned ?? []
  const conflicts = data?.conflicts ?? []
  const actorStudyProgramId =
    typeof board?.meta?.actor_study_program_id === "string"
      ? board.meta.actor_study_program_id
      : null
  const classesById = useMemo(
    () => new Map(allClasses.map((item) => [item.class_section_id, item])),
    [allClasses],
  )
  const visibleConflictRows = useMemo(
    () =>
      conflicts
        .map((conflict) => ({
          key: [
            conflict.class_section_a_id,
            conflict.class_section_b_id,
            conflict.kind,
            conflict.day_of_week,
            conflict.start_hour,
          ].join(":"),
          classA: classesById.get(conflict.class_section_a_id),
          classB: classesById.get(conflict.class_section_b_id),
          conflict,
        }))
        .filter(
          (row) =>
            (row.classA || row.classB) &&
            (!selectedProgramId ||
              row.classA?.study_program_id === selectedProgramId ||
              row.classB?.study_program_id === selectedProgramId),
        ),
    [classesById, conflicts, selectedProgramId],
  )
  const canGenerate = isAdmin || isPjProdi
  const overrideOptions = useMemo(() => {
    const grouped = new Map<string, ClassCountOption>()
    const programCodes = new Map(
      programs.map((program) => [
        program.study_program_id,
        program.study_program_code,
      ]),
    )
    allClasses.forEach((item) => {
      if (!item.course_id) return
      const key = `${item.course_id}:${item.study_program_id}`
      const option = grouped.get(key)
      if (option) {
        option.currentCount += 1
        return
      }
      grouped.set(key, {
        key,
        course_id: item.course_id,
        study_program_id: item.study_program_id,
        course_code: item.course_code,
        course_name: item.course_name,
        study_program_code: item.study_program_code,
        currentCount: 1,
      })
    })
    curriculumCourses.forEach((course) => {
      if (!course.course_id || !course.study_program_id) return
      const key = `${course.course_id}:${course.study_program_id}`
      if (grouped.has(key)) return
      grouped.set(key, {
        key,
        course_id: course.course_id,
        study_program_id: course.study_program_id,
        course_code: course.course_code,
        course_name: course.course_name,
        study_program_code: programCodes.get(course.study_program_id) ?? "",
        currentCount: 0,
      })
    })
    return Array.from(grouped.values()).sort((left, right) =>
      `${left.course_code} ${left.study_program_code}`.localeCompare(
        `${right.course_code} ${right.study_program_code}`,
      ),
    )
  }, [allClasses, curriculumCourses, programs])
  const selectedOverrideOption =
    overrideOptions.find((option) => option.key === overrideCourseKey) ??
    overrideOptions[0] ??
    null
  const canOverrideClassCount = canGenerate && !isFinal
  const canEditClass = (item: BoardClassItem) => {
    if (isFinal || item.state === "final") return false
    if (isAdmin) return true
    if (!isPjProdi || !actorStudyProgramId) return false
    const programIds = item.program_ids
    if (Array.isArray(programIds) && programIds.length > 0) {
      return programIds.includes(actorStudyProgramId)
    }
    return item.study_program_id === actorStudyProgramId
  }

  const runGenerate = async (mode: "fill_empty" | "full_reset") => {
    if (!canGenerate || busyAction) return
    setBusyAction(mode)
    setActionError(null)
    setActionNotice(null)
    try {
      const result = await schedulingService.generate({
        academic_period_id: periodId || undefined,
        mode,
        confirm_full_reset: mode === "full_reset",
      })
      setActionNotice(
        mode === "full_reset"
          ? `Jadwal dibuat ulang: ${result.assigned_count ?? result.assigned} kelas ditempatkan, ${result.unassigned_count ?? result.unassigned.length} belum tersedia.`
          : `${result.assigned_count ?? result.assigned} slot kosong diisi, ${result.unassigned_count ?? result.unassigned.length} kelas masih menunggu.`,
      )
      setConfirmAction(null)
      await loadBoard()
    } catch (cause) {
      setActionError(
        apiErrorMessage(cause, "Penjadwalan otomatis gagal dijalankan."),
      )
    } finally {
      setBusyAction(null)
    }
  }

  const runFinalize = async () => {
    if (!isPjProdi || !periodId || busyAction) return
    setBusyAction("finalize")
    setActionError(null)
    setActionNotice(null)
    try {
      const result = await schedulingService.finalize(periodId)
      setActionNotice(
        result.all_final
          ? "Seluruh jadwal program studi telah final."
          : "Jadwal program studi telah difinalisasi.",
      )
      await loadBoard()
      refreshSchedulingStatus()
      window.dispatchEvent(new CustomEvent("scheduling-status-changed"))
    } catch (cause) {
      setActionError(apiErrorMessage(cause, "Finalisasi jadwal gagal."))
    } finally {
      setBusyAction(null)
    }
  }

  const runUnlock = async (reason: string) => {
    if (!isAdmin || !periodId || busyAction) return
    setBusyAction("unlock")
    setActionError(null)
    try {
      await schedulingService.unlock(periodId, { reason, confirm: true })
      setConfirmAction(null)
      setActionNotice("Kunci jadwal telah dibuka. Jadwal kembali dapat diubah.")
      await loadBoard()
      refreshSchedulingStatus()
      window.dispatchEvent(new CustomEvent("scheduling-status-changed"))
    } catch (cause) {
      setActionError(apiErrorMessage(cause, "Kunci jadwal gagal dibuka."))
    } finally {
      setBusyAction(null)
    }
  }

  const openEdit = (item: BoardClassItem) => {
    if (isFinal || (!isAdmin && !isPjProdi)) return
    setActionError(null)
    setActionNotice(null)
    setEditDraft({
      item,
      day_of_week: item.day_of_week,
      start_hour: item.start_hour,
      room_id: item.room_id ?? "",
      reason: "",
    })
  }

  const submitEdit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!editDraft || busyAction) return
    setBusyAction("edit")
    setActionError(null)
    setActionNotice(null)
    const request: ClassMoveRequest = {
      day_of_week: editDraft.day_of_week,
      start_hour: editDraft.start_hour,
      room_id: editDraft.room_id,
      reason: editDraft.reason.trim(),
    }
    try {
      const result = await schedulingService.moveClass(
        editDraft.item.class_section_id,
        request,
      )
      setEditDraft(null)
      setActionNotice(
        result.conflicts.length > 0
          ? `Jadwal kelas tersimpan, tetapi ${result.conflicts.length} bentrok masih terdeteksi.`
          : "Perubahan jadwal kelas tersimpan.",
      )
      await loadBoard()
    } catch (cause) {
      setActionError(apiErrorMessage(cause, "Perubahan jadwal gagal disimpan."))
    } finally {
      setBusyAction(null)
    }
  }
  const submitClassCountOverride = async (
    event: FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault()
    const option = selectedOverrideOption
    if (
      !option ||
      !canOverrideClassCount ||
      !periodId ||
      busyAction !== null ||
      overrideClassCount < 1 ||
      overrideClassCount > 3
    ) {
      return
    }
    setBusyAction("class_count")
    setActionError(null)
    setActionNotice(null)
    try {
      const result = await schedulingService.setClassCountOverride({
        academic_period_id: periodId,
        course_id: option.course_id,
        study_program_id: option.study_program_id,
        class_count: overrideClassCount,
      })
      setActionNotice(
        `Jumlah kelas ${option.course_code} (${option.study_program_code}) disimpan menjadi ${result.class_count}. Jalankan generate ulang untuk menerapkannya.`,
      )
      await loadBoard()
    } catch (cause) {
      setActionError(apiErrorMessage(cause, "Jumlah kelas gagal disimpan."))
    } finally {
      setBusyAction(null)
    }
  }

  const handleTabKeyDown = (
    event: KeyboardEvent<HTMLButtonElement>,
    index: number,
  ) => {
    let nextIndex: number | null = null
    if (event.key === "ArrowRight") nextIndex = (index + 1) % TABS.length
    if (event.key === "ArrowLeft")
      nextIndex = (index - 1 + TABS.length) % TABS.length
    if (event.key === "Home") nextIndex = 0
    if (event.key === "End") nextIndex = TABS.length - 1
    if (nextIndex === null) return
    event.preventDefault()
    setActiveTab(TABS[nextIndex].id)
    tabRefs.current[nextIndex]?.focus()
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-1">
          <p className="font-mono text-[10px] font-semibold uppercase tracking-widest text-gold">
            Penjadwalan kelas lintas prodi
          </p>
          <h1 className="font-heading text-xl font-bold text-navy md:text-2xl">
            Papan Jadwal Bersama
          </h1>
          <p className="text-xs text-muted">
            {data?.period_label || "Periode akademik aktif"} · Seluruh kelas MK
            dari lima program studi
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span
            role="status"
            aria-live="polite"
            className={cn(
              "inline-flex items-center rounded-full border px-3 py-1.5 text-xs font-semibold",
              isFinal
                ? "border-navy/25 bg-navy/10 text-navy"
                : "border-gold/40 bg-gold/15 text-navy",
            )}
          >
            {statusLabel}
          </span>
          <button
            type="button"
            onClick={() => setReloadKey((key) => key + 1)}
            className="inline-flex min-h-11 items-center gap-1.5 rounded-lg border border-border bg-surface px-3 text-xs font-semibold text-navy transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold cursor-pointer"
          >
            <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
            Muat ulang
          </button>
          {onNavigate && (
            <button
              type="button"
              onClick={() => onNavigate("dashboard")}
              className="inline-flex min-h-11 items-center rounded-lg border border-border bg-surface px-3 text-xs font-semibold text-navy transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold cursor-pointer"
            >
              Dashboard
            </button>
          )}
        </div>
      </header>

      {isLoading && (
        <div
          role="status"
          className="flex flex-col items-center gap-3 rounded-xl border border-border bg-surface py-12 text-muted"
        >
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-gold/30 border-t-gold" />
          <p className="font-mono text-xs">Memuat papan jadwal...</p>
        </div>
      )}

      {!isLoading && loadError && (
        <div
          role="alert"
          className="flex flex-col gap-3 rounded-xl border border-orange/30 bg-orange/10 px-4 py-3 text-sm text-navy sm:flex-row sm:items-center sm:justify-between"
        >
          <span className="flex items-center gap-2">
            <AlertCircle
              className="h-4 w-4 shrink-0 text-orange"
              aria-hidden="true"
            />
            {loadError}
          </span>
          <button
            type="button"
            onClick={() => setReloadKey((key) => key + 1)}
            className="min-h-11 rounded-lg border border-orange/40 px-3 text-xs font-semibold text-orange transition-colors hover:bg-orange/20 cursor-pointer"
          >
            Coba lagi
          </button>
        </div>
      )}

      {actionError && (
        <div
          role="alert"
          className="rounded-xl border border-orange/30 bg-orange/10 px-4 py-2.5 text-xs text-navy"
        >
          {actionError}
        </div>
      )}
      {actionNotice && (
        <div
          role="status"
          className="rounded-xl border border-teal/40 bg-teal/15 px-4 py-2.5 text-xs text-navy"
        >
          {actionNotice}
        </div>
      )}

      {!isLoading && !loadError && (
        <>
          <section
            aria-labelledby="scheduling-controls-title"
            className="space-y-3 rounded-xl border border-border bg-surface p-4"
          >
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div className="space-y-1">
                <h2
                  id="scheduling-controls-title"
                  className="font-heading text-base font-bold text-navy"
                >
                  Kontrol Penjadwalan
                </h2>
                <p className="text-xs text-muted">
                  {conflicts.length} bentrok terdeteksi · {unassigned.length}{" "}
                  kelas belum terjadwal
                </p>
              </div>
              <label className="flex flex-col gap-1 text-xs font-semibold text-navy">
                Filter program studi
                <select
                  value={selectedProgramId}
                  onChange={(event) => setSelectedProgramId(event.target.value)}
                  className="min-h-11 rounded-lg border border-input bg-surface px-3 text-xs font-normal text-navy"
                >
                  <option value="">Semua program studi</option>
                  {programs.map((program) => (
                    <option
                      key={program.study_program_id}
                      value={program.study_program_id}
                    >
                      {program.study_program_code || program.study_program_id}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="flex flex-wrap gap-2">
              {canGenerate && !isFinal && (
                <button
                  type="button"
                  onClick={() => void runGenerate("fill_empty")}
                  disabled={busyAction !== null}
                  className="inline-flex min-h-11 items-center rounded-lg bg-navy px-4 text-xs font-semibold text-white transition-colors hover:bg-navy-light disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold cursor-pointer disabled:cursor-not-allowed"
                >
                  Isi slot kosong
                </button>
              )}
              {isAdmin && !isFinal && (
                <button
                  type="button"
                  onClick={() => {
                    setActionError(null)
                    setConfirmAction("reset")
                  }}
                  disabled={busyAction !== null}
                  className="inline-flex min-h-11 items-center rounded-lg border border-orange/40 px-4 text-xs font-semibold text-orange transition-colors hover:bg-orange/10 disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold cursor-pointer disabled:cursor-not-allowed"
                >
                  Reset &amp; generate semua
                </button>
              )}
              {isPjProdi && !isFinal && selectedProgram?.state !== "final" && (
                <button
                  type="button"
                  onClick={() => void runFinalize()}
                  disabled={busyAction !== null || !periodId}
                  className="inline-flex min-h-11 items-center rounded-lg bg-gold px-4 text-xs font-semibold text-navy-dark transition-colors hover:bg-gold-hover disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold cursor-pointer disabled:cursor-not-allowed"
                >
                  Finalisasi jadwal
                </button>
              )}
              {isAdmin && isFinal && (
                <button
                  type="button"
                  onClick={() => {
                    setActionError(null)
                    setConfirmAction("unlock")
                  }}
                  disabled={busyAction !== null || !periodId}
                  className="inline-flex min-h-11 items-center rounded-lg border border-navy/30 px-4 text-xs font-semibold text-navy transition-colors hover:bg-accent disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold cursor-pointer disabled:cursor-not-allowed"
                >
                  Buka kunci jadwal
                </button>
              )}
              {isFinal && !isAdmin && (
                <p className="self-center text-xs text-muted">
                  Jadwal sudah final. Perubahan memerlukan pembukaan kunci oleh
                  admin.
                </p>
              )}
              {!canGenerate && (
                <p className="self-center text-xs text-muted">
                  Hanya PJ Prodi dan admin yang dapat menjalankan penjadwalan.
                </p>
              )}
            </div>
            {canGenerate && (
              <form
                onSubmit={(event) => void submitClassCountOverride(event)}
                aria-labelledby="class-count-override-title"
                className="flex flex-col gap-2 rounded-lg border border-border bg-background p-3 sm:flex-row sm:items-end"
              >
                <div className="min-w-0 flex-1 space-y-1">
                  <h3
                    id="class-count-override-title"
                    className="font-heading text-xs font-bold text-navy"
                  >
                    Jumlah kelas per mata kuliah
                  </h3>
                  <label className="flex flex-col gap-1 text-[11px] font-semibold text-navy">
                    Mata kuliah
                    <select
                      value={selectedOverrideOption?.key ?? ""}
                      onChange={(event) => {
                        setOverrideCourseKey(event.target.value)
                        const option = overrideOptions.find(
                          (item) => item.key === event.target.value,
                        )
                        if (option) {
                          setOverrideClassCount(
                            Math.min(3, Math.max(1, option.currentCount)),
                          )
                        }
                      }}
                      disabled={
                        !canOverrideClassCount ||
                        selectedOverrideOption === null
                      }
                      className={cn(
                        "min-h-10 rounded-lg border border-input bg-surface px-2 text-xs font-normal text-navy",
                        !canOverrideClassCount &&
                          "cursor-not-allowed opacity-60",
                      )}
                    >
                      {overrideOptions.length === 0 && (
                        <option value="">Belum ada mata kuliah</option>
                      )}
                      {overrideOptions.map((option) => (
                        <option key={option.key} value={option.key}>
                          {option.course_code} · {option.course_name}
                          {option.study_program_code
                            ? ` (${option.study_program_code})`
                            : ""}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <label className="flex w-full flex-col gap-1 text-[11px] font-semibold text-navy sm:w-24">
                  Jumlah kelas
                  <select
                    value={overrideClassCount}
                    onChange={(event) =>
                      setOverrideClassCount(Number(event.target.value))
                    }
                    disabled={
                      !canOverrideClassCount || selectedOverrideOption === null
                    }
                    className={cn(
                      "min-h-10 rounded-lg border border-input bg-surface px-2 text-xs font-normal text-navy",
                      !canOverrideClassCount && "cursor-not-allowed opacity-60",
                    )}
                  >
                    {[1, 2, 3].map((count) => (
                      <option key={count} value={count}>
                        {count} kelas
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  type="submit"
                  disabled={
                    !canOverrideClassCount ||
                    !periodId ||
                    selectedOverrideOption === null ||
                    busyAction !== null
                  }
                  className="inline-flex min-h-10 items-center rounded-lg bg-navy px-3 text-xs font-semibold text-white transition-colors hover:bg-navy-light disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold cursor-pointer disabled:cursor-not-allowed"
                >
                  {busyAction === "class_count"
                    ? "Menyimpan..."
                    : "Simpan jumlah kelas"}
                </button>
                {!canOverrideClassCount && (
                  <p className="self-center text-[11px] text-muted">
                    Jadwal sudah final dan KRS dibuka. Hubungi admin untuk
                    membuka kunci.
                  </p>
                )}
              </form>
            )}
          </section>

          {editDraft && (
            <section
              aria-labelledby="class-edit-title"
              className="rounded-xl border border-navy/20 bg-surface p-4"
            >
              <h3
                id="class-edit-title"
                className="font-heading text-base font-bold text-navy"
              >
                Ubah jadwal {editDraft.item.course_code} ·{" "}
                {editDraft.item.section_code}
              </h3>
              <p className="mb-3 text-xs text-muted">
                {editDraft.item.course_name} · blok {editDraft.item.credits} jam
              </p>
              <form
                onSubmit={(event) => void submitEdit(event)}
                className="grid gap-3 md:grid-cols-4"
              >
                <label className="flex flex-col gap-1 text-xs font-semibold text-navy">
                  Hari
                  <select
                    value={editDraft.day_of_week}
                    onChange={(event) =>
                      setEditDraft((draft) =>
                        draft
                          ? {
                              ...draft,
                              day_of_week: Number(event.target.value),
                            }
                          : draft,
                      )
                    }
                    className="min-h-11 rounded-lg border border-input bg-surface px-2 text-xs font-normal"
                  >
                    {DAYS.map((day) => (
                      <option key={day.day} value={day.day}>
                        {day.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col gap-1 text-xs font-semibold text-navy">
                  Jam mulai
                  <select
                    value={editDraft.start_hour}
                    onChange={(event) =>
                      setEditDraft((draft) =>
                        draft
                          ? { ...draft, start_hour: Number(event.target.value) }
                          : draft,
                      )
                    }
                    className="min-h-11 rounded-lg border border-input bg-surface px-2 text-xs font-normal"
                  >
                    {START_HOURS.map((hour) => (
                      <option key={hour} value={hour}>
                        {formatHour(hour)}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col gap-1 text-xs font-semibold text-navy">
                  Ruangan
                  <select
                    value={editDraft.room_id}
                    onChange={(event) =>
                      setEditDraft((draft) =>
                        draft
                          ? { ...draft, room_id: event.target.value }
                          : draft,
                      )
                    }
                    className="min-h-11 rounded-lg border border-input bg-surface px-2 text-xs font-normal"
                  >
                    <option value="">Tanpa ruangan</option>
                    {rooms
                      .filter((room) => room.is_active)
                      .map((room) => (
                        <option key={room.room_id} value={room.room_id}>
                          {room.room_code} · {room.capacity} kursi
                        </option>
                      ))}
                  </select>
                </label>
                <label className="flex flex-col gap-1 text-xs font-semibold text-navy">
                  Alasan perubahan *
                  <input
                    type="text"
                    required
                    maxLength={500}
                    value={editDraft.reason}
                    onChange={(event) =>
                      setEditDraft((draft) =>
                        draft
                          ? { ...draft, reason: event.target.value }
                          : draft,
                      )
                    }
                    placeholder="Contoh: menyesuaikan ketersediaan dosen"
                    className="min-h-11 rounded-lg border border-input bg-surface px-3 text-xs font-normal"
                  />
                </label>
                <div className="flex items-end gap-2 md:col-span-4">
                  <button
                    type="submit"
                    disabled={
                      busyAction !== null ||
                      editDraft.reason.trim().length === 0
                    }
                    className="min-h-11 rounded-lg bg-navy px-4 text-xs font-semibold text-white transition-colors hover:bg-navy-light disabled:opacity-60 cursor-pointer"
                  >
                    Simpan perubahan
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditDraft(null)}
                    className="min-h-11 rounded-lg border border-border px-4 text-xs font-semibold text-navy transition-colors hover:bg-accent cursor-pointer"
                  >
                    Batal
                  </button>
                </div>
              </form>
            </section>
          )}

          <section aria-labelledby="conflict-list-title" className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2
                id="conflict-list-title"
                className="font-heading text-base font-bold text-navy"
              >
                Bentrok Jadwal
              </h2>
              <span className="rounded-full border border-danger/40 bg-danger/10 px-2.5 py-1 text-[11px] font-semibold text-danger">
                {visibleConflictRows.length} bentrok
              </span>
            </div>
            {visibleConflictRows.length === 0 ? (
              <p
                role="status"
                className="rounded-xl border border-teal/40 bg-teal/15 px-4 py-3 text-xs text-navy"
              >
                Tidak ada bentrok yang terdeteksi pada tampilan ini.
              </p>
            ) : (
              <ul className="divide-y divide-border rounded-xl border border-danger/30 bg-surface">
                {visibleConflictRows.map((row) => (
                  <li
                    key={row.key}
                    className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 text-xs"
                  >
                    <div className="min-w-0 space-y-0.5">
                      <p className="font-mono font-semibold text-navy">
                        {row.classA
                          ? `${row.classA.course_code} ${row.classA.section_code}`
                          : "Kelas A belum tersedia"}
                        {" · "}
                        {row.classB
                          ? `${row.classB.course_code} ${row.classB.section_code}`
                          : "Kelas B belum tersedia"}
                      </p>
                      <p className="text-muted">
                        {conflictKindLabel(row.conflict.kind)}
                      </p>
                    </div>
                    <span
                      title={conflictMarkerLabel(row.conflict)}
                      className="rounded bg-danger/20 px-1.5 py-0.5 text-[10px] font-semibold text-danger"
                    >
                      {conflictMarkerLabel(row.conflict)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section aria-labelledby="diagnostics-title" className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2
                id="diagnostics-title"
                className="font-heading text-base font-bold text-navy"
              >
                Kelas Belum Terjadwal
              </h2>
              <span className="rounded-full border border-orange/30 bg-orange/10 px-2.5 py-1 text-[11px] font-semibold text-orange">
                {unassigned.length} kelas
              </span>
            </div>
            {unassigned.length === 0 ? (
              <p
                role="status"
                className="rounded-xl border border-teal/40 bg-teal/15 px-4 py-3 text-xs text-navy"
              >
                Semua kelas telah memiliki blok jadwal.
              </p>
            ) : (
              <ul className="divide-y divide-border rounded-xl border border-border bg-surface">
                {unassigned.map((item) => (
                  <li
                    key={item.class_section_id}
                    className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 text-xs"
                  >
                    <span className="font-mono font-semibold text-navy">
                      {item.course_code || "Mata kuliah tanpa kode"}
                    </span>
                    <span className="text-muted">
                      {item.reason || "Belum ada alasan yang tercatat."}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <div className="space-y-3">
            <div
              role="tablist"
              aria-label="Bagian pengaturan penjadwalan"
              className="flex flex-wrap gap-2 border-b border-border"
            >
              {TABS.map((tab, index) => (
                <button
                  key={tab.id}
                  ref={(element) => {
                    tabRefs.current[index] = element
                  }}
                  type="button"
                  role="tab"
                  id={`scheduling-tab-${tab.id}`}
                  aria-selected={activeTab === tab.id}
                  aria-controls={`scheduling-panel-${tab.id}`}
                  tabIndex={activeTab === tab.id ? 0 : -1}
                  onClick={() => setActiveTab(tab.id)}
                  onKeyDown={(event) => handleTabKeyDown(event, index)}
                  className={cn(
                    "min-h-11 rounded-t-lg border-b-2 px-3 text-xs font-semibold transition-colors cursor-pointer",
                    activeTab === tab.id
                      ? "border-navy text-navy"
                      : "border-transparent text-muted hover:text-navy",
                  )}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <div
              role="tabpanel"
              id="scheduling-panel-board"
              aria-labelledby="scheduling-tab-board"
              hidden={activeTab !== "board"}
            >
              {activeTab === "board" && (
                <BoardGrid
                  classes={allClasses}
                  conflicts={conflicts}
                  selectedProgramId={selectedProgramId || null}
                  canEditClass={canEditClass}
                  onEditClass={openEdit}
                />
              )}
            </div>
            <div
              role="tabpanel"
              id="scheduling-panel-rooms"
              aria-labelledby="scheduling-tab-rooms"
              hidden={activeTab !== "rooms"}
              className="rounded-xl border border-border bg-surface p-4"
            >
              {activeTab === "rooms" && <RoomAdminPanel />}
            </div>
            <div
              role="tabpanel"
              id="scheduling-panel-instructors"
              aria-labelledby="scheduling-tab-instructors"
              hidden={activeTab !== "instructors"}
              className="rounded-xl border border-border bg-surface p-4"
            >
              {activeTab === "instructors" && <InstructorMappingPanel />}
            </div>
            <div
              role="tabpanel"
              id="scheduling-panel-availability"
              aria-labelledby="scheduling-tab-availability"
              hidden={activeTab !== "availability"}
              className="rounded-xl border border-border bg-surface p-4"
            >
              {activeTab === "availability" && <AvailabilityPanel />}
            </div>
          </div>
        </>
      )}

      {confirmAction === "reset" && (
        <ConfirmDialog
          title="Reset dan generate ulang jadwal?"
          body={
            <p className="text-xs text-muted">
              Seluruh penempatan kelas pada periode ini akan diganti. Tindakan
              ini tidak dapat dibatalkan.
            </p>
          }
          confirmLabel="Reset & generate"
          tone="orange"
          busy={busyAction === "full_reset"}
          errorMessage={actionError}
          manualField={{
            expected: "RESET",
            label: "Ketik RESET untuk mengonfirmasi",
            placeholder: "RESET",
          }}
          onConfirm={() => void runGenerate("full_reset")}
          onCancel={() => setConfirmAction(null)}
        />
      )}

      {confirmAction === "unlock" && (
        <ConfirmDialog
          title="Buka kunci jadwal?"
          body={
            <p className="text-xs text-muted">
              Jadwal yang telah final dapat diubah kembali setelah kunci dibuka.
            </p>
          }
          confirmLabel="Buka kunci"
          tone="orange"
          busy={busyAction === "unlock"}
          errorMessage={actionError}
          reasonField={{ required: true, label: "Alasan pembukaan kunci" }}
          onConfirm={(values: ConfirmDialogValues) =>
            void runUnlock(values.reason)
          }
          onCancel={() => setConfirmAction(null)}
        />
      )}
    </div>
  )
}
