import { useCallback, useEffect, useRef, useState, type ReactNode } from "react"
import { AlertCircle } from "lucide-react"
import ModalShell from "@/shared/ui/course/ModalShell"
import { cn } from "@/shared/utils"

export interface ConfirmDialogValues {
  reason: string
}

interface ConfirmReasonField {
  required?: boolean
  label?: string
  placeholder?: string
}

interface ConfirmManualField {
  expected: string
  label: string
  placeholder?: string
}

interface ConfirmDialogProps {
  title: string
  body: ReactNode
  confirmLabel: string
  cancelLabel?: string
  reasonField?: ConfirmReasonField
  manualField?: ConfirmManualField
  busy?: boolean
  errorMessage?: string | null
  onConfirm: (values: ConfirmDialogValues) => void | Promise<void>
  onCancel: () => void
  labelledBy?: string
  icon?: ReactNode
  tone?: "navy" | "orange"
  panelClassName?: string
  overlayClassName?: string
}

const DEFAULT_PANEL_CLASS =
  "w-full max-w-md rounded-2xl border border-border bg-surface p-6 space-y-4 shadow-2xl animate-in zoom-in-95 duration-200"
const DEFAULT_OVERLAY_CLASS =
  "bg-black/60 backdrop-blur-xs animate-in fade-in duration-200"

/**
 * Dialog konfirmasi untuk aksi admin. Pembatalan tidak pernah memanggil
 * onConfirm; fokus awal ada di tombol Batal agar Enter tidak menyetujui aksi.
 */
export default function ConfirmDialog({
  title,
  body,
  confirmLabel,
  cancelLabel = "Batal",
  reasonField,
  manualField,
  busy = false,
  errorMessage = null,
  onConfirm,
  onCancel,
  labelledBy = "confirm-dialog-title",
  icon,
  tone = "navy",
  panelClassName,
  overlayClassName,
}: ConfirmDialogProps) {
  const [reason, setReason] = useState("")
  const [typedConfirmation, setTypedConfirmation] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const cancelRef = useRef<HTMLButtonElement>(null)
  const onCancelRef = useRef(onCancel)
  onCancelRef.current = onCancel

  const isBusy = busy || isSubmitting
  const isBusyRef = useRef(isBusy)
  isBusyRef.current = isBusy
  const isSubmittingRef = useRef(false)

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => cancelRef.current?.focus())
    return () => window.cancelAnimationFrame(frame)
  }, [])

  const handleClose = useCallback(() => {
    if (isBusyRef.current) return
    onCancelRef.current()
  }, [])

  const reasonReady = !reasonField?.required || reason.trim().length > 0
  const manualReady =
    !manualField ||
    (manualField.expected.trim().length > 0 &&
      typedConfirmation.trim() === manualField.expected.trim())
  const canConfirm = reasonReady && manualReady && !isBusy

  const handleConfirm = async () => {
    if (isSubmittingRef.current) return
    if (!canConfirm || isSubmitting) return
    isSubmittingRef.current = true
    setIsSubmitting(true)
    try {
      await onConfirm({ reason: reason.trim() })
    } finally {
      isSubmittingRef.current = false
      setIsSubmitting(false)
    }
  }

  return (
    <ModalShell
      onClose={handleClose}
      labelledBy={labelledBy}
      overlayClassName={cn(DEFAULT_OVERLAY_CLASS, overlayClassName)}
      panelClassName={cn(DEFAULT_PANEL_CLASS, panelClassName)}
    >
      {icon && <div className="flex justify-center">{icon}</div>}

      <div className="space-y-1">
        <h2
          id={labelledBy}
          className="font-heading font-bold text-lg text-navy"
        >
          {title}
        </h2>
        {body}
      </div>

      {reasonField && (
        <div className="space-y-1.5">
          <label
            htmlFor={`${labelledBy}-reason`}
            className="block text-xs font-semibold text-foreground"
          >
            {reasonField.label ?? "Alasan"}
            {reasonField.required ? " *" : " (opsional)"}
          </label>
          <textarea
            id={`${labelledBy}-reason`}
            rows={2}
            value={reason}
            disabled={isBusy}
            onChange={(event) => setReason(event.target.value)}
            placeholder={reasonField.placeholder}
            className="w-full min-h-11 rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted focus:border-gold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/40 disabled:opacity-70"
          />
        </div>
      )}

      {manualField && (
        <div className="space-y-1.5">
          <label
            htmlFor={`${labelledBy}-confirmation`}
            className="block text-xs font-semibold text-foreground"
          >
            {manualField.label}
          </label>
          <input
            id={`${labelledBy}-confirmation`}
            type="text"
            autoComplete="off"
            value={typedConfirmation}
            disabled={isBusy}
            onChange={(event) => setTypedConfirmation(event.target.value)}
            placeholder={manualField.placeholder}
            className="w-full min-h-11 rounded-xl border border-border bg-background px-3 font-mono text-sm text-foreground placeholder:text-muted focus:border-gold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/40 disabled:opacity-70"
          />
        </div>
      )}

      {errorMessage && (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-xl border border-orange/30 bg-white p-3 text-sm text-orange"
        >
          <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <span>{errorMessage}</span>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 pt-2">
        <button
          ref={cancelRef}
          type="button"
          onClick={handleClose}
          disabled={isBusy}
          className="min-h-11 w-full rounded-xl border border-border bg-background px-4 text-sm font-medium text-foreground transition-colors hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy focus-visible:ring-offset-2 disabled:opacity-60 cursor-pointer"
        >
          {cancelLabel}
        </button>
        <button
          type="button"
          onClick={() => void handleConfirm()}
          disabled={!canConfirm}
          aria-busy={isBusy}
          className={cn(
            "min-h-11 w-full rounded-xl px-4 text-sm font-medium text-white transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer",
            tone === "orange"
              ? "bg-orange hover:bg-orange/90"
              : "bg-navy hover:bg-navy-light",
          )}
        >
          {confirmLabel}
        </button>
      </div>
    </ModalShell>
  )
}
