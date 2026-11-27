import { useCallback, useMemo, useState } from "react"

export type SortOrder = "asc" | "desc"

export interface SortState {
  key: string
  order: SortOrder
}

export interface TableControls<T> {
  search: string
  setSearch(v: string): void
  sort: SortState
  toggleSort(key: string): void
  page: number
  setPage(n: number): void
  pageSize: number
  setPageSize(n: number): void
  pageCount: number
  pageItems: T[]
  total: number
  from: number
  to: number
}

export interface TableControlsOptions<T> {
  searchFields: (item: T) => string[]
  sorters: Record<string, (item: T) => string | number | null | undefined>
  initialSort: SortState
  pageSize?: number
}

const DEFAULT_PAGE_SIZE = 10
const collator = new Intl.Collator("id", {
  numeric: true,
  sensitivity: "base",
})

function compareValues(a: string | number, b: string | number): number {
  if (typeof a === "number" && typeof b === "number") return a - b
  return collator.compare(String(a), String(b))
}

/**
 * Menyimpan state pencarian, pengurutan, dan paginasi untuk satu tabel.
 * Nilai kosong selalu diletakkan di akhir tanpa memandang arah urutan, dan
 * halaman yang sedang tampil dijepit ke rentang yang tersedia sehingga data
 * yang menyusut tidak menyisakan halaman kosong.
 */
export function useTableControls<T>(
  items: T[],
  {
    searchFields,
    sorters,
    initialSort,
    pageSize: initialPageSize = DEFAULT_PAGE_SIZE,
  }: TableControlsOptions<T>,
): TableControls<T> {
  const [search, setSearchState] = useState("")
  const [sort, setSort] = useState<SortState>(initialSort)
  const [page, setPageState] = useState(1)
  const [pageSize, setPageSizeState] = useState(initialPageSize)

  const normalizedQuery = search.trim().toLowerCase()

  const filtered = useMemo(() => {
    if (!normalizedQuery) return items
    return items.filter((item) =>
      searchFields(item).some((field) =>
        field.toLowerCase().includes(normalizedQuery),
      ),
    )
  }, [items, normalizedQuery, searchFields])

  const sorted = useMemo(() => {
    const sorter = sorters[sort.key]
    if (!sorter) return filtered

    const decorated = filtered.map((item, index) => ({
      item,
      index,
      value: sorter(item),
    }))

    decorated.sort((a, b) => {
      if (a.value == null || b.value == null) {
        if (a.value == null && b.value == null) return a.index - b.index
        return a.value == null ? 1 : -1
      }
      const order = compareValues(a.value, b.value)
      if (order !== 0) return sort.order === "asc" ? order : -order
      return a.index - b.index
    })

    return decorated.map((entry) => entry.item)
  }, [filtered, sort, sorters])

  const total = sorted.length
  const pageCount = Math.max(1, Math.ceil(total / pageSize))
  const currentPage = Math.min(Math.max(page, 1), pageCount)

  const pageItems = useMemo(() => {
    const start = (currentPage - 1) * pageSize
    return sorted.slice(start, start + pageSize)
  }, [sorted, currentPage, pageSize])

  const setSearch = useCallback((value: string) => {
    setSearchState(value)
    setPageState(1)
  }, [])

  const toggleSort = useCallback((key: string) => {
    setSort((prev) =>
      prev.key === key
        ? { key, order: prev.order === "asc" ? "desc" : "asc" }
        : { key, order: "asc" },
    )
    setPageState(1)
  }, [])

  const setPage = useCallback((next: number) => {
    setPageState(Math.max(1, next))
  }, [])

  const setPageSize = useCallback((next: number) => {
    setPageSizeState(next)
    setPageState(1)
  }, [])

  return {
    search,
    setSearch,
    sort,
    toggleSort,
    page: currentPage,
    setPage,
    pageSize,
    setPageSize,
    pageCount,
    pageItems,
    total,
    from: total === 0 ? 0 : (currentPage - 1) * pageSize + 1,
    to: total === 0 ? 0 : Math.min(currentPage * pageSize, total),
  }
}
