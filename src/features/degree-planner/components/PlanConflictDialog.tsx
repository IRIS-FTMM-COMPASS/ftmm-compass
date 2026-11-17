import ModalShell from "@/shared/ui/course/ModalShell"
import type { PlanConflict } from "@/features/degree-planner/state/degreeDrafts"

interface PlanConflictDialogProps {
  conflict: PlanConflict | null
  onConfirm: () => void
  onCancel: () => void
}

export default function PlanConflictDialog({
  conflict,
  onConfirm,
  onCancel,
}: PlanConflictDialogProps) {
  if (!conflict) return null

  return (
    <ModalShell
      onClose={onCancel}
      labelledBy="plan-conflict-title"
      overlayClassName="backdrop-blur-xs"
      panelClassName="w-full max-w-md rounded-2xl border border-border bg-surface p-5 shadow-2xl"
    >
      <h2
        id="plan-conflict-title"
        className="font-heading text-lg font-bold text-navy"
      >
        {conflict.title}
      </h2>
      <p id="plan-conflict-message" className="mt-2 text-sm text-navy/80">
        {conflict.message}
      </p>
      <div className="mt-5 flex flex-wrap justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="min-h-11 rounded-lg border border-border px-5 text-sm font-semibold text-navy hover:bg-navy/5 cursor-pointer"
        >
          Batalkan
        </button>
        <button
          type="button"
          onClick={onConfirm}
          className="min-h-11 rounded-lg bg-navy px-5 text-sm font-semibold text-white hover:bg-navy-light cursor-pointer"
        >
          {conflict.confirmLabel}
        </button>
      </div>
    </ModalShell>
  )
}
