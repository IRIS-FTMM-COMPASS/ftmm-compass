import { useCallback, useEffect, useMemo, useState } from "react"
import { apiErrorMessage } from "@/shared/api/client"
import type { AuthUser } from "@/features/auth/authService"
import {
  dashboardService,
  type DashboardMeResponse,
  type DashboardScheduleItem,
} from "@/features/dashboard/dashboardService"
import { usePlanner } from "@/features/degree-planner/state/planner"
import type { ScheduleItem } from "@/shared/domain/models"

function toScheduleItem(item: DashboardScheduleItem): ScheduleItem | null {
  const [startHour, startMinute] = item.start_time.split(":").map(Number)
  const [endHour, endMinute] = item.end_time.split(":").map(Number)
  if (![startHour, startMinute, endHour, endMinute].every(Number.isFinite)) {
    return null
  }
  const start = startHour + startMinute / 60
  const end = endHour + endMinute / 60
  if (end <= start) return null
  return {
    id: item.id,
    course: item.course_name,
    code: item.course_code,
    day: item.day,
    start,
    duration: end - start,
    color: item.color || "teal",
    room: item.room,
    sectionCode: item.class_name,
    lecturer: item.lecturer,
  }
}

export function useDashboardData(user: AuthUser | null) {
  const { schedule } = usePlanner()
  const [dashboardData, setDashboardData] =
    useState<DashboardMeResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  const retry = useCallback(() => setAttempt((value) => value + 1), [])

  useEffect(() => {
    let mounted = true
    setIsLoading(true)
    setError(null)
    dashboardService
      .getDashboardMe()
      .then((data) => {
        if (mounted) setDashboardData(data)
      })
      .catch((cause: unknown) => {
        if (mounted) {
          setDashboardData(null)
          setError(
            apiErrorMessage(cause, "Gagal memuat data dashboard. Coba lagi."),
          )
        }
      })
      .finally(() => {
        if (mounted) setIsLoading(false)
      })
    return () => {
      mounted = false
    }
  }, [user, attempt])

  const displayedSchedule = useMemo<ScheduleItem[]>(() => {
    if (user?.role === "admin") return []
    const apiSchedule = (dashboardData?.schedule ?? [])
      .map(toScheduleItem)
      .filter((item): item is ScheduleItem => item !== null)
    if (apiSchedule.length > 0) return apiSchedule
    return schedule
  }, [user?.role, dashboardData, schedule])

  const hasConflict = displayedSchedule.some((item) => item.conflict)

  return {
    dashboardData,
    isLoading,
    displayedSchedule,
    hasConflict,
    error,
    retry,
  }
}
