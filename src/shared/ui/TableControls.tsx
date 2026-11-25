import type { ReactNode } from "react"
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  ChevronsUpDown,
  Search,
  X,
} from "lucide-react"
import { cn } from "@/shared/utils"
import type { SortState } from "@/shared/hooks/useTableControls"

const PAGE_SIZE_OPTIONS = [10, 20, 50] as const

type Align = "left" | "center" | "right"

const ALIGN_TH: Record<Align, string> = {
  left: "text-left",
  center: "text-center",
  right: "text-right",
}

const ALIGN_BUTTON: Record<Align, string> = {
  left: "justify-start text-left",
  center: "justify-center text-center",
  right: "justify-end text-right",
}

export interface SortableThProps {
  label: ReactNode
  sortKey: string
  sort: SortState
  onSort: (key: string) => void
  align?: Align
  className?: string
  srLabel?: string
}

/**
 * Sel header tabel yang dapat diurutkan lewat tombol di dalamnya, sehingga
 * pengguna keyboard mendapat target fokus yang jelas dan pembaca layar
 * menerima status aria-sort.
 */
export function SortableTh({
  label,
  sortKey,
  sort,
  onSort,
  align = "left",
  className,
  srLabel,
}: SortableThProps) {
  const active = sort.key === sortKey
  const ariaSort = active
    ? sort.order === "asc"
      ? "ascending"
      : "descending"
    : "none"
  const Indicator = !active
    ? ChevronsUpDown
    : sort.order === "asc"
      ? ChevronUp
      : ChevronDown

  return (
    <th
      scope="col"
      aria-sort={ariaSort}
      className={cn(
        "px-3 py-2 text-xs font-semibold uppercase tracking-wide text-muted",
        ALIGN_TH[align],
        className,
      )}
    >
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        aria-label={srLabel}
        className={cn(
          "inline-flex min-h-11 w-full items-center gap-1.5 rounded-lg px-1 text-xs font-semibold uppercase tracking-wide text-muted transition-colors hover:text-navy focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/50 focus-visible:ring-offset-2 cursor-pointer",
          ALIGN_BUTTON[align],
        )}
      >
        <span>{label}</span>
        <Indicator
          aria-hidden
          className={cn(
            "h-3.5 w-3.5 shrink-0",
            active ? "text-navy" : "text-muted/70",
          )}
        />
      </button>
    </th>
  )
}

export interface TablePagerProps {
  page: number
  pageCount: number
  pageSize: number
  total: number
  from: number
  to: number
  onPage: (page: number) => void
  onPageSize: (pageSize: number) => void
  idPrefix: string
}

/** Kontrol paginasi: rentang baris, ukuran halaman, dan navigasi halaman. */
export function TablePager({
  page,
  pageCount,
  pageSize,
  total,
  from,
  to,
  onPage,
  onPageSize,
  idPrefix,
}: TablePagerProps) {
  const canPrev = page > 1
  const canNext = page < pageCount
  const selectId = `${idPrefix}-page-size`

  return (
    <div className="flex flex-col gap-3 border-t border-border px-3 py-3 text-sm text-muted sm:flex-row sm:items-center sm:justify-between">
      <p className="tabular-nums">
        {from}–{to} dari {total}
      </p>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <label htmlFor={selectId} className="text-xs font-medium text-muted">
            Baris per halaman
          </label>
          <select
            id={selectId}
            value={pageSize}
            onChange={(event) => onPageSize(Number(event.target.value))}
            className="h-11 rounded-lg border border-border bg-surface px-2 text-sm text-foreground focus:border-gold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/40 cursor-pointer"
          >
            {PAGE_SIZE_OPTIONS.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => onPage(page - 1)}
            disabled={!canPrev}
            aria-label="Halaman sebelumnya"
            className="inline-flex h-11 w-11 items-center justify-center rounded-lg border border-border bg-surface text-foreground transition-colors hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/50 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer"
          >
            <ChevronLeft aria-hidden className="h-4 w-4" />
          </button>
          <span className="min-w-24 text-center text-xs tabular-nums text-muted">
            Halaman {page} dari {pageCount}
          </span>
          <button
            type="button"
            onClick={() => onPage(page + 1)}
            disabled={!canNext}
            aria-label="Halaman berikutnya"
            className="inline-flex h-11 w-11 items-center justify-center rounded-lg border border-border bg-surface text-foreground transition-colors hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/50 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer"
          >
            <ChevronRight aria-hidden className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  )
}

export interface TableSearchInputProps {
  value: string
  onChange: (value: string) => void
  label: string
  placeholder?: string
  id: string
}

/** Input pencarian tabel dengan label terlihat dan tombol hapus. */
export function TableSearchInput({
  value,
  onChange,
  label,
  placeholder,
  id,
}: TableSearchInputProps) {
  return (
    <div className="w-full sm:max-w-xs">
      <label
        htmlFor={id}
        className="mb-1 block text-xs font-semibold text-foreground"
      >
        {label}
      </label>
      <div className="relative">
        <Search
          aria-hidden
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted"
        />
        <input
          id={id}
          type="search"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          className="h-11 w-full rounded-lg border border-border bg-surface pl-9 pr-10 text-sm text-foreground placeholder:text-muted focus:border-gold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/40 [&::-webkit-search-cancel-button]:hidden"
        />
        {value !== "" && (
          <button
            type="button"
            onClick={() => onChange("")}
            aria-label="Hapus pencarian"
            className="absolute right-1 top-1/2 inline-flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-md text-muted transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/50 cursor-pointer"
          >
            <X aria-hidden className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  )
}
