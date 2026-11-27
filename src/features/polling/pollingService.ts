import { apiFetch } from "@/shared/api/client"
import { readUser } from "@/shared/api/session"

export interface PollingPeriod {
  period_id: string
  academic_year: string
  term: "ganjil" | "genap"
  target_semester_type: "ganjil" | "genap"
  start_date: string
  end_date: string
  is_active: boolean
  min_quorum: number
  max_votes_per_student: number
  description?: string
}

export interface StudentVote {
  vote_id: string
  course_id: string
  course_code?: string
  course_name?: string
  priority: 1 | 2 | 3
  created_at: string
}

export interface SubmitVotePayload {
  course_id: string
  priority: 1 | 2 | 3
}

export interface CourseDemandItem {
  course_id: string
  course_code: string
  course_name: string
  study_program: string
  program_code?: string
  credits: number
  total_votes: number
  priority_1_votes: number
  priority_2_votes: number
  priority_3_votes: number
  min_quorum: number
  status: "QUALIFIED" | "BORDERLINE" | "UNQUALIFIED"
  projected_classes: number
}

export interface DemandAnalyticsResponse {
  period: PollingPeriod
  total_students_voted: number
  items: CourseDemandItem[]
}

export const ADMIN_ROLES = ["admin", "lecturer"]

export interface PjAvailabilityItem {
  curriculum_course_id: string
  course_id: string
  course_code: string
  course_name: string
  credits: number
  semester: number | null
  type: string
  course_scope: string
  is_active: boolean
  can_toggle: boolean
  lock_reason: string | null
  class_count?: number
  capacity_per_class?: number
  total_quota?: number
  enrolled_count?: number
}

export interface PjAvailabilityMeta {
  period_id: string
  target_semester: number
  study_program: string
  total: number
}

export interface PjAvailabilityResponse {
  data: PjAvailabilityItem[]
  meta: PjAvailabilityMeta
}

export interface PjAvailabilityParams {
  periodId?: string
  semester?: number
}

export interface CourseQuotaResponse {
  curriculum_course_id: string
  study_program_id: string
  academic_period_id: string
  class_count: number
  capacity_per_class: number
  total_quota: number
  enrolled_count: number
  created: boolean
}

export const pollingService = {
  getActivePeriod(): Promise<PollingPeriod> {
    return apiFetch<PollingPeriod>("/api/v1/polling/periods/active", {
      auth: true,
    })
  },

  getMyVotes(): Promise<StudentVote[]> {
    return apiFetch<StudentVote[]>("/api/v1/polling/my-votes", { auth: true })
  },

  submitVote(payload: SubmitVotePayload): Promise<StudentVote> {
    return apiFetch<StudentVote>("/api/v1/polling/votes", {
      method: "POST",
      body: payload,
      auth: true,
    })
  },

  removeVote(courseId: string): Promise<void> {
    return apiFetch<void>(
      `/api/v1/polling/votes/${encodeURIComponent(courseId)}`,
      { method: "DELETE", auth: true },
    )
  },

  getDemandAnalytics(studyProgram?: string): Promise<DemandAnalyticsResponse> {
    const query =
      studyProgram && studyProgram !== "all"
        ? `?study_program=${encodeURIComponent(studyProgram)}`
        : ""
    const role = readUser<{ role: string }>()?.role ?? "student"
    const base = ADMIN_ROLES.includes(role)
      ? "/api/v1/admin/polling/demand-analytics"
      : "/api/v1/polling/demand-analytics"
    return apiFetch<DemandAnalyticsResponse>(`${base}${query}`, { auth: true })
  },
}

export const pjService = {
  getAvailability(
    params: PjAvailabilityParams = {},
  ): Promise<PjAvailabilityResponse> {
    const query: string[] = []
    if (params.periodId) {
      query.push(`period_id=${encodeURIComponent(params.periodId)}`)
    }
    if (params.semester !== undefined) {
      query.push(`semester=${encodeURIComponent(String(params.semester))}`)
    }
    const suffix = query.length > 0 ? `?${query.join("&")}` : ""
    return apiFetch<PjAvailabilityResponse>(
      `/api/v1/pj/course-availability${suffix}`,
      { auth: true },
    )
  },

  setAvailability(
    curriculumCourseId: string,
    isActive: boolean,
    reason?: string,
  ): Promise<PjAvailabilityItem> {
    return apiFetch<PjAvailabilityItem>(
      `/api/v1/pj/course-availability/${encodeURIComponent(curriculumCourseId)}`,
      {
        method: "PATCH",
        body: {
          is_active: isActive,
          ...(reason ? { reason } : {}),
        },
        auth: true,
      },
    )
  },

  setQuota(
    curriculumCourseId: string,
    payload: {
      academic_period_id?: string
      class_count: number
      capacity_per_class: number
      reason?: string
    },
  ): Promise<CourseQuotaResponse> {
    return apiFetch<CourseQuotaResponse>(
      `/api/v1/pj/course-availability/${encodeURIComponent(curriculumCourseId)}/quota`,
      {
        method: "PUT",
        body: payload,
        auth: true,
      },
    )
  },
}
