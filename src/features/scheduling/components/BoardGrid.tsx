import { useState } from "react"
import { cn } from "@/shared/utils"
import ProdiBadge from "@/shared/ui/ProdiBadge"
import { PRODI_CODES, prodiTone } from "@/shared/domain/prodi"
import ClassDetailDialog from "./ClassDetailDialog"
import type {
  BoardClassItem,
  BoardClassProgram,
  BoardConflictItem,
} from "../schedulingService"

const DAYS = [
  { day: 1, label: "Senin" },
  { day: 2, label: "Selasa" },
  { day: 3, label: "Rabu" },
  { day: 4, label: "Kamis" },
  { day: 5, label: "Jumat" },
] as const

const START_HOUR = 7
const END_HOUR = 17
const HOUR_ROWS = Array.from(
  { length: END_HOUR - START_HOUR },
  (_, index) => START_HOUR + index,
)
const GRID_COLUMNS = "grid-cols-[4rem_repeat(5,minmax(0,1fr))]"

function timeLabel(hour: number): string {
  return `${String(hour).padStart(2, "0")}:00`
}

const CONFLICT_KIND_LABEL: Record<BoardConflictItem["kind"], string> = {
  lecturer: "Dosen",
  room: "Ruangan",
}

export const LINTAS_PRODI_FILTER = "__lintas_prodi__"

function clockLabel(hour: number): string {
  return `${String(hour).padStart(2, "0")}.00`
}

function conflictFallbackLabel(conflict: BoardConflictItem): string {
  const object = conflict.object_label || CONFLICT_KIND_LABEL[conflict.kind]
  const day = conflict.day_name || `Hari ${conflict.day_of_week}`
  return `Bentrok ${object}: ${conflict.class_section_a_label} dengan ${conflict.class_section_b_label}, ${day} ${clockLabel(conflict.start_hour)}-${clockLabel(conflict.end_hour)}`
}

export function conflictMarkerLabel(conflict: BoardConflictItem): string {
  return conflict.label || conflictFallbackLabel(conflict)
}

export function conflictKindLabel(kind: BoardConflictItem["kind"]): string {
  return CONFLICT_KIND_LABEL[kind]
}

function programsFor(item: BoardClassItem): BoardClassProgram[] {
  if (item.programs.length > 0) return item.programs
  return [
    {
      study_program_id: item.study_program_id,
      study_program_code: item.study_program_code,
      study_program_name:
        item.study_program_name || "Nama program studi tidak tersedia",
      state: item.state,
      label: item.state,
    },
  ]
}

function programNamesFor(item: BoardClassItem): string {
  return programsFor(item)
    .map(
      (program) =>
        `${program.study_program_code} ${program.study_program_name}`,
    )
    .join(", ")
}

function ProdiScopeBadge({ item }: { item: BoardClassItem }) {
  const programs = programsFor(item)
  if (programs.length > 1) {
    const names = programNamesFor(item)
    return (
      <span
        aria-label={`${programs.length} program studi: ${names}`}
        title={names}
        className="inline-flex shrink-0 items-center rounded-full border border-border bg-secondary px-1.5 py-0.5 text-[10px] font-semibold text-muted"
      >
        {programs.length} prodi
      </span>
    )
  }
  return (
    <ProdiBadge
      code={programs[0]?.study_program_code ?? item.study_program_code}
      className="shrink-0"
    />
  )
}

interface BoardClassCardProps {
  item: BoardClassItem
  positionClass: string
  conflicts: BoardConflictItem[]
  isConflict: boolean
  canEdit: boolean
  onEdit?: (item: BoardClassItem) => void
}

