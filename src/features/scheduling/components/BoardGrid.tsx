import { Pencil } from "lucide-react"
import { cn } from "@/shared/utils"
import type { BoardClassItem, BoardConflictItem } from "../schedulingService"

const DAYS = [
  { day: 1, label: "Senin" },
  { day: 2, label: "Selasa" },
  { day: 3, label: "Rabu" },
  { day: 4, label: "Kamis" },
  { day: 5, label: "Jumat" },
] as const

const START_HOUR = 7
const END_HOUR = 17
const HOUR_HEIGHT_PX = 64
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

function clockLabel(hour: number): string {
  return `${String(hour).padStart(2, "0")}.00`
}

function conflictTimeLabel(conflict: BoardConflictItem): string {
  const day = DAYS.find((entry) => entry.day === conflict.day_of_week)
  const dayLabel = day ? day.label : `Hari ${conflict.day_of_week}`
  return `${dayLabel} ${clockLabel(conflict.start_hour)}-${clockLabel(conflict.end_hour)}`
}

export function conflictMarkerLabel(conflict: BoardConflictItem): string {
  return `Bentrok ${conflictTimeLabel(conflict)}`
}

export function conflictKindLabel(kind: BoardConflictItem["kind"]): string {
  return CONFLICT_KIND_LABEL[kind]
}

export interface BoardGridProps {
  classes: BoardClassItem[]
  conflicts?: BoardConflictItem[]
  selectedProgramId?: string | null
  canEditClass?: (item: BoardClassItem) => boolean
  onEditClass?: (item: BoardClassItem) => void
  className?: string
}

export default function BoardGrid({
  classes,
  conflicts = [],
  selectedProgramId = null,
  canEditClass,
  onEditClass,
  className,
}: BoardGridProps) {
  const visibleClasses = selectedProgramId
    ? classes.filter((item) => item.study_program_id === selectedProgramId)
    : classes
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
        <div className="flex flex-wrap items-center gap-3 text-[11px] text-muted">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-sm border border-navy/25 bg-accent" />
            Terjadwal
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-sm border border-danger/40 bg-danger/10" />
            Bentrok
          </span>
        </div>
      </div>

      {visibleClasses.length === 0 && (
        <p
          role="status"
          className="rounded-lg border border-border bg-background px-3 py-2 text-xs text-muted"
        >
          Belum ada kelas yang ditempatkan pada tampilan ini.
        </p>
      )}

      <div className="overflow-x-auto rounded-xl border border-border bg-surface">
        <div
          role="grid"
          aria-label="Jadwal mingguan Senin sampai Jumat, pukul 07.00 sampai 17.00"
          aria-rowcount={HOUR_ROWS.length + 1}
          aria-colcount={DAYS.length + 1}
          className="min-w-[60rem]"
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
              {DAYS.map((day) => (
                <div
                  key={`${day.day}-${hour}`}
                  role="gridcell"
                  aria-label={`${day.label} ${timeLabel(hour)}`}
                  className="relative h-16 border-l border-border"
                >
                  {visibleClasses
                    .filter(
                      (item) =>
                        item.day_of_week === day.day &&
                        item.start_hour === hour &&
                        item.end_hour > hour,
                    )
                    .map((item) => {
                      const sectionConflicts =
                        conflictsBySection.get(item.class_section_id) ?? []
                      const isConflict = sectionConflicts.length > 0
                      const clashText = sectionConflicts
                        .map(conflictMarkerLabel)
                        .join(", ")
                      const canEdit =
                        Boolean(onEditClass) && canEditClass?.(item) === true
                      const endHour = Math.min(item.end_hour, END_HOUR)
                      const scheduledMinutes = (endHour - item.start_hour) * 60
                      const blockHeight =
                        Math.max(1, endHour - item.start_hour) * HOUR_HEIGHT_PX
                      const lecturers =
                        item.lecturers.length > 0
                          ? item.lecturers.join(", ")
                          : "Dosen belum ditentukan"
                      const loadMinutes = item.face_to_face_minutes

                      return (
                        <div
                          key={item.class_section_id}
                          role="group"
                          aria-label={`${item.course_code} ${item.course_name}, kelas ${item.section_code}, ${lecturers}, ${item.room_code ?? "ruangan belum ditentukan"}${
                            isConflict ? `, ${clashText}` : ""
                          }`}
                          style={{ height: blockHeight }}
                          title={isConflict ? clashText : undefined}
                          className={cn(
                            "absolute inset-x-1 top-0 z-10 flex flex-col gap-0.5 overflow-hidden rounded-lg border px-2 py-1 text-left shadow-2xs",
                            isConflict
                              ? "border-danger/50 bg-danger/10 text-navy"
                              : "border-navy/20 bg-accent text-navy",
                          )}
                        >
                          <p className="font-mono text-[10px] font-semibold leading-tight">
                            {item.course_code}
                          </p>
                          <p
                            title={item.course_name}
                            className="truncate text-xs font-semibold leading-tight"
                          >
                            {item.course_name}
                          </p>
                          <p className="truncate text-[10px] leading-tight">
                            {item.section_code} · {lecturers}
                          </p>
                          <p
                            title={`Blok ${scheduledMinutes} menit · Tatap muka ${loadMinutes} menit (${item.credits} SKS)`}
                            className="truncate text-[10px] leading-tight"
                          >
                            {item.room_code ?? "Ruangan belum ditentukan"} ·
                            Tatap muka {loadMinutes} menit
                          </p>
                          <div className="mt-auto flex items-center justify-between gap-1">
                            {isConflict && (
                              <span
                                title={clashText}
                                className="min-w-0 truncate rounded bg-danger/20 px-1.5 py-0.5 text-[10px] font-semibold text-danger"
                              >
                                {clashText}
                              </span>
                            )}
                            {canEdit && onEditClass && (
                              <button
                                type="button"
                                onClick={() => onEditClass(item)}
                                aria-label={`Ubah jadwal ${item.course_code} kelas ${item.section_code}`}
                                title="Ubah jadwal kelas"
                                className="ml-auto inline-flex min-h-7 min-w-7 items-center justify-center rounded-md border border-navy/25 bg-surface/80 text-navy transition-colors hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold cursor-pointer"
                              >
                                <Pencil
                                  className="h-3.5 w-3.5"
                                  aria-hidden="true"
                                />
                              </button>
                            )}
                          </div>
                        </div>
                      )
                    })}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
