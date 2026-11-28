import { useRef, type KeyboardEvent as ReactKeyboardEvent } from "react"
import { RefreshCw } from "lucide-react"
import { cn } from "@/shared/utils"

export const SCHEDULING_TABS = [
  { id: "board", label: "Papan Jadwal" },
  { id: "rooms", label: "Ruangan" },
  { id: "deadlines", label: "Deadline Preferensi" },
] as const

export type SchedulingTabId = typeof SCHEDULING_TABS[number]["id"]

interface SchedulingPageHeaderProps {
  periodLabel?: string
  scopeLabel: string
  canOperateSchedule: boolean
  statusLabel: string
  isCurrentScopeFinal: boolean
  isAdmin: boolean
  isPjProdi: boolean
  activeTab: SchedulingTabId
  onSelectTab: (tab: SchedulingTabId) => void
  onReload: () => void
}

export default function SchedulingPageHeader({
  periodLabel,
  scopeLabel,
  canOperateSchedule,
  statusLabel,
  isCurrentScopeFinal,
  isAdmin,
  isPjProdi,
  activeTab,
  onSelectTab,
  onReload,
}: SchedulingPageHeaderProps) {
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([])
  const visibleTabs = SCHEDULING_TABS.filter((tab) => {
    if (!canOperateSchedule) return tab.id === "board"
    if (tab.id === "rooms") return isAdmin
    if (tab.id === "deadlines") return isAdmin || isPjProdi
    return true
  })

  const handleKeyDown = (
    event: ReactKeyboardEvent<HTMLButtonElement>,
    index: number,
  ) => {
    let nextIndex: number | null = null
    if (event.key === "ArrowRight") nextIndex = (index + 1) % visibleTabs.length
    if (event.key === "ArrowLeft")
      nextIndex = (index - 1 + visibleTabs.length) % visibleTabs.length
    if (event.key === "Home") nextIndex = 0
    if (event.key === "End") nextIndex = visibleTabs.length - 1
    if (nextIndex === null) return
    event.preventDefault()
    const nextTab = visibleTabs[nextIndex]
    onSelectTab(nextTab.id)
    tabRefs.current[nextIndex]?.focus()
  }

  return (
    <>
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-1">
          <p className="font-mono text-[10px] font-semibold uppercase tracking-widest text-gold">
            Penjadwalan kelas lintas prodi
          </p>
          <h2 className="font-heading text-xl font-bold text-navy md:text-2xl">
            Penjadwalan
          </h2>
          <p className="text-xs text-muted">
            {periodLabel || "Periode akademik aktif"},{" "}
            {canOperateSchedule
              ? `cakupan ${scopeLabel.toLowerCase()}`
              : "tampilan jadwal hanya-baca"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span
            role="status"
            aria-live="polite"
            className={cn(
              "inline-flex items-center rounded-full border px-3 py-1.5 text-xs font-semibold",
              isCurrentScopeFinal
                ? "border-navy/25 bg-navy/10 text-navy"
                : "border-gold/40 bg-gold/15 text-navy",
            )}
          >
            {statusLabel}
          </span>
          <button
            type="button"
            onClick={onReload}
            className="inline-flex min-h-11 items-center gap-1.5 rounded-lg border border-border bg-surface px-3 text-xs font-semibold text-navy transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold cursor-pointer"
          >
            <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
            Muat ulang
          </button>
        </div>
      </header>

      <div
        role="tablist"
        aria-label="Bagian penjadwalan"
        className="flex flex-wrap gap-2 border-b border-border"
      >
        {visibleTabs.map((tab, index) => (
          <button
            key={tab.id}
            ref={(element) => {
              tabRefs.current[index] = element
            }}
            type="button"
            role="tab"
            id={`scheduling-tab-${tab.id}`}
            aria-selected={activeTab === tab.id}
            aria-controls={`scheduling-panel-${tab.id}`}
            tabIndex={activeTab === tab.id ? 0 : -1}
            onClick={() => onSelectTab(tab.id)}
            onKeyDown={(event) => handleKeyDown(event, index)}
            className={cn(
              "min-h-11 rounded-t-lg border-b-2 px-3 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring cursor-pointer",
              activeTab === tab.id
                ? "border-navy text-navy"
                : "border-transparent text-muted hover:text-navy",
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>
    </>
  )
}
