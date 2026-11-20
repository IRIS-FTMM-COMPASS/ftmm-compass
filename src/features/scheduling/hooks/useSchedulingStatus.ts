import { useCallback, useEffect, useState } from "react"
import { apiFetch } from "@/shared/api/client"
import type {
  BoardProgramStatus,
  BoardResponse,
} from "@/features/scheduling/schedulingService"

const IN_PROGRESS_LABEL = "Jadwal masih dalam proses"
const FINAL_LABEL = "Jadwal final"
const STATUS_CHANGED_EVENT = "scheduling-status-changed"
const STATUS_POLL_INTERVAL_MS = 5_000

function statusFromPrograms(
  programs: BoardProgramStatus[],
): {
  status: string
  isFinal: boolean
} {
  if (programs.length === 0) {
    return { status: IN_PROGRESS_LABEL, isFinal: false }
  }
  if (programs.every((program) => program.state === "final")) {
    return { status: FINAL_LABEL, isFinal: true }
  }
  const pending = programs.find((program) => program.state !== "final")
  return { status: pending?.label || IN_PROGRESS_LABEL, isFinal: false }
}

export function useSchedulingStatus() {
  const [status, setStatus] = useState(IN_PROGRESS_LABEL)
  const [isFinal, setIsFinal] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [attempt, setAttempt] = useState(0)

  const retry = useCallback(() => setAttempt((value) => value + 1), [])

  useEffect(() => {
    let mounted = true
    const controller = new AbortController()
    setIsLoading(true)
    apiFetch<BoardResponse>("/api/v1/scheduling/board", {
      auth: true,
      signal: controller.signal,
    })
      .then((response) => {
        if (!mounted) return
        const next = statusFromPrograms(response?.data?.programs ?? [])
        setStatus(next.status)
        setIsFinal(next.isFinal)
      })
      .catch(() => {
        if (!mounted) return
        setStatus(IN_PROGRESS_LABEL)
        setIsFinal(false)
      })
      .finally(() => {
        if (mounted) setIsLoading(false)
      })
    return () => {
      mounted = false
      controller.abort()
    }
  }, [attempt])

  useEffect(() => {
    window.addEventListener(STATUS_CHANGED_EVENT, retry)
    const interval = window.setInterval(retry, STATUS_POLL_INTERVAL_MS)
    return () => {
      window.removeEventListener(STATUS_CHANGED_EVENT, retry)
      window.clearInterval(interval)
    }
  }, [retry])

  return { status, isFinal, isLoading, retry }
}
