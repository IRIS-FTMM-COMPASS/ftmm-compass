import { useCallback, useEffect, useState, type ReactNode } from "react"
import ConfirmDialog from "@/shared/ui/ConfirmDialog"

export interface DiscardGuardOptions {
  dirty: boolean
  onClose: () => void
}

export interface DiscardGuard {
  requestClose: () => void
  discardDialog: ReactNode
}

/**
 * Menjaga penutupan panel yang masih menyimpan perubahan belum tersimpan.
 * Saat tidak ada perubahan, onClose langsung dipanggil tanpa dialog.
 */
export function useDiscardGuard({
  dirty,
  onClose,
}: DiscardGuardOptions): DiscardGuard {
  const [confirmOpen, setConfirmOpen] = useState(false)

  useEffect(() => {
    if (!dirty) setConfirmOpen(false)
  }, [dirty])

  const requestClose = useCallback(() => {
    if (!dirty) {
      onClose()
      return
    }
    setConfirmOpen(true)
  }, [dirty, onClose])

  const discardDialog =
    dirty && confirmOpen ? (
      <ConfirmDialog
        title="Buang perubahan?"
        body={
          <p className="text-sm text-muted">
            Perubahan yang belum disimpan akan hilang.
          </p>
        }
        confirmLabel="Buang"
        cancelLabel="Lanjut mengedit"
        tone="orange"
        onConfirm={() => {
          setConfirmOpen(false)
          onClose()
        }}
        onCancel={() => setConfirmOpen(false)}
      />
    ) : null

  return { requestClose, discardDialog }
}
