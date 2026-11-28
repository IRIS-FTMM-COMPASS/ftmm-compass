import { useEffect, useRef, type ReactNode } from "react"
import { cn } from "@/shared/utils"

interface ModalShellProps {
  onClose: () => void
  labelledBy: string
  children: ReactNode
  panelClassName?: string
  overlayClassName?: string
}

/**
 * Satu perilaku dialog: Esc menutup, klik backdrop menutup, dan fokus kembali ke
 * elemen pemicu saat dialog ditutup.
 */
export default function ModalShell({
  onClose,
  labelledBy,
  children,
  panelClassName,
  overlayClassName,
}: ModalShellProps) {
  const panelRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    triggerRef.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose()
        return
      }
      if (event.key !== "Tab" || !panelRef.current) return
      const focusable = Array.from(
        panelRef.current.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ),
      ).filter((element) => element.getClientRects().length > 0)
      if (focusable.length === 0) {
        event.preventDefault()
        panelRef.current.focus()
        return
      }
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      const active = document.activeElement
      if (
        event.shiftKey &&
        (active === first ||
          active === panelRef.current ||
          !panelRef.current.contains(active))
      ) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && active === last) {
        event.preventDefault()
        first.focus()
      }
    }
    window.addEventListener("keydown", handleKeyDown)
    panelRef.current?.focus()
    return () => {
      window.removeEventListener("keydown", handleKeyDown)
      triggerRef.current?.focus()
    }
  }, [onClose])

  return (
    <div
      className={cn(
        "fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs animate-in fade-in duration-150",
        overlayClassName,
      )}
      onClick={onClose}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        tabIndex={-1}
        className={cn("outline-hidden", panelClassName)}
        onClick={(event) => event.stopPropagation()}
      >
        {children}
      </div>
    </div>
  )
}
