import UnassignedClassList from "./UnassignedClassList"
import type { UnassignedItem } from "../schedulingService"

interface SchedulingDiagnosticsSectionProps {
  items: UnassignedItem[]
  onMapping: (item: UnassignedItem) => void
  onAssignment: (item: UnassignedItem) => void
  onDiagnostic: (item: UnassignedItem) => void
}

export default function SchedulingDiagnosticsSection({
  items,
  onMapping,
  onAssignment,
  onDiagnostic,
}: SchedulingDiagnosticsSectionProps) {
  return (
    <section aria-labelledby="diagnostics-title" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2
          id="diagnostics-title"
          className="font-heading text-base font-bold text-navy"
        >
          Kelas Belum Terjadwal
        </h2>
        <span className="rounded-full border border-orange/30 bg-orange/10 px-2.5 py-1 text-[11px] font-semibold text-orange">
          {items.length} kelas
        </span>
      </div>
      <UnassignedClassList
        items={items}
        onMapping={onMapping}
        onAssignment={onAssignment}
        onDiagnostic={onDiagnostic}
      />
    </section>
  )
}
