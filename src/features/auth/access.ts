import type { AuthUser } from "@/features/auth/authService"

const STUDENT_ONLY_PAGES: Record<string, true> = {
  "degree-planner": true,
  chatbot: true,
}

const ADMIN_ONLY_PAGES: Record<string, true> = {
  "admin-accounts": true,
}

const LECTURER_ONLY_PAGES: Record<string, true> = {
  "pj-courses": true,
  preferences: true,
}

const SCHEDULING_PAGES: Record<string, true> = {
  scheduling: true,
}

const SCHEDULE_MANAGE_PAGES: Record<string, true> = {
  "teaching-team": true,
  "class-assignment": true,
}

export function canManageSchedule(user: AuthUser | null): boolean {
  return (
    user?.role === "admin" ||
    (user?.role === "lecturer" && user.is_program_coordinator === true)
  )
}

export function canAccessPage(user: AuthUser | null, page: string): boolean {
  const role = user?.role ?? "student"
  if (ADMIN_ONLY_PAGES[page]) return role === "admin"
  if (STUDENT_ONLY_PAGES[page]) return role === "student"
  if (LECTURER_ONLY_PAGES[page]) return role === "lecturer"
  if (SCHEDULING_PAGES[page]) return role === "admin" || role === "lecturer"
  if (SCHEDULE_MANAGE_PAGES[page]) {
    return (
      role === "admin" ||
      (role === "lecturer" && user?.is_program_coordinator === true)
    )
  }
  return true
}
