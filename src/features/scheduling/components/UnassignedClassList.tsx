import type { UnassignedItem } from "../schedulingService"

interface UnassignedClassListProps {
  items: UnassignedItem[]
  onMapping: (item: UnassignedItem) => void
  onAssignment: (item: UnassignedItem) => void
  onDiagnostic: (item: UnassignedItem) => void
}

function actionLabel(action: string): string {
  if (action === "edit_pjmk") return "Perbaiki PJ MK"
  if (action === "open_pjmk_form") return "Tambah PJ MK"
  if (action === "open_assignment") return "Atur Assignment Pengajar"
  if (action === "open_room_detail") return "Detail ruangan"
  if (action === "open_course_detail") return "Detail mata kuliah"
  return "Detail kendala"
}

export default function UnassignedClassList({
  items,
  onMapping,
  onAssignment,
  onDiagnostic,
}: UnassignedClassListProps) {
  if (items.length === 0) {
    return (
      <p
        role="status"
        className="rounded-xl border border-teal/40 bg-teal/15 px-4 py-3 text-xs text-navy"
      >
        Semua kelas telah memiliki blok jadwal.
      </p>
    )
  }

  return (
    <ul className="divide-y divide-border rounded-xl border border-border bg-surface">
      {items.map((item) => (
        <li key={item.class_section_id} className="space-y-3 p-4">
          <div className="min-w-0">
            <p className="font-semibold text-navy">
              <span className="font-mono">
                {item.course_code || "Kode tidak tersedia"}
              </span>{" "}
              {item.course_name || "Nama mata kuliah tidak tersedia"}
            </p>
            <p className="mt-1 text-xs text-muted">
              Kelas {item.section_code || "tidak tersedia"}
            </p>
            {item.programs.length > 0 && (
              <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
                {item.programs.map((program) => (
                  <li key={program.study_program_id}>
                    <span className="font-mono">
                      {program.study_program_code}
                    </span>{" "}
                    {program.study_program_name}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <p className="rounded-lg border border-orange/30 bg-orange/10 px-3 py-2 text-sm text-navy">
            {item.reason || "Alasan tidak tersedia dari sistem penjadwalan."}
          </p>
          <button
            type="button"
            onClick={() => {
              if (
                item.action === "edit_pjmk" ||
                item.action === "open_pjmk_form"
              ) {
                onMapping(item)
              } else if (item.action === "open_assignment") {
                onAssignment(item)
              } else {
                onDiagnostic(item)
              }
            }}
            className="inline-flex min-h-11 items-center justify-center rounded-lg border border-navy bg-navy px-4 text-sm font-semibold text-white hover:bg-navy-light focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold cursor-pointer"
          >
            {actionLabel(item.action)}
          </button>
        </li>
      ))}
    </ul>
  )
}