function BoardClassCard({
  item,
  positionClass,
  conflicts,
  isConflict,
  canEdit,
  onEdit,
}: BoardClassCardProps) {
  const [detailsOpen, setDetailsOpen] = useState(false)
  const lecturers =
    item.assigned_lecturer_name ??
    (item.lecturers.length > 0
      ? item.lecturers.join(", ")
      : "Dosen belum ditentukan")
  const room = item.room_code ?? "Ruangan belum ditentukan"
  const blockMinutes = (item.end_hour - item.start_hour) * 60
  const programs = programsFor(item)
  const conflictDetails = conflicts.map(conflictMarkerLabel)
  const clashText = conflictDetails.join(", ")

  return (
    <div
      role="group"
      aria-label={`${item.course_code} ${item.course_name}, kelas ${item.section_code}, ${programNamesFor(item)}, ${lecturers}, ${room}, blok ${blockMinutes} menit, ${item.credits} SKS, tatap muka ${item.face_to_face_minutes} menit${
        isConflict ? `, ${clashText}` : ""
      }`}
      className={cn(
        "absolute top-1 bottom-1 flex min-h-0 flex-col gap-0.5 overflow-hidden rounded-lg border border-l-[3px] px-1.5 py-1 text-left shadow-2xs",
        positionClass,
        isConflict
          ? "border-danger/50 bg-danger/10 text-navy"
          : "border-navy/20 bg-accent text-navy",
      )}
      style={{
        borderLeftColor: prodiTone(programs[0]?.study_program_code).leftVar,
      }}
    >
      <button
        type="button"
        onClick={() => setDetailsOpen(true)}
        aria-haspopup="dialog"
        aria-label={`${item.course_code} ${item.course_name}, kelas ${item.section_code}. Tampilkan detail kelas`}
        title={`${item.course_code}, ${item.course_name}, ${programNamesFor(item)}`}
        className="flex min-w-0 flex-1 flex-col gap-0.5 overflow-hidden rounded-sm text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold"
      >
        <span className="flex items-center justify-between gap-1">
          <span className="truncate font-mono text-[10px] font-semibold leading-tight">
            {item.course_code}
          </span>
          <ProdiScopeBadge item={item} />
        </span>
        <span className="truncate text-[10px] font-semibold leading-tight">
          {item.course_name}
        </span>
      </button>

      {detailsOpen && (
        <ClassDetailDialog
          item={item}
          conflicts={conflicts}
          canEdit={canEdit}
          onEdit={onEdit}
          onClose={() => setDetailsOpen(false)}
        />
      )}
    </div>
  )
}

export interface BoardGridProps {
  classes: BoardClassItem[]
  conflicts?: BoardConflictItem[]
  selectedProgramId?: string | null
  mineOnly?: boolean
  assignedLecturerId?: string | null
  canEditClass?: (item: BoardClassItem) => boolean
  onEditClass?: (item: BoardClassItem) => void
  className?: string
}

