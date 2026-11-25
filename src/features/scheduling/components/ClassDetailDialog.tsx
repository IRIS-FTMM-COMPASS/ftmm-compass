import { useEffect, useRef } from "react"
import { Pencil, X } from "lucide-react"
import { cn } from "@/shared/utils"
import type { BoardClassItem, BoardConflictItem } from "../schedulingService"

const DAYS = [
  { day: 1, label: "Senin" },
  { day: 2, label: "Selasa" },
  { day: 3, label: "Rabu" },
  { day: 4, label: "Kamis" },
  { day: 5, label: "Jumat" },
] as const

function stateLabel(state: string): string {
  if (state === "final") return "Final"
  if (state === "draft") return "Draf"
  if (state === "mixed") return "Campuran, ada program studi final dan draf"
  return "Status tidak tersedia"
}

function clockLabel(hour: number): string {
  return `${String(hour).padStart(2, "0")}.00`
}

interface ClassDetailDialogProps {
  item: BoardClassItem
  conflicts: BoardConflictItem[]
  canEdit: boolean
  onEdit?: (item: BoardClassItem) => void
  onClose: () => void
}

export default function ClassDetailDialog({
  item,
  conflicts,
  canEdit,
  onEdit,
  onClose,
}: ClassDetailDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const closeRef = useRef<HTMLButtonElement>(null)
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose

  useEffect(() => {
    const opener =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null
    const dialog = dialogRef.current
    if (!dialog) return
    dialog.showModal()
    closeRef.current?.focus()
    return () => {
      dialog.close()
      opener?.focus()
    }
  }, [])

  const day = DAYS.find((entry) => entry.day === item.day_of_week)
  const lecturers =
    item.assigned_lecturer_name ??
    (item.lecturers.length > 0
      ? item.lecturers.join(", ")
      : "Dosen belum ditentukan")
  const room = item.room_code ?? "Ruangan belum ditentukan"

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="class-detail-title"
      aria-describedby="class-detail-description"
      onCancel={(event) => {
        event.preventDefault()
        onCloseRef.current()
      }}
      className="m-auto max-h-[calc(100dvh_-_2rem)] w-[calc(100%_-_2rem)] max-w-lg overflow-y-auto rounded-xl border border-border bg-surface p-0 text-navy shadow-xl backdrop:bg-black/50"
    >
      <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-border bg-surface p-4 sm:p-6">
        <div className="min-w-0">
          <h2
            id="class-detail-title"
            className="font-heading text-lg font-bold text-navy"
          >
            {item.course_code} {item.course_name}
          </h2>
          <p id="class-detail-description" className="mt-1 text-sm text-muted">
            Detail kelas {item.section_code}
          </p>
        </div>
        <button
          ref={closeRef}
          type="button"
          onClick={() => onCloseRef.current()}
          aria-label="Tutup detail kelas"
          className="inline-flex min-h-11 min-w-11 shrink-0 items-center justify-center rounded-lg border border-border bg-surface text-navy hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold cursor-pointer"
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>

      <div className="space-y-4 p-4 sm:p-6">
        <dl className="space-y-3 text-sm">
          <div>
            <dt className="font-semibold text-navy">Program studi</dt>
            <dd className="mt-1">
              {item.programs.length > 0 ? (
                <ul className="space-y-2">
                  {item.programs.map((program) => (
                    <li
                      key={program.study_program_id}
                      className="rounded-lg border border-border bg-background p-3"
                    >
                      <p className="font-medium text-navy">
                        <span className="font-mono">
                          {program.study_program_code}
                        </span>{" "}
                        {program.study_program_name}
                      </p>
                      <p className="mt-1 text-xs text-muted">
                        Status: {stateLabel(program.state)}
                      </p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-muted">
                  Daftar program studi tidak tersedia.
                </p>
              )}
            </dd>
          </div>
          <div className="flex flex-wrap gap-x-8 gap-y-2">
            <div>
              <dt className="font-semibold text-navy">Status kelas</dt>
              <dd className="mt-1 text-muted">{stateLabel(item.state)}</dd>
            </div>
            <div>
              <dt className="font-semibold text-navy">Kelas</dt>
              <dd className="mt-1 text-muted">
                {item.section_code || "Tidak tersedia"}
              </dd>
            </div>
          </div>
          <div>
            <dt className="font-semibold text-navy">Dosen</dt>
            <dd className="mt-1 text-muted">{lecturers}</dd>
          </div>
          <div>
            <dt className="font-semibold text-navy">Ruangan</dt>
            <dd className="mt-1 text-muted">{room}</dd>
          </div>
          <div className="flex flex-wrap gap-x-8 gap-y-2">
            <div>
              <dt className="font-semibold text-navy">Hari</dt>
              <dd className="mt-1 text-muted">
                {day?.label ?? "Belum terjadwal"}
              </dd>
            </div>
            <div>
              <dt className="font-semibold text-navy">Jam</dt>
              <dd className="mt-1 text-muted">
                {item.day_of_week
                  ? `${clockLabel(item.start_hour)} sampai ${clockLabel(item.end_hour)}`
                  : "Belum terjadwal"}
              </dd>
            </div>
          </div>
          <div className="flex flex-wrap gap-x-8 gap-y-2">
            <div>
              <dt className="font-semibold text-navy">SKS</dt>
              <dd className="mt-1 text-muted">{item.credits} SKS</dd>
            </div>
            <div>
              <dt className="font-semibold text-navy">Tatap muka</dt>
              <dd className="mt-1 text-muted">
                {item.face_to_face_minutes} menit
              </dd>
            </div>
          </div>
        </dl>

        {conflicts.length > 0 && (
          <section aria-labelledby="class-conflict-title" className="space-y-2">
            <h3
              id="class-conflict-title"
              className="font-heading text-base font-bold text-navy"
            >
              Bentrok jadwal
            </h3>
            <ul className="space-y-2">
              {conflicts.map((conflict, index) => (
                <li
                  key={`${conflict.kind}-${conflict.object_id ?? conflict.object_label}-${index}`}
                  className="rounded-lg border border-danger/40 bg-danger/10 p-3 text-sm text-navy"
                >
                  {conflict.label}
                </li>
              ))}
            </ul>
            <p className="text-xs text-muted">
              Hubungi PJ Prodi melalui kanal resmi untuk menindaklanjuti
              bentrok. Aplikasi tidak menyediakan kontak atau rekomendasi dosen.
            </p>
          </section>
        )}

        {canEdit && onEdit && (
          <button
            type="button"
            onClick={() => {
              onCloseRef.current()
              onEdit(item)
            }}
            className={cn(
              "inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-navy px-4 text-sm font-semibold text-white hover:bg-navy-light focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold cursor-pointer sm:w-auto",
            )}
          >
            <Pencil className="h-4 w-4" aria-hidden="true" />
            Ubah jadwal
          </button>
        )}
      </div>
    </dialog>
  )
}
