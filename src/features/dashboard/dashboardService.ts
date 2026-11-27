import { apiFetch } from "@/shared/api/client"

export interface StudentDashboardStats {
  type: "student"
  sks_completed: number
  sks_target: number
  completion_percentage: number
  current_semester: number
  courses_planned: number
  sks_planned: number
  gpa: number
  predicate: string
}

export interface LecturerDashboardStats {
  type: "lecturer"
  assigned_classes: number
  scheduled_classes: number
  unscheduled_classes: number
}

export interface AdminDashboardStats {
  type: "admin"
  total_active_students: number
  total_lecturers: number
  total_courses: number
  total_study_programs: number
  system_status: string
}

export type DashboardStats = StudentDashboardStats | LecturerDashboardStats | AdminDashboardStats

export interface DashboardScheduleItem {
  id: string
  class_section_id: string
  assignment_id: string
  course_id: string
  course_code: string
  course_name: string
  credits: number
  study_program_ids: string[]
  study_program_codes: string[]
  study_program_names: string[]
  schedule_state: "draft" | "final"
  day: string
  day_of_week: number
  start_time: string
  end_time: string
  time: string
  room: string
  lecturer?: string | null
  class_name?: string | null
  color?: string | null
}

export interface DashboardAssignedClass {
  assignment_id: string
  class_section_id: string
  course_id: string
  course_code: string
  course_name: string
  class_name: string
  credits: number
  study_program_ids: string[]
  study_program_codes: string[]
  study_program_names: string[]
  schedule_state: "draft" | "final"
  schedules: DashboardScheduleItem[]
}

export interface LecturerPreferenceStatus {
  academic_period_id: string | null
  status: "empty" | "filled"
  preferred_count: number
  unavailable_count: number
  deadline: string | null
  deadline_scope: "program" | "global" | null
}

export interface DashboardMeResponse {
  user_id: string
  full_name: string
  role: string
  email: string
  student_number?: string | null
  study_program?: string | null
  schedule_status?: string
  stats: DashboardStats
  schedule: DashboardScheduleItem[]
  academic_period_id?: string | null
  today?: string | null
  today_schedule?: DashboardScheduleItem[]
  assigned_classes?: DashboardAssignedClass[]
  unscheduled_classes?: DashboardAssignedClass[]
  preference?: LecturerPreferenceStatus | null
}

export const dashboardService = {
  async getDashboardMe(): Promise<DashboardMeResponse> {
    return apiFetch<DashboardMeResponse>("/api/v1/dashboard/me", { auth: true })
  },
}
