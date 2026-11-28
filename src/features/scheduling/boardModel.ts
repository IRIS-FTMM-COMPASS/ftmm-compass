import type { AuthUser } from "@/features/auth/authService"
import { canManageSchedule } from "@/features/auth/access"
import { LINTAS_PRODI_FILTER } from "./components/BoardGrid"
import type {
  BoardClassItem,
  BoardConflictItem,
  BoardProgramStatus,
  BoardResponse,
  UnassignedItem,
} from "./schedulingService"

export const IN_PROGRESS_LABEL = "Jadwal masih dalam proses"
export const FINAL_LABEL = "Jadwal final"

export type ClassScope = "all" | "mine"

export interface ProgramLabel {
  code: string
  name: string
}

export interface VisibleConflictRow {
  key: string
  classA?: BoardClassItem
  classB?: BoardClassItem
  conflict: BoardConflictItem
}

export interface SchedulingModelInput {
  board: BoardResponse | null
  user: AuthUser | null
  selectedProgramId: string
  classScope: ClassScope
  isFinal: boolean
}

export interface SchedulingModel {
  programs: BoardProgramStatus[]
  allClasses: BoardClassItem[]
  unassigned: UnassignedItem[]
  programLabels: Map<string, ProgramLabel>
  selectedProgram?: BoardProgramStatus
  scopedProgram?: BoardProgramStatus
  scopedPrograms: BoardProgramStatus[]
  actorStudyProgramId: string | null
  effectiveProgramId: string
  isAdmin: boolean
  isPjProdi: boolean
  canOperateSchedule: boolean
  isOrdinaryLecturer: boolean
  isCurrentScopeFinal: boolean
  isCurrentScopeMixed: boolean
  isPeriodFinal: boolean
  hasFinalProgram: boolean
  statusLabel: string
  scopeLabel: string
  viewScopeLabel: string
  actionScopeLabel: string
  generationTargetProgramId?: string
  periodId: string
  scopedClasses: BoardClassItem[]
  scopedUnassigned: UnassignedItem[]
  visibleConflictRows: VisibleConflictRow[]
  blockingConflictCount: number
  unmappedRoomCount: number
  unmappedLecturerCount: number
  emptySectionCount: number
  staleClasses: BoardClassItem[]
  stalePrograms: BoardProgramStatus[]
  staleCount: number
  requiresRegeneration: boolean
  inputRevision: number | null
  finalizeBlockers: string[]
  canGenerate: boolean
  canEditClass: (item: BoardClassItem) => boolean
}

function readNumber(
  meta: Record<string, unknown> | undefined,
  key: string,
): number {
  const value = meta?.[key]
  return typeof value === "number" && Number.isFinite(value) ? value : 0
}

export function matchesProgram(
  item: BoardClassItem,
  programId: string,
): boolean {
  if (!programId) return true
  if (programId === LINTAS_PRODI_FILTER) {
    return item.programs.length > 1
  }
  return item.programs.length > 0
    ? item.programs.some((program) => program.study_program_id === programId)
    : item.study_program_id === programId
}

function formatProgramLabel(label: ProgramLabel): string {
  return [label.code, label.name].filter(Boolean).join(" ")
}

export function scopeLabelForProgram(
  labels: Map<string, ProgramLabel>,
  studyProgramId: string | null,
): string {
  if (!studyProgramId) return "semua program studi"
  const label = labels.get(studyProgramId)
  return label ? formatProgramLabel(label) : "program studi terpilih"
}

export function buildSchedulingModel({
  board,
  user,
  selectedProgramId,
  classScope,
  isFinal,
}: SchedulingModelInput): SchedulingModel {
  const isAdmin = user?.role === "admin"
  const isPjProdi = canManageSchedule(user) && !isAdmin
  const canOperateSchedule = isAdmin || isPjProdi
  const isOrdinaryLecturer = user?.role === "lecturer" && !isPjProdi

  const data = board?.data
  const programs = data?.programs ?? []
  const allClasses = data?.classes ?? []
  const unassigned = data?.unassigned ?? []
  const conflicts = data?.conflicts ?? []
  const boardMeta = board?.meta

  const programLabels = new Map<string, ProgramLabel>()
  for (const program of programs) {
    programLabels.set(program.study_program_id, {
      code: program.study_program_code,
      name: program.study_program_name ?? "",
    })
  }
  for (const item of allClasses) {
    for (const program of item.programs) {
      programLabels.set(program.study_program_id, {
        code: program.study_program_code,
        name: program.study_program_name,
      })
    }
  }
  for (const item of unassigned) {
    for (const program of item.programs) {
      programLabels.set(program.study_program_id, {
        code: program.study_program_code,
        name: program.study_program_name,
      })
    }
  }

  const selectedProgram = programs.find(
    (program) => program.study_program_id === selectedProgramId,
  )
  const actorStudyProgramId =
    typeof boardMeta?.actor_study_program_id === "string"
      ? boardMeta.actor_study_program_id
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
    ? formatProgramLabel({
        code: scopedProgram.study_program_code,
        name: programLabels.get(scopedProgram.study_program_id)?.name ?? "",
      })
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
  const actionScopeLabel = generationTargetProgramId
    ? scopeLabelForProgram(programLabels, generationTargetProgramId)
    : "semua program studi"
  const viewScopeLabel =
    selectedProgramId === LINTAS_PRODI_FILTER
      ? "Lintas prodi"
      : selectedProgram
        ? formatProgramLabel({
            code:
              programLabels.get(selectedProgramId)?.code ??
              selectedProgram.study_program_code,
            name: programLabels.get(selectedProgramId)?.name ?? "",
          })
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

  const classesById = new Map(
    allClasses.map((item) => [item.class_section_id, item]),
  )
  const visibleConflictRows = conflicts
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
    })
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

  const canEditClass = (item: BoardClassItem) => {
    if (item.read_only || !item.can_edit || item.state === "final") return false
    if (isPjProdi ? scopedProgram?.state === "final" : isCurrentScopeFinal) {
      return false
    }
    if (isAdmin) return true
    if (!isPjProdi || !actorStudyProgramId) return false
    return matchesProgram(item, actorStudyProgramId)
  }

  return {
    programs,
    allClasses,
    unassigned,
    programLabels,
    selectedProgram,
    scopedProgram,
    scopedPrograms,
    actorStudyProgramId,
    effectiveProgramId,
    isAdmin,
    isPjProdi,
    canOperateSchedule,
    isOrdinaryLecturer,
    isCurrentScopeFinal,
    isCurrentScopeMixed,
    isPeriodFinal: isFinal,
    hasFinalProgram: programs.some((program) => program.state === "final"),
    statusLabel,
    scopeLabel,
    viewScopeLabel,
    actionScopeLabel,
    generationTargetProgramId,
    periodId,
    scopedClasses,
    scopedUnassigned,
    visibleConflictRows,
    blockingConflictCount,
    unmappedRoomCount: readNumber(boardMeta, "unmapped_room_count"),
    unmappedLecturerCount: readNumber(boardMeta, "unmapped_lecturer_count"),
    emptySectionCount: readNumber(boardMeta, "empty_section_count"),
    staleClasses,
    stalePrograms,
    staleCount,
    requiresRegeneration,
    inputRevision,
    finalizeBlockers,
    canGenerate: canOperateSchedule,
    canEditClass,
  }
}
