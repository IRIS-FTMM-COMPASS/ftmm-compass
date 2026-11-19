import { apiFetch } from "@/shared/api/client"

export interface TimetableSelection {
  course_code: string
  section_id: string
  section_code: string
}

export interface TimetableResponse {
  academic_period_id: string | null
  selections: TimetableSelection[]
  updated_at: string | null
}

export interface TimetableSelectionInput {
  course_code: string
  section_id: string
}

const PATH = "/api/v1/me/timetable"

export const timetableService = {
  get(signal?: AbortSignal): Promise<TimetableResponse> {
    return apiFetch<TimetableResponse>(PATH, { auth: true, signal })
  },

  replace(
    selections: TimetableSelectionInput[],
    signal?: AbortSignal,
  ): Promise<TimetableResponse> {
    return apiFetch<TimetableResponse>(PATH, {
      method: "PUT",
      auth: true,
      body: { selections },
      signal,
    })
  },
}
