import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react"
import { AlertCircle, RefreshCw } from "lucide-react"
import { useSession } from "@/features/auth/session"
import { apiErrorMessage, apiFieldErrors } from "@/shared/api/client"
import { useDiscardGuard } from "@/shared/hooks/useDiscardGuard"
import ConfirmDialog, {
  type ConfirmDialogValues,
} from "@/shared/ui/ConfirmDialog"
import SearchableCombobox, {
  type ComboboxOption,
} from "@/shared/ui/SearchableCombobox"
import FormFieldError from "@/shared/ui/FormFieldError"
import { cn } from "@/shared/utils"
import BoardGrid, {
  LINTAS_PRODI_FILTER,
  conflictMarkerLabel,
} from "./components/BoardGrid"
import SchedulingLifecycleStatus from "./components/SchedulingLifecycleStatus"
import RoomAdminPanel from "./components/RoomAdminPanel"
import PreferenceDeadlinePanel from "./components/PreferenceDeadlinePanel"
import UnassignedClassList from "./components/UnassignedClassList"
import UnassignedDiagnosticDialog from "./components/UnassignedDiagnosticDialog"
import { useSchedulingStatus } from "./hooks/useSchedulingStatus"
import {
  schedulingService,
  type BoardClassItem,
  type BoardResponse,
  type ClassMoveRequest,
  type FinalizeResponse,
  type GenerateResponse,
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
  { id: "deadlines", label: "Deadline Preferensi" },
] as const

type TabId = typeof TABS[number]["id"]
type BusyAction = "regenerate" | "full_reset" | "finalize" | "unlock" | "edit"
type ConfirmAction = "reset" | "unlock" | null

interface SchedulingPageProps {
  onOpenPanel?: (
    target: "teaching-team" | "class-assignment",
    params: {
      period?: string | null
      course?: string | null
      reference?: string | null
    },
  ) => void
}

interface EditDraft {
  item: BoardClassItem
  day_of_week: number
  start_hour: number
  room_id: string
  reason: string
}

interface ProgramLabel {
  code: string
  name: string
}

function formatHour(hour: number): string {
  return `${String(hour).padStart(2, "0")}:00`
}

function readNumber(
  meta: Record<string, unknown> | undefined,
  key: string,
): number {
  const value = meta?.[key]
  return typeof value === "number" && Number.isFinite(value) ? value : 0
}

function matchesProgram(item: BoardClassItem, programId: string): boolean {
  if (!programId) return true
  if (programId === LINTAS_PRODI_FILTER) {
    return item.programs.length > 1
  }
  return item.programs.length > 0
    ? item.programs.some((program) => program.study_program_id === programId)
    : item.study_program_id === programId
}

