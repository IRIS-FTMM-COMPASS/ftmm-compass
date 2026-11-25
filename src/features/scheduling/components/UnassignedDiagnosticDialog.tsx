import { useEffect, useRef } from "react"
import { X } from "lucide-react"
import type { UnassignedItem } from "../schedulingService"

interface DiagnosticCopy {
  title: string
  guidance: string
}

function diagnosticCopy(item: UnassignedItem): DiagnosticCopy {
  if (
    item.action === "open_room_detail" ||
    item.reason_code === "room_capacity" ||
    item.reason_code === "no_room"
  ) {
    return {
      title: "Detail kendala ruangan",
      guidance:
        "Kelas belum mendapatkan ruangan yang memenuhi aturan kapasitas atau kepemilikan program studi. Tinjau data ruangan bersama admin melalui kanal resmi.",
    }
  }
  if (
    item.action === "open_course_detail" ||
    item.reason_code === "course_locked" ||
    item.reason_code === "parity_mismatch"
  ) {
    return {
      title: "Detail kendala mata kuliah",
      guidance:
        item.reason_code === "course_locked"
          ? "Mata kuliah terkunci sehingga belum dapat dijadwalkan. PJ Prodi perlu meninjau penguncian melalui kanal resmi."
          : "Paritas kelas belum sesuai dengan aturan program studi. Hubungi PJ Prodi melalui kanal resmi untuk meninjau kelas ini.",
    }
  }
  if (item.reason_code === "curriculum_context_required") {
    return {
      title: "Detail konteks kurikulum",
      guidance:
        "Konteks kurikulum kelas perlu ditentukan oleh admin atau PJ Prodi penanggung jawab sebelum Assignment Pengajar dapat diubah.",
    }
  }
  return {
    title: "Detail kelas belum terjadwal",
    guidance:
      "Hubungi PJ Prodi melalui kanal resmi untuk meninjau kendala penjadwalan kelas ini.",
  }
}

interface UnassignedDiagnosticDialogProps {
  item: UnassignedItem
  onClose: () => void
}

export default function UnassignedDiagnosticDialog({
  item,
  onClose,
}: UnassignedDiagnosticDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const closeRef = useRef<HTMLButtonElement>(null)
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose
  const copy = diagnosticCopy(item)

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

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="unassigned-diagnostic-title"
      aria-describedby="unassigned-diagnostic-description"
      onCancel={(event) => {
        event.preventDefault()
        onCloseRef.current()
      }}
      className="m-auto max-h-[calc(100dvh_-_2rem)] w-[calc(100%_-_2rem)] max-w-xl overflow-y-auto rounded-xl border border-border bg-surface p-0 text-navy shadow-xl backdrop:bg-black/50"
    >
      <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-border bg-surface p-4 sm:p-6">
        <div>
          <h2
            id="unassigned-diagnostic-title"
            className="font-heading text-lg font-bold text-navy"
          >
            {copy.title}
          </h2>
          <p
            id="unassigned-diagnostic-description"
            className="mt-1 text-sm text-muted"
          >
            {item.course_code} {item.course_name}, kelas {item.section_code}
          </p>
        </div>
        <button
          ref={closeRef}
          type="button"
          onClick={() => onCloseRef.current()}
          aria-label="Tutup detail kendala"
          className="inline-flex min-h-11 min-w-11 shrink-0 items-center justify-center rounded-lg border border-border bg-surface text-navy hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold cursor-pointer"
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>

      <div className="space-y-4 p-4 sm:p-6">
        <section
          aria-labelledby="unassigned-reason-title"
          className="space-y-2"
        >
          <h3
            id="unassigned-reason-title"
            className="font-heading text-base font-bold text-navy"
          >
            Alasan penjadwalan
          </h3>
          <p className="rounded-lg border border-orange/30 bg-orange/10 p-3 text-sm text-navy">
            {item.reason || "Alasan tidak tersedia dari sistem penjadwalan."}
          </p>
          <p className="text-sm text-muted">{copy.guidance}</p>
        </section>

        <section
          aria-labelledby="unassigned-program-title"
          className="space-y-2"
        >
          <h3
            id="unassigned-program-title"
            className="font-heading text-base font-bold text-navy"
          >
            Program studi terkait
          </h3>
          {item.programs.length > 0 ? (
            <ul className="space-y-2">
              {item.programs.map((program) => (
                <li
                  key={program.study_program_id}
                  className="rounded-lg border border-border bg-background p-3 text-sm text-navy"
                >
                  <span className="font-mono font-semibold">
                    {program.study_program_code}
                  </span>{" "}
                  {program.study_program_name}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted">
              Daftar program studi tidak tersedia.
            </p>
          )}
        </section>

        {item.eligible_curriculum_contexts.length > 0 && (
          <section
            aria-labelledby="unassigned-context-title"
            className="space-y-2"
          >
            <h3
              id="unassigned-context-title"
              className="font-heading text-base font-bold text-navy"
            >
              Konteks kurikulum
            </h3>
            <ul className="space-y-2">
              {item.eligible_curriculum_contexts.map((context) => (
                <li
                  key={context.curriculum_course_id}
                  className="rounded-lg border border-border bg-background p-3 text-sm text-navy"
                >
                  <p className="font-medium">
                    <span className="font-mono">{context.course_code}</span>{" "}
                    {context.course_name}
                  </p>
                  <p className="mt-1 text-xs text-muted">
                    <span className="font-mono">
                      {context.study_program_code}
                    </span>{" "}
                    {context.study_program_name}
                  </p>
                  <p className="mt-1 text-xs text-muted">
                    {context.pjmk_reference_id
                      ? "PJ MK tersedia"
                      : "PJ MK belum tersedia"}
                  </p>
                </li>
              ))}
            </ul>
          </section>
        )}

        <button
          type="button"
          onClick={() => onCloseRef.current()}
          className="inline-flex min-h-11 w-full items-center justify-center rounded-lg border border-navy bg-navy px-4 text-sm font-semibold text-white hover:bg-navy-light focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold cursor-pointer sm:w-auto"
        >
          Tutup
        </button>
      </div>
    </dialog>
  )
}
