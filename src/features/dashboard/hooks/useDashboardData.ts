import { useEffect, useMemo, useState } from "react"
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

  useEffect(() => {
    let mounted = true
    setIsLoading(true)
    dashboardService
      .getDashboardMe()
      .then((data) => {
        if (mounted) setDashboardData(data)
      })
      .catch(() => {})
      .finally(() => {
        if (mounted) setIsLoading(false)
      })
    return () => {
      mounted = false
    }
  }, [user])

  const displayedSchedule = useMemo<ScheduleItem[]>(() => {
    if (user?.role === "admin") return []
    if (schedule.length > 0) return schedule
    return (dashboardData?.schedule ?? [])
      .map(toScheduleItem)
      .filter((item): item is ScheduleItem => item !== null)
  }, [user?.role, dashboardData, schedule])

  const hasConflict = displayedSchedule.some((item) => item.conflict)

  return { dashboardData, isLoading, displayedSchedule, hasConflict }
}