export default function SchedulingPage({ onOpenPanel }: SchedulingPageProps) {
  const { user } = useSession()
  const isAdmin = user?.role === "admin"
  const isPjProdi =
    user?.role === "lecturer" && user.is_program_coordinator === true
  const canOperateSchedule = isAdmin || isPjProdi
  const isOrdinaryLecturer = user?.role === "lecturer" && !isPjProdi
  const { isFinal, retry: refreshSchedulingStatus } = useSchedulingStatus()

  const [board, setBoard] = useState<BoardResponse | null>(null)
  const [rooms, setRooms] = useState<RoomResponse[]>([])
  const [selectedProgramId, setSelectedProgramId] = useState("")
  const [classScope, setClassScope] = useState<"all" | "mine">("all")
  const [activeTab, setActiveTab] = useState<TabId>("board")
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [actionNotice, setActionNotice] = useState<string | null>(null)
  const [editRoomError, setEditRoomError] = useState<string | null>(null)
  const [generationResult, setGenerationResult] =
    useState<GenerateResponse | null>(null)
  const [finalizeResult, setFinalizeResult] = useState<FinalizeResponse | null>(
    null,
  )
  const [busyAction, setBusyAction] = useState<BusyAction | null>(null)
  const [confirmAction, setConfirmAction] = useState<ConfirmAction>(null)
  const [editDraft, setEditDraft] = useState<EditDraft | null>(null)
  const [diagnosticItem, setDiagnosticItem] = useState<UnassignedItem | null>(
    null,
  )
  const [reloadKey, setReloadKey] = useState(0)
  const boardLoadCount = useRef(0)
  const generationKeysRef =
    useRef<Partial<Record<"regenerate" | "full_reset", string>>>({})
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([])
  const visibleTabs = useMemo(
    () =>
      TABS.filter((tab) => {
        if (!canOperateSchedule) return tab.id === "board"
        if (tab.id === "rooms") return isAdmin
        if (tab.id === "deadlines") return isAdmin || isPjProdi
        return true
      }),
    [canOperateSchedule, isAdmin, isPjProdi],
  )

  const loadBoard = useCallback(async (options?: { silent?: boolean }) => {
    const silent = options?.silent === true
    if (!silent) setIsLoading(true)
    boardLoadCount.current += 1
    try {
      const response = await schedulingService.getBoard()
      setBoard(response)
      setGenerationResult((current) => {
        if (!current) return current
        const program = current.study_program_id
          ? response.data.programs.find(
              (item) => item.study_program_id === current.study_program_id,
            )
          : undefined
        const revision = program?.input_revision ?? response.meta.input_revision
        return current.input_revision === revision ? current : null
      })
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
    if (!canOperateSchedule) {
      setActiveTab("board")
      return
    }
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
  }, [canOperateSchedule])

  const data = board?.data
  const programs = data?.programs ?? []
  const allClasses = data?.classes ?? []
  const unassigned: UnassignedItem[] = data?.unassigned ?? []
  const conflicts = data?.conflicts ?? []
  const programLabels = useMemo(() => {
    const labels = new Map<string, ProgramLabel>()
    for (const program of programs) {
      labels.set(program.study_program_id, {
        code: program.study_program_code,
        name: program.study_program_name ?? "",
      })
    }
    for (const item of allClasses) {
      for (const program of item.programs) {
        labels.set(program.study_program_id, {
          code: program.study_program_code,
          name: program.study_program_name,
        })
      }
    }
    for (const item of unassigned) {
      for (const program of item.programs) {
        labels.set(program.study_program_id, {
          code: program.study_program_code,
          name: program.study_program_name,
        })
      }
    }
    return labels
  }, [allClasses, programs, unassigned])
  const selectedProgram = programs.find(
    (program) => program.study_program_id === selectedProgramId,
  )
  const actorStudyProgramId =
    typeof board?.meta?.actor_study_program_id === "string"
      ? board.meta.actor_study_program_id
      : null

  const scopedProgram = isPjProdi
    ? programs.find(
        (program) => program.study_program_id === actorStudyProgramId,
      )
    : selectedProgram
  const effectiveProgramId = isPjProdi
    ? (actorStudyProgramId ?? "")
    : selectedProgramId
  const scopedPrograms = programs.filter(
    (program) =>
      !effectiveProgramId ||
      effectiveProgramId === LINTAS_PRODI_FILTER ||
      program.study_program_id === effectiveProgramId,
  )
  const scopeStates = scopedPrograms.map((program) => program.state)
  const isCurrentScopeFinal =
    scopeStates.length > 0
      ? scopeStates.every((state) => state === "final")
      : scopedProgram?.state === "final" ||
        (!isPjProdi && !selectedProgramId && isFinal)
  const isCurrentScopeMixed =
    scopeStates.some((state) => state === "final") &&
    scopeStates.some((state) => state !== "final")
  const statusLabel = isCurrentScopeMixed
    ? "Sebagian jadwal final"
    : isCurrentScopeFinal
      ? FINAL_LABEL
      : IN_PROGRESS_LABEL
  const scopedProgramLabel = scopedProgram
    ? [
        scopedProgram.study_program_code,
        programLabels.get(scopedProgram.study_program_id)?.name,
      ]
        .filter(Boolean)
        .join(" ")
    : ""
  const scopeLabel =
    scopedProgramLabel ||
    (isPjProdi
      ? actorStudyProgramId
        ? "Prodi Anda"
        : "Cakupan prodi tidak tersedia"
      : effectiveProgramId === LINTAS_PRODI_FILTER
        ? "Lintas prodi"
        : "Semua program studi")
  const generationTargetProgramId = isPjProdi
    ? (actorStudyProgramId ?? undefined)
    : selectedProgramId && selectedProgramId !== LINTAS_PRODI_FILTER
      ? selectedProgramId
      : undefined
  const targetProgramLabel = generationTargetProgramId
    ? programLabels.get(generationTargetProgramId)
    : null
  const actionScopeLabel = targetProgramLabel
    ? [targetProgramLabel.code, targetProgramLabel.name]
        .filter(Boolean)
        .join(" ")
    : generationTargetProgramId
      ? "program studi terpilih"
      : "semua program studi"
  const viewScopeLabel =
    selectedProgramId === LINTAS_PRODI_FILTER
      ? "Lintas prodi"
      : selectedProgram
        ? [
            programLabels.get(selectedProgramId)?.code ??
              selectedProgram.study_program_code,
            programLabels.get(selectedProgramId)?.name,
          ]
            .filter(Boolean)
            .join(" ")
        : "Semua program studi"
  const periodId = data?.academic_period_id ?? ""
  const scopedClasses = allClasses.filter(
    (item) =>
      matchesProgram(item, effectiveProgramId) &&
      (!isOrdinaryLecturer ||
        classScope !== "mine" ||
        item.assigned_lecturer_id === user?.user_id),
  )
  const scopedUnassigned = unassigned.filter(
    (item) =>
      !effectiveProgramId ||
      effectiveProgramId === LINTAS_PRODI_FILTER ||
      item.programs.some(
        (program) => program.study_program_id === effectiveProgramId,
      ),
  )
  const roomOptions = useMemo<ComboboxOption[]>(
    () => [
      { value: "", label: "Tanpa ruangan" },
      ...rooms
        .filter((room) => room.is_active)
        .map((room) => ({
          value: room.room_id,
          label: `${room.room_code}, ${room.capacity} kursi`,
        })),
    ],
    [rooms],
  )

  const boardMeta = board?.meta
  const unmappedRoomCount = readNumber(boardMeta, "unmapped_room_count")
  const unmappedLecturerCount = readNumber(boardMeta, "unmapped_lecturer_count")
  const emptySectionCount = readNumber(boardMeta, "empty_section_count")
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
        .filter((row) => {
          if (!row.classA && !row.classB) return false
          return [row.classA, row.classB].some(
            (item) => item && matchesProgram(item, effectiveProgramId),
          )
        }),
    [classesById, conflicts, effectiveProgramId],
  )
  const blockingConflictCount = visibleConflictRows.length
  const staleClasses = scopedClasses.filter((item) => item.is_stale)
  const stalePrograms = programs.filter(
    (program) =>
      program.is_stale &&
      (!effectiveProgramId ||
        effectiveProgramId === LINTAS_PRODI_FILTER ||
        program.study_program_id === effectiveProgramId),
  )
  const reportedStaleCount = readNumber(boardMeta, "stale_count")
  const staleCount =
    isPjProdi ||
    (effectiveProgramId && effectiveProgramId !== LINTAS_PRODI_FILTER)
      ? staleClasses.length
      : Math.max(reportedStaleCount, staleClasses.length)
  const requiresRegeneration = staleCount > 0 || stalePrograms.length > 0
  const inputRevisionValue =
    isPjProdi ||
    (effectiveProgramId && effectiveProgramId !== LINTAS_PRODI_FILTER)
      ? scopedProgram?.input_revision
      : (boardMeta?.input_revision ?? scopedProgram?.input_revision)
  const inputRevision =
    typeof inputRevisionValue === "number" &&
    Number.isFinite(inputRevisionValue)
      ? inputRevisionValue
      : null

  const invalidClassCount = scopedClasses.filter(
    (item) => !item.room_id || item.lecturers.length === 0,
  ).length
  const finalizeBlockers: string[] = []
  if (blockingConflictCount > 0) {
    finalizeBlockers.push(`${blockingConflictCount} bentrok ruang/dosen`)
  }
  if (scopedUnassigned.length > 0) {
    finalizeBlockers.push(`${scopedUnassigned.length} kelas belum terjadwal`)
  }
  if (invalidClassCount > 0) {
    finalizeBlockers.push(
      `${invalidClassCount} kelas tanpa ruangan atau pengajar aktif`,
    )
  }
  if (requiresRegeneration) {
    finalizeBlockers.push("jadwal stale perlu diregenerasi")
  }
  if (isPjProdi && !scopedProgram?.run_id) {
    finalizeBlockers.push("belum ada hasil penjadwalan pada revisi input ini")
  }
  const generationProgramLabel = generationResult?.study_program_id
    ? programLabels.get(generationResult.study_program_id)
    : null
  const generationScopeLabel = generationResult
    ? generationProgramLabel
      ? [generationProgramLabel.code, generationProgramLabel.name]
          .filter(Boolean)
          .join(" ")
      : "semua program studi"
    : null
  const canGenerate = canOperateSchedule

  const editDirty =
    editDraft !== null &&
    (editDraft.day_of_week !== editDraft.item.day_of_week ||
      editDraft.start_hour !== editDraft.item.start_hour ||
      editDraft.room_id !== (editDraft.item.room_id ?? "") ||
      editDraft.reason !== "")
  const closeEditDraft = useCallback(() => setEditDraft(null), [])
  const { requestClose: requestCloseEdit, discardDialog } = useDiscardGuard({
    dirty: editDirty,
    onClose: closeEditDraft,
  })

  useEffect(() => {
    if (!editDraft) return
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return
      event.preventDefault()
      requestCloseEdit()
    }
    document.addEventListener("keydown", handleKeyDown)
    return () => document.removeEventListener("keydown", handleKeyDown)
  }, [editDraft, requestCloseEdit])

  const renderConflictRow = (row: typeof visibleConflictRows[number]) => (
    <li
      key={row.key}
      className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 text-xs"
    >
      <div className="min-w-0 space-y-1">
        <p className="font-semibold text-navy">
          {conflictMarkerLabel(row.conflict)}
        </p>
        {row.conflict.object_label && (
          <p className="text-muted">{row.conflict.object_label}</p>
        )}
      </div>
    </li>
  )

  const canEditClass = (item: BoardClassItem) => {
    if (item.read_only || !item.can_edit || item.state === "final") return false
    if (isPjProdi ? scopedProgram?.state === "final" : isCurrentScopeFinal) {
      return false
    }
    if (isAdmin) return true
    if (!isPjProdi || !actorStudyProgramId) return false
    return matchesProgram(item, actorStudyProgramId)
  }

  const openMappingForUnassigned = (item: UnassignedItem) => {
    const contexts = item.eligible_curriculum_contexts
    const actorContexts =
      isPjProdi && actorStudyProgramId
        ? contexts.filter(
            (context) => context.study_program_id === actorStudyProgramId,
          )
        : contexts
    const context =
      actorContexts.find(
        (candidate) =>
          item.pjmk_reference_id !== null &&
          candidate.pjmk_reference_id === item.pjmk_reference_id,
      ) ??
      actorContexts[0] ??
      contexts.find(
        (candidate) =>
          item.pjmk_reference_id !== null &&
          candidate.pjmk_reference_id === item.pjmk_reference_id,
      ) ??
      contexts[0]
    if (!context || !periodId) {
      setDiagnosticItem(item)
      return
    }
    onOpenPanel?.("teaching-team", {
      period: periodId,
      course: context.curriculum_course_id,
      reference: item.pjmk_reference_id,
    })
  }

  const openAssignmentForUnassigned = (item: UnassignedItem) => {
    if (!periodId || item.eligible_curriculum_contexts.length === 0) {
      setDiagnosticItem(item)
      return
    }
    onOpenPanel?.("class-assignment", {
      period: periodId,
      course:
        item.eligible_curriculum_contexts.length === 1
          ? item.eligible_curriculum_contexts[0].curriculum_course_id
          : null,
    })
  }

  const runGenerate = async (mode: "regenerate" | "full_reset") => {
    if (!canGenerate || busyAction || !periodId) return
    if (mode === "full_reset" && !isAdmin) return
    const targetProgramId = generationTargetProgramId
    if (mode === "regenerate" && isPjProdi && !targetProgramId) return
    const requestKey =
      generationKeysRef.current[mode] ??
      (generationKeysRef.current[mode] = crypto.randomUUID())
    setBusyAction(mode)
    setActionError(null)
    setActionNotice(null)
    setFinalizeResult(null)
    try {
      const result = await schedulingService.generate({
        academic_period_id: periodId,
        mode,
        confirm_full_reset: mode === "full_reset",
        study_program_id: targetProgramId,
        request_key: requestKey,
      })
      setGenerationResult(result)
      setActionNotice(
        mode === "full_reset"
          ? "Reset penuh jadwal selesai."
          : "Jadwal berhasil dibuat ulang.",
      )
      setConfirmAction(null)
      await loadBoard()
    } catch (cause) {
      setActionError(
        apiErrorMessage(cause, "Penjadwalan otomatis gagal dijalankan."),
      )
    } finally {
      delete generationKeysRef.current[mode]
      setBusyAction(null)
    }
  }

  const runFinalize = async () => {
    if (!isPjProdi || !periodId || busyAction || finalizeBlockers.length > 0) {
      return
    }
    setBusyAction("finalize")
    setActionError(null)
    setActionNotice(null)
    setGenerationResult(null)
    try {
      const result = await schedulingService.finalize(periodId)
      setFinalizeResult(result)
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
    setActionNotice(null)
    setGenerationResult(null)
    setFinalizeResult(null)
    try {
      const result = await schedulingService.unlock(periodId, {
        reason,
        confirm: true,
      })
      setConfirmAction(null)
      setActionNotice(
        `${result.unlocked_count} jadwal dibuka. ${result.audit_count} catatan audit dibuat.`,
      )
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
    if (!canEditClass(item)) return
    setActionError(null)
    setEditRoomError(null)
    setActionNotice(null)
    setGenerationResult(null)
    setFinalizeResult(null)
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
    if (!editDraft || busyAction || !canEditClass(editDraft.item)) return
    setBusyAction("edit")
    setActionError(null)
    setEditRoomError(null)
    setActionNotice(null)
    setGenerationResult(null)
    setFinalizeResult(null)

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
      const roomIssue = apiFieldErrors(cause).find(
        (issue) => issue.field === "room_id" || issue.field === "room",
      )
      setEditRoomError(roomIssue?.message ?? null)
      setActionError(apiErrorMessage(cause, "Perubahan jadwal gagal disimpan."))
    } finally {
      setBusyAction(null)
    }
  }

  const handleTabKeyDown = (
    event: ReactKeyboardEvent<HTMLButtonElement>,
    index: number,
  ) => {
    let nextIndex: number | null = null
    if (event.key === "ArrowRight") nextIndex = (index + 1) % visibleTabs.length
    if (event.key === "ArrowLeft")
      nextIndex = (index - 1 + visibleTabs.length) % visibleTabs.length
    if (event.key === "Home") nextIndex = 0
    if (event.key === "End") nextIndex = visibleTabs.length - 1
    if (nextIndex === null) return
    event.preventDefault()
    setActiveTab(visibleTabs[nextIndex].id)
    tabRefs.current[nextIndex]?.focus()
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-1">
          <p className="font-mono text-[10px] font-semibold uppercase tracking-widest text-gold">
            Penjadwalan kelas lintas prodi
          </p>
          <h2 className="font-heading text-xl font-bold text-navy md:text-2xl">
            Penjadwalan
          </h2>
          <p className="text-xs text-muted">
            {data?.period_label || "Periode akademik aktif"},{" "}
            {canOperateSchedule
              ? `cakupan ${scopeLabel.toLowerCase()}`
              : "tampilan jadwal hanya-baca"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span
            role="status"
            aria-live="polite"
            className={cn(
              "inline-flex items-center rounded-full border px-3 py-1.5 text-xs font-semibold",
              isCurrentScopeFinal
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
        </div>
      </header>

      <div
        role="tablist"
        aria-label="Bagian penjadwalan"
        className="flex flex-wrap gap-2 border-b border-border"
      >
        {visibleTabs.map((tab, index) => (
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
              "min-h-11 rounded-t-lg border-b-2 px-3 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring cursor-pointer",
              activeTab === tab.id
                ? "border-navy text-navy"
                : "border-transparent text-muted hover:text-navy",
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

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

      {canOperateSchedule && actionError && (
        <div
          role="alert"
          className="rounded-xl border border-orange/30 bg-orange/10 px-4 py-2.5 text-xs text-navy"
        >
          {actionError}
        </div>
      )}
      {canOperateSchedule && actionNotice && (
        <div
          role="status"
          className="rounded-xl border border-teal/40 bg-teal/15 px-4 py-2.5 text-xs text-navy"
        >
          {actionNotice}
        </div>
      )}

      <div
        role="tabpanel"
        id="scheduling-panel-board"
        aria-labelledby="scheduling-tab-board"
        hidden={activeTab !== "board"}
        className="space-y-6"
      >
        {activeTab === "board" && !isLoading && !loadError && (
          <>
            {canOperateSchedule && (
              <SchedulingLifecycleStatus
                staleCount={staleCount}
                inputRevision={inputRevision}
                stalePrograms={stalePrograms}
                staleClasses={staleClasses}
                generationResult={generationResult}
                finalizeResult={finalizeResult}
                generationScopeLabel={generationScopeLabel}
              />
            )}

            <section
              aria-labelledby="scheduling-controls-title"
              className="space-y-3 rounded-xl border border-border bg-surface p-4"
            >
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="space-y-1">
                  <h2
                    id="scheduling-controls-title"
                    className="font-heading text-base font-bold text-navy"
                  >
                    {canOperateSchedule
                      ? "Kontrol Penjadwalan"
                      : "Tampilan jadwal"}
                  </h2>
                </div>
                <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row sm:items-end">
                  <label className="flex flex-col gap-1 text-xs font-semibold text-navy">
                    Filter program studi
                    <select
                      value={selectedProgramId}
                      onChange={(event) =>
                        setSelectedProgramId(event.target.value)
                      }
                      className="min-h-11 rounded-lg border border-input bg-surface px-3 text-xs font-normal text-navy disabled:cursor-not-allowed disabled:bg-background"
                    >
                      <>
                        <option value="">Semua program studi</option>
                        <option value={LINTAS_PRODI_FILTER}>
                          Lintas prodi
                        </option>
                        {programs.map((program) => {
                          const label = programLabels.get(
                            program.study_program_id,
                          )
                          return (
                            <option
                              key={program.study_program_id}
                              value={program.study_program_id}
                            >
                              {[
                                label?.code ?? program.study_program_code,
                                label?.name,
                              ]
                                .filter(Boolean)
                                .join(" ") || "Program studi"}
                            </option>
                          )
                        })}
                      </>
                    </select>
                  </label>
                  {isOrdinaryLecturer && (
                    <label className="flex flex-col gap-1 text-xs font-semibold text-navy">
                      Cakupan kelas
                      <select
                        value={classScope}
                        onChange={(event) =>
                          setClassScope(event.target.value as "all" | "mine")
                        }
                        className="min-h-11 rounded-lg border border-input bg-surface px-3 text-xs font-normal text-navy"
                      >
                        <option value="all">Semua kelas</option>
                        <option value="mine">Kelas Saya</option>
                      </select>
                    </label>
                  )}
                </div>
              </div>
              <p className="mt-2 text-xs text-muted">
                {canOperateSchedule
                  ? `Tampilan: ${viewScopeLabel}. Aksi penjadwalan draf: ${actionScopeLabel}. ${blockingConflictCount} bentrok ruang/dosen, ${scopedUnassigned.length} kelas belum terjadwal.`
                  : "Pilih program studi atau Kelas Saya. Tampilan ini hanya-baca."}
              </p>

              {canOperateSchedule && (
                <>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted">
                    <span>{unmappedRoomCount} ruangan belum dipetakan</span>
                    <span>{unmappedLecturerCount} dosen belum dipetakan</span>
                    <span>{emptySectionCount} kelas tanpa blok jadwal</span>
                  </div>
                  <ul
                    aria-label="Status penjadwalan per program studi"
                    className="flex flex-wrap gap-2"
                  >
                    {programs
                      .filter(
                        (program) =>
                          !isPjProdi ||
                          program.study_program_id === actorStudyProgramId,
                      )
                      .map((program) => {
                        const isActorProgram =
                          actorStudyProgramId !== null &&
                          program.study_program_id === actorStudyProgramId
                        return (
                          <li
                            key={program.study_program_id}
                            className={cn(
                              "inline-flex flex-wrap items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px]",
                              isActorProgram
                                ? "border-navy/30 bg-navy/10 text-navy"
                                : "border-border text-muted",
                            )}
                          >
                            <span className="font-mono font-semibold">
                              {[
                                program.study_program_code,
                                programLabels.get(program.study_program_id)
                                  ?.name,
                              ]
                                .filter(Boolean)
                                .join(" ") || "Program studi"}
                            </span>
                            <span>{program.label || program.state}</span>
                            <span className="font-semibold">
                              {program.state === "final" ? "final" : "draft"}
                            </span>
                            {program.is_stale && (
                              <span className="font-semibold text-orange">
                                Jadwal stale
                              </span>
                            )}
                            {isActorProgram && (
                              <span className="font-semibold text-navy">
                                Prodi Anda
                              </span>
                            )}
                          </li>
                        )
                      })}
                  </ul>

                  <div className="flex flex-wrap items-center gap-2">
                    {!isCurrentScopeFinal && (
                      <button
                        type="button"
                        onClick={() => void runGenerate("regenerate")}
                        disabled={busyAction !== null || !periodId}
                        className="inline-flex min-h-11 items-center rounded-lg bg-navy px-4 text-xs font-semibold text-white transition-colors hover:bg-navy-light disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold cursor-pointer disabled:cursor-not-allowed"
                      >
                        Buat ulang jadwal
                      </button>
                    )}
                    {isAdmin && !isCurrentScopeFinal && (
                      <button
                        type="button"
                        onClick={() => {
                          setActionError(null)
                          setConfirmAction("reset")
                        }}
                        disabled={busyAction !== null || !periodId}
                        className="inline-flex min-h-11 items-center rounded-lg border border-orange/40 px-4 text-xs font-semibold text-orange transition-colors hover:bg-orange/10 disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold cursor-pointer disabled:cursor-not-allowed"
                      >
                        Reset &amp; generate ulang
                      </button>
                    )}
                    {isPjProdi && !isCurrentScopeFinal && (
                      <>
                        <button
                          type="button"
                          onClick={() => void runFinalize()}
                          disabled={
                            busyAction !== null ||
                            !periodId ||
                            finalizeBlockers.length > 0
                          }
                          className="inline-flex min-h-11 items-center rounded-lg bg-gold px-4 text-xs font-semibold text-navy-dark transition-colors hover:bg-gold-hover disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold cursor-pointer disabled:cursor-not-allowed"
                        >
                          Finalisasi jadwal
                        </button>
                        <p
                          role="status"
                          className="w-full text-xs text-muted sm:w-auto"
                        >
                          {finalizeBlockers.length > 0
                            ? `Finalisasi diblokir: ${finalizeBlockers.join(", ")}.`
                            : "Siap difinalisasi. Tidak ada blocker pada cakupan prodi ini."}
                        </p>
                      </>
                    )}
                    {isAdmin &&
                      (isFinal ||
                        programs.some(
                          (program) => program.state === "final",
                        )) && (
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
                    {isCurrentScopeFinal && !isAdmin && (
                      <p className="text-xs text-muted">
                        Jadwal sudah final. Perubahan memerlukan pembukaan kunci
                        oleh admin.
                      </p>
                    )}
                  </div>
                </>
              )}
            </section>

            {canOperateSchedule && editDraft && (
              <section
                aria-labelledby="class-edit-title"
                className="rounded-xl border border-navy/20 bg-surface p-4"
              >
                <h3
                  id="class-edit-title"
                  className="font-heading text-base font-bold text-navy"
                >
                  Ubah jadwal {editDraft.item.course_code},{" "}
                  {editDraft.item.section_code}
                </h3>
                <p className="mb-3 text-xs text-muted">
                  {editDraft.item.course_name}, blok {editDraft.item.credits}{" "}
                  jam
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
                            ? {
                                ...draft,
                                start_hour: Number(event.target.value),
                              }
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
                  <div className="flex flex-col gap-1">
                    <SearchableCombobox
                      id="class-edit-room"
                      label="Ruangan"
                      options={roomOptions}
                      value={editDraft.room_id}
                      onChange={(roomId) => {
                        setEditDraft((draft) =>
                          draft ? { ...draft, room_id: roomId } : draft,
                        )
                        setEditRoomError(null)
                      }}
                      placeholder="Pilih ruangan"
                      searchPlaceholder="Cari ruangan"
                      emptyLabel="Tidak ada ruangan yang cocok."
                      invalid={Boolean(editRoomError)}
                      errorId={
                        editRoomError ? "class-edit-room-error" : undefined
                      }
                    />
                    <FormFieldError
                      id="class-edit-room-error"
                      message={editRoomError}
                    />
                  </div>
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
                      placeholder="Contoh: menyesuaikan Preferensi Jadwal"
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
                      onClick={requestCloseEdit}
                      className="min-h-11 rounded-lg border border-border px-4 text-xs font-semibold text-navy transition-colors hover:bg-accent cursor-pointer"
                    >
                      Batal
                    </button>
                  </div>
                </form>
              </section>
            )}

            <div className="space-y-3">
              {canOperateSchedule &&
                (data?.classes.length ?? 0) > 0 &&
                (data?.classes.every((item) => !item.day_of_week) ?? false) && (
                  <div
                    role="alert"
                    className="flex items-center gap-2 rounded-xl border border-orange/30 bg-orange/10 px-4 py-2.5 text-xs text-navy"
                  >
                    <AlertCircle
                      className="h-4 w-4 shrink-0 text-orange"
                      aria-hidden="true"
                    />
                    Jadwal ada tetapi belum memiliki hari; muat ulang setelah
                    perbaikan backend.
                  </div>
                )}
              <BoardGrid
                classes={allClasses}
                conflicts={conflicts}
                selectedProgramId={selectedProgramId || null}
                mineOnly={isOrdinaryLecturer && classScope === "mine"}
                assignedLecturerId={user?.user_id ?? null}
                canEditClass={canEditClass}
                onEditClass={openEdit}
              />
            </div>

            {canOperateSchedule && (
              <>
                <section
                  aria-labelledby="conflict-list-title"
                  className="space-y-3"
                >
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
                      Tidak ada bentrok ruang/dosen.
                    </p>
                  ) : (
                    <ul className="divide-y divide-border rounded-xl border border-danger/30 bg-surface">
                      {visibleConflictRows.map(renderConflictRow)}
                    </ul>
                  )}
                  {visibleConflictRows.length > 0 && (
                    <p className="rounded-lg border border-border bg-background px-3 py-2 text-xs text-muted">
                      Hubungi PJ Prodi melalui kanal resmi untuk menindaklanjuti
                      bentrok. Aplikasi tidak menyediakan kontak atau
                      rekomendasi dosen.
                    </p>
                  )}
                </section>

                <section
                  aria-labelledby="diagnostics-title"
                  className="space-y-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h2
                      id="diagnostics-title"
                      className="font-heading text-base font-bold text-navy"
                    >
                      Kelas Belum Terjadwal
                    </h2>
                    <span className="rounded-full border border-orange/30 bg-orange/10 px-2.5 py-1 text-[11px] font-semibold text-orange">
                      {scopedUnassigned.length} kelas
                    </span>
                  </div>
                  <UnassignedClassList
                    items={scopedUnassigned}
                    onMapping={openMappingForUnassigned}
                    onAssignment={openAssignmentForUnassigned}
                    onDiagnostic={setDiagnosticItem}
                  />
                </section>
              </>
            )}
          </>
        )}
      </div>

      <div
        role="tabpanel"
        id="scheduling-panel-rooms"
        aria-labelledby="scheduling-tab-rooms"
        hidden={activeTab !== "rooms"}
        className="rounded-xl border border-border bg-surface p-4"
      >
        {activeTab === "rooms" && isAdmin && <RoomAdminPanel />}
      </div>
      <div
        role="tabpanel"
        id="scheduling-panel-deadlines"
        aria-labelledby="scheduling-tab-deadlines"
        hidden={activeTab !== "deadlines"}
        className="rounded-xl border border-border bg-surface p-4"
      >
        {activeTab === "deadlines" && (isAdmin || isPjProdi) && (
          <PreferenceDeadlinePanel />
        )}
      </div>

      {diagnosticItem && (
        <UnassignedDiagnosticDialog
          item={diagnosticItem}
          onClose={() => setDiagnosticItem(null)}
        />
      )}

      {discardDialog}

      {confirmAction === "reset" && (
        <ConfirmDialog
          title="Reset dan generate ulang jadwal?"
          body={
            <p className="text-xs text-muted">
              Penjadwalan draf untuk {actionScopeLabel} akan dibuat ulang.
              Periksa cakupan dan hasilnya sebelum finalisasi.
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