export default function BoardGrid({
  classes,
  conflicts = [],
  selectedProgramId = null,
  mineOnly = false,
  assignedLecturerId = null,
  canEditClass,
  onEditClass,
  className,
}: BoardGridProps) {
  const visibleClasses = classes.filter((item) => {
    const matchesSelectedProgram = selectedProgramId
      ? selectedProgramId === LINTAS_PRODI_FILTER
        ? item.programs.length > 1
        : item.programs.some(
            (program) => program.study_program_id === selectedProgramId,
          ) ||
          (!item.programs.length && item.study_program_id === selectedProgramId)
      : true
    const matchesLecturer =
      !mineOnly ||
      (assignedLecturerId !== null &&
        item.assigned_lecturer_id === assignedLecturerId)
    return matchesSelectedProgram && matchesLecturer
  })
  const visibleIds = new Set(
    visibleClasses.map((item) => item.class_section_id),
  )
  const conflictsBySection = new Map<string, BoardConflictItem[]>()
  conflicts.forEach((conflict) => {
    const sectionIds = [
      conflict.class_section_a_id,
      conflict.class_section_b_id,
    ].filter((id) => visibleIds.has(id))
    sectionIds.forEach((id) => {
      const sectionConflicts = conflictsBySection.get(id) ?? []
      sectionConflicts.push(conflict)
      conflictsBySection.set(id, sectionConflicts)
    })
  })

  return (
    <section
      aria-labelledby="board-grid-title"
      className={cn("space-y-3", className)}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3
          id="board-grid-title"
          className="font-heading text-base font-bold text-navy"
        >
          Papan Jadwal Bersama
        </h3>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[11px] text-muted">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-sm border border-navy/25 bg-accent" />
            Terjadwal
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-sm border border-danger/40 bg-danger/10" />
            Bentrok
          </span>
          <span className="inline-flex flex-wrap items-center gap-1">
            <span>Prodi</span>
            {PRODI_CODES.map((code) => (
              <ProdiBadge key={code} code={code} />
            ))}
          </span>
          <span className="inline-flex flex-wrap items-center gap-1">
            <span>Jenis bentrok</span>
            {(Object.keys(
              CONFLICT_KIND_LABEL,
            ) as BoardConflictItem["kind"][]).map((kind) => (
              <span
                key={kind}
                className="rounded-sm border border-danger/40 bg-danger/10 px-1.5 py-0.5 text-[10px] font-semibold text-danger"
              >
                {conflictKindLabel(kind)}
              </span>
            ))}
          </span>
        </div>
      </div>

      {visibleClasses.length === 0 && (
        <p
          role="status"
          className="rounded-lg border border-border bg-background px-3 py-2 text-xs text-muted"
        >
          {mineOnly
            ? "Tidak ada kelas yang ditugaskan kepada Anda pada filter ini."
            : "Belum ada kelas yang ditempatkan pada filter ini."}
        </p>
      )}

      <div
        role="region"
        aria-label="Papan jadwal mingguan, geser horizontal untuk melihat semua hari"
        tabIndex={0}
        className="overflow-x-auto rounded-xl border border-border bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold"
      >
        <div
          role="grid"
          aria-label="Jadwal mingguan Senin sampai Jumat, pukul 07.00 sampai 17.00"
          aria-rowcount={HOUR_ROWS.length + 1}
          aria-colcount={DAYS.length + 1}
          className="min-w-[64rem]"
        >
          <div
            role="row"
            className={cn(
              "grid border-b border-border bg-background",
              GRID_COLUMNS,
            )}
          >
            <div
              role="columnheader"
              className="px-2 py-2 text-center font-mono text-[10px] font-semibold uppercase tracking-wider text-muted"
            >
              Jam
            </div>
            {DAYS.map((day) => (
              <div
                key={day.day}
                role="columnheader"
                className="border-l border-border px-2 py-2 text-center font-heading text-xs font-semibold text-navy"
              >
                {day.label}
              </div>
            ))}
          </div>

          {HOUR_ROWS.map((hour) => (
            <div
              key={hour}
              role="row"
              className={cn(
                "grid border-b border-border last:border-b-0",
                GRID_COLUMNS,
              )}
            >
              <div
                role="rowheader"
                className="px-2 pt-1 font-mono text-[10px] text-muted"
              >
                {timeLabel(hour)}
              </div>
              {DAYS.map((day) => {
                const cellClasses = visibleClasses.filter(
                  (item) =>
                    item.day_of_week === day.day &&
                    item.start_hour === hour &&
                    item.end_hour > hour,
                )
                const shownClasses = cellClasses.slice(0, 2)
                const extraClasses = cellClasses.slice(2)
                const extraCodes = extraClasses
                  .map((item) => item.course_code)
                  .join(", ")

                return (
                  <div
                    key={`${day.day}-${hour}`}
                    role="gridcell"
                    aria-label={`${day.label} ${timeLabel(hour)}`}
                    className="relative h-16 border-l border-border"
                  >
                    {shownClasses.map((item, index) => {
                      const sectionConflicts =
                        conflictsBySection.get(item.class_section_id) ?? []
                      const isCompact = shownClasses.length > 1
                      const positionClass = isCompact
                        ? index === 0
                          ? "left-1 right-1/2"
                          : "left-1/2 right-1"
                        : "inset-x-1"
                      const canEdit =
                        item.can_edit &&
                        !item.read_only &&
                        Boolean(onEditClass) &&
                        canEditClass?.(item) === true

                      return (
                        <BoardClassCard
                          key={item.class_section_id}
                          item={item}
                          positionClass={positionClass}
                          conflicts={sectionConflicts}
                          isConflict={sectionConflicts.length > 0}
                          canEdit={canEdit}
                          onEdit={canEdit ? onEditClass : undefined}
                        />
                      )
                    })}
                    {extraClasses.length > 0 && (
                      <span
                        aria-label={`${extraClasses.length} kelas lainnya: ${extraCodes}`}
                        title={extraCodes}
                        className="absolute bottom-1 right-1 z-20 max-w-[45%] truncate rounded bg-navy/90 px-1.5 py-0.5 text-[9px] font-semibold text-white"
                      >
                        +{extraClasses.length} kelas
                      </span>
                    )}
                  </div>
                )
              })}
            </div>
          ))}
        </div>
      </div>

      {conflictsBySection.size > 0 && (
        <p className="rounded-lg border border-border bg-background px-3 py-2 text-xs text-muted">
          Untuk menindaklanjuti bentrok, hubungi PJ Prodi melalui kanal resmi.
          Aplikasi tidak menyediakan kontak atau rekomendasi dosen.
        </p>
      )}
    </section>
  )
}
