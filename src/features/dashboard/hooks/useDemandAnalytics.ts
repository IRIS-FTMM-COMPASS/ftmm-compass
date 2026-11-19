import { useCallback, useEffect, useMemo, useState } from "react"
import type { AuthUser } from "@/features/auth/authService"
import { usePolling } from "@/features/polling/polling"
import {
  PROGRAM_ABBREVIATIONS,
  normalizeProgramName,
} from "@/shared/domain/course"

const PROGRAM_NAMES_BY_CODE: Record<string, string> = Object.fromEntries(
  Object.entries(PROGRAM_ABBREVIATIONS).map(([name, code]) => [
    code.toLowerCase(),
    name,
  ]),
)

function coordinatorProdi(unitName?: string): string {
  const raw = unitName?.trim()
  if (!raw) return ""

  const normalized = normalizeProgramName(raw)
  const byCode = PROGRAM_NAMES_BY_CODE[normalized.toLowerCase()]
  if (byCode) return byCode
  if (PROGRAM_ABBREVIATIONS[normalized]) return normalized

  const byName = Object.keys(PROGRAM_ABBREVIATIONS).find((name) =>
    normalized.toLowerCase().includes(name.toLowerCase()),
  )
  return byName ?? normalized
}

export function useDemandAnalytics(user: AuthUser | null) {
  const { demand, loadDemand, isLoading } = usePolling()
  const [chosenProdi, setChosenProdi] = useState<string>("all")
  const isProgramCoordinator =
    user?.role === "lecturer" && Boolean(user.is_program_coordinator)
  const lockedProdi = isProgramCoordinator
    ? coordinatorProdi(user?.unit_name)
    : null
  const selectedProdi = lockedProdi ?? chosenProdi

  const setSelectedProdi = useCallback(
    (value: string) => {
      if (isProgramCoordinator) return
      setChosenProdi(value)
    },
    [isProgramCoordinator],
  )

  useEffect(() => {
    if (!user || user.role === "student" || !selectedProdi) return
    if (demand[selectedProdi]) return
    void loadDemand(selectedProdi)
  }, [demand, loadDemand, selectedProdi, user])

  const demandAnalytics = demand[selectedProdi]
  const items = useMemo(() => demandAnalytics?.items || [], [demandAnalytics])

  const handleExportCSV = () => {
    if (!items.length) return
    const headers = [
      "Kode MK",
      "Nama Mata Kuliah",
      "Program Studi",
      "SKS",
      "Total Peminat",
      "Prioritas 1",
      "Prioritas 2",
      "Prioritas 3",
      "Min Quorum",
      "Status",
      "Proyeksi Kelas",
    ]

    const rows = items.map((it) => [
      `"${it.course_code}"`,
      `"${it.course_name.replace(/"/g, '""')}"`,
      `"${it.study_program}"`,
      it.credits,
      it.total_votes,
      it.priority_1_votes,
      it.priority_2_votes,
      it.priority_3_votes,
      it.min_quorum,
      it.status,
      it.projected_classes,
    ])

    const csvContent =
      "data:text/csv;charset=utf-8," +
      [headers.join(","), ...rows.map((e) => e.join(","))].join("\n")

    const encodedUri = encodeURI(csvContent)
    const link = document.createElement("a")
    link.setAttribute("href", encodedUri)
    link.setAttribute(
      "download",
      `rekap_peminatan_mk_pilihan_${selectedProdi}_${new Date().toISOString().slice(0, 10)}.csv`,
    )
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  return {
    selectedProdi,
    setSelectedProdi,
    demandAnalytics,
    items,
    isLoadingAnalytics: isLoading,
    handleExportCSV,
  }
}
