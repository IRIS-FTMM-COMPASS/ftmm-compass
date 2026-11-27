import { apiFetch } from "@/shared/api/client"

const SCHEDULING_BASE = "/api/v1/scheduling"

export interface RoomResponse {
  room_id: string
  room_code: string
  building: string
  floor: string | null
  capacity: number
  owner_study_program_id: string | null
  is_active: boolean
}

export interface RoomCreateRequest {
  room_code: string
  building: string
  floor?: string | null
  capacity: number
  owner_study_program_id?: string | null
  is_active?: boolean
}

export interface RoomUpdateRequest {
  room_code?: string | null
  building?: string | null
  floor?: string | null
  capacity?: number | null
  owner_study_program_id?: string | null
  is_active?: boolean | null
}

export interface RoomListResponse {
  data: RoomResponse[]
  meta: Record<string, unknown>
}

export interface InstructorReferenceResponse {
  reference_id: string
  instructor_name: string
  instructor_role: string
  course_code?: string | null
  course_name?: string | null
  curriculum_course_id?: string | null
  study_program_id?: string | null
  study_program_code?: string | null
  study_program_name?: string | null
  user_id?: string | null
  is_mapped: boolean
  lecturer_name?: string | null
  academic_period_id: string
  position: number | null
  can_auto_assign: boolean
  eligibility_reason: "eligible" | "external" | "inactive_account" | "not_lecturer"
  source_reference_id: string | null
}

export interface PreferenceSlot {
  preference_id?: string
  day_of_week: number
  day_name?: string
  start_time: string
  end_time: string
  kind: "preferred" | "unavailable"
}

export interface PreferenceWarning {
  code?: string
  message?: string
  class_section_id?: string
  course_code?: string
  day_of_week?: number
  start_time?: string
  end_time?: string
  course_name?: string
  section_code?: string
  day_name?: string
  unavailable_start_time?: string
  unavailable_end_time?: string
  class_start_time?: string
  class_end_time?: string
  overlap_start_time?: string
  overlap_end_time?: string
}

export interface PreferenceResponse {
  data?: PreferenceSlot[]
  slots?: PreferenceSlot[]
  user_id: string
  meta: {
    count: number
    status: "empty" | "filled"
    preferred_count: number
    unavailable_count: number
    completeness: {
      filled: boolean
      preferred_count: number
      unavailable_count: number
    }
    deadline: string | null
    warnings: Array<string | PreferenceWarning>
    locked?: boolean
    is_read_only?: boolean
    read_only?: boolean
  }
}

export interface SchedulePeriodSettings {
  academic_period_id: string
  study_program_id: string | null
  study_program_code?: string | null
  study_program_name?: string | null
  preference_deadline: string | null
  input_revision: number
  finalized_at: string | null
  updated_at?: string | null
}

export interface PeriodSettingsRequest {
  academic_period_id: string
  study_program_id?: string | null
  preference_deadline?: string | null
}

export interface PeriodSettingsParams {
  academic_period_id: string
  study_program_id?: string
}

export interface PreferenceSummaryItem {
  user_id: string
  full_name: string
  study_program_id: string
  study_program_code: string
  study_program_name: string
  status: "empty" | "filled"
  preferred_count: number
  unavailable_count: number
  deadline: string | null
}

export interface PreferenceSummaryResponse {
  data: PreferenceSummaryItem[]
  meta: Record<string, number>
}

export interface SchedulingProgramIdentity {
  study_program_id: string
  study_program_code: string
  study_program_name: string
}

export interface BoardClassProgram extends SchedulingProgramIdentity {
  state: string
  label: string
}

export interface AssignmentLecturer {
  user_id: string
  lecturer_name: string
  position: number
  is_pjmk: boolean
  curriculum_course_id?: string | null
}

export interface ClassInstructorAssignment {
  assignment_id: string
  class_section_id: string
  academic_period_id: string
  curriculum_course_id: string | null
  user_id: string
  lecturer_name: string
  source: "auto" | "manual"
  is_pinned: boolean
  is_active: boolean
  assigned_by: string
  assigned_at: string
}

export interface AssignmentPreviewClass {
  class_section_id: string
  section_code: string
  curriculum_course_id: string
  can_edit: boolean
  context_required: boolean
  candidate: AssignmentLecturer | null
  existing_assignment: ClassInstructorAssignment | null
}

export interface AssignmentPreviewGroup {
  curriculum_course_id: string
  study_program_id: string
  study_program_code?: string | null
  study_program_name?: string | null
  programs: SchedulingProgramIdentity[]
  course_code: string
  course_name: string
  can_edit: boolean
  pool: AssignmentLecturer[]
  classes: AssignmentPreviewClass[]
}

export interface AssignmentPreviewResponse {
  data: AssignmentPreviewGroup[]
  meta: {
    academic_period_id: string
    input_revision: number
    [key: string]: unknown
  }
}

export interface AssignmentDecision {
  class_section_id: string
  curriculum_course_id?: string | null
  user_id: string
  source: "auto" | "manual"
  is_pinned: boolean
}

export interface AssignmentUpsertRequest {
  decisions: AssignmentDecision[]
}

export interface AssignmentUpsertResponse {
  data: ClassInstructorAssignment[]
  meta?: Record<string, unknown>
}

export interface PreferencePeriod {
  academic_period_id: string
  academic_year_start: number
  semester_number: number | null
  term?: string | null
  label: string
  is_active: boolean
  is_current: boolean
}

export interface PreferencePeriodListResponse {
  data: PreferencePeriod[]
  meta: { current_academic_period_id: string | null }
}

export interface InstructorPeriod {
  academic_period_id: string
  academic_year_start: number
  semester_number: number
  term: string | null
  is_active: boolean
}

export interface InstructorPeriodListResponse {
  data: InstructorPeriod[]
  meta: { total: number }
}

export interface PreferenceCopyRequest {
  from_academic_period_id: string
  academic_period_id: string
  overwrite?: boolean
}

export interface PreferenceReplaceRequest {
  academic_period_id: string
  slots: Array<Omit<PreferenceSlot, "preference_id">>
}

export interface InstructorCopyRequest {
  from_academic_period_id: string
  academic_period_id: string
}

export interface InstructorCopyMeta {
  copied: number
  skipped: number
  total: number
}

export interface InstructorCopyResponse {
  data: InstructorReferenceResponse[]
  meta: InstructorCopyMeta
}

export interface InstructorOrderRequest {
  curriculum_course_id: string
  academic_period_id: string
  ordered_reference_ids: string[]
}

export interface InstructorOrderResponse {
  data: InstructorReferenceResponse[]
  meta: { total: number }
}

export type InstructorReferenceRole = "pjmk" | "teaching_team" | "lecturer" | "other"

export interface InstructorReferenceListParams {
  role?: InstructorReferenceRole
  academic_period_id: string
}

export interface InstructorReferenceCreateRequest {
  curriculum_course_id: string
  instructor_name: string
  instructor_role: InstructorReferenceRole
  academic_period_id: string
  user_id?: string | null
  position?: number
}

export interface InstructorReferenceUpdateRequest {
  instructor_name?: string
  user_id?: string | null
  academic_period_id: string
  position?: number
}

export interface CurriculumCourseOption {
  curriculum_course_id: string
  course_id: string
  study_program_id: string
  course_code: string
  course_name: string
}

export interface InstructorReferenceListResponse {
  data: InstructorReferenceResponse[]
  meta: Record<string, unknown>
}

export interface InstructorCandidateItem {
  user_id: string
  full_name: string
  email: string
  employee_number?: string | null
  study_program_id?: string | null
  study_program_code?: string | null
  is_active: boolean
}

export interface InstructorCandidateListResponse {
  data: InstructorCandidateItem[]
  meta: Record<string, unknown>
}

export interface EligibleCurriculumContext extends SchedulingProgramIdentity {
  curriculum_course_id: string
  curriculum_id: string
  course_code: string
  course_name: string
  pjmk_reference_id: string | null
}

export interface UnassignedItem {
  class_section_id: string
  course_id: string
  course_code: string
  course_name: string
  section_code: string
  reason: string
  reason_code: string
  programs: SchedulingProgramIdentity[]
  eligible_curriculum_contexts: EligibleCurriculumContext[]
  action: string
  pjmk_reference_id: string | null
}

export interface BoardClassItem {
  class_section_id: string
  section_code: string
  course_code: string
  course_name: string
  credits: number
  face_to_face_minutes: number
  course_id: string
  study_program_id: string
  study_program_code: string
  study_program_name: string
  programs: BoardClassProgram[]
  program_ids?: string[]
  day_of_week: number
  start_hour: number
  end_hour: number
  room_id: string | null
  room_code: string | null
  lecturers: string[]
  assigned_lecturer_id: string | null
  assigned_lecturer_name: string | null
  assigned_curriculum_course_id: string | null
  is_manually_edited: boolean
  state: string
  can_edit: boolean
  read_only: boolean
  is_stale: boolean
  run_id: string | null
  input_revision: number
}

export interface BoardMeta {
  input_revision: number
  stale_count: number
  [key: string]: unknown
}

export interface BoardConflictItem {
  class_section_a_id: string
  class_section_b_id: string
  kind: "lecturer" | "room"
  object_id: string | null
  object_name: string
  object_label: string
  class_section_a_label: string
  class_section_b_label: string
  day_name: string
  label: string
  day_of_week: number
  start_hour: number
  end_hour: number
}

export interface BoardProgramStatus {
  study_program_id: string
  study_program_code: string
  study_program_name?: string | null
  state: string
  label: string
  finalized_at: string | null
  is_stale: boolean
  run_id: string | null
  input_revision: number
}

export interface BoardData {
  academic_period_id: string
  period_label: string
  classes: BoardClassItem[]
  conflicts: BoardConflictItem[]
  programs: BoardProgramStatus[]
  unassigned: UnassignedItem[]
}

export interface BoardResponse {
  data: BoardData
  meta: BoardMeta
}

export interface GenerateRequest {
  academic_period_id?: string | null
  mode: "regenerate" | "full_reset"
  confirm_full_reset?: boolean
  study_program_id?: string
}

export interface GenerateResponse {
  run_id: string
  assigned: number
  unassigned: UnassignedItem[]
  conflicts: BoardConflictItem[]
  mode: "regenerate" | "full_reset"
  assigned_count: number
  unassigned_count: number
  conflict_count: number
  input_revision: number
  study_program_id: string | null
  regenerated_count: number
  preserved_final_count: number
  preserved_manual_count: number
}

export interface ClassMoveRequest {
  day_of_week: number
  start_hour: number
  room_id: string
  reason: string
}

export interface ClassMoveResponse {
  class: BoardClassItem
  conflicts: BoardConflictItem[]
}

export interface ConflictListResponse {
  data: BoardConflictItem[]
  meta: Record<string, unknown>
}

export interface UnassignedListResponse {
  data: UnassignedItem[]
  meta: Record<string, unknown>
}

export interface FinalizeWarning {
  code: string
  message: string
  class_section_id?: string
  user_id?: string
}

export interface FinalizeCompleteness {
  classes: {
    total: number
    scheduled: number
  }
  preferences: {
    expected: number
    submitted: number
    complete: boolean
    missing_user_ids: string[]
  }
}

export interface FinalizeResponse {
  study_program_id: string
  state: string
  all_final: boolean
  warnings: FinalizeWarning[]
  completeness: FinalizeCompleteness
}

export interface UnlockRequest {
  reason: string
  confirm?: boolean
}

export interface UnlockResponse {
  state: string
  message: string
  unlocked_count: number
  audit_count: number
}

export interface ClassCountOverrideRequest {
  academic_period_id?: string | null
  course_id: string
  study_program_id: string
  class_count: number
}

export interface ClassCountOverrideResponse {
  override_id: string
  academic_period_id: string
  course_id: string
  study_program_id: string
  class_count: number
  created: boolean
}

async function fetchSchedulingList<T>(
  path: string,
  query?: URLSearchParams,
): Promise<T[]> {
  const suffix = query?.toString()
  const payload = await apiFetch<T[] | { data: T[] }>(
    `${SCHEDULING_BASE}${path}${suffix ? `?${suffix}` : ""}`,
    { auth: true },
  )
  return Array.isArray(payload) ? payload : payload.data
}

export const schedulingService = {
  getBoard(): Promise<BoardResponse> {
    return apiFetch<BoardResponse>(`${SCHEDULING_BASE}/board`, { auth: true })
  },

  generate(request: GenerateRequest): Promise<GenerateResponse> {
    return apiFetch<GenerateResponse>(`${SCHEDULING_BASE}/generate`, {
      method: "POST",
      body: request,
      auth: true,
    })
  },

  getConflicts(): Promise<BoardConflictItem[]> {
    return fetchSchedulingList<BoardConflictItem>("/conflicts")
  },

  moveClass(
    classSectionId: string,
    request: ClassMoveRequest,
  ): Promise<ClassMoveResponse> {
    return apiFetch<ClassMoveResponse>(
      `${SCHEDULING_BASE}/classes/${encodeURIComponent(classSectionId)}`,
      { method: "PATCH", body: request, auth: true },
    )
  },

  finalize(periodId: string): Promise<FinalizeResponse> {
    return apiFetch<FinalizeResponse>(
      `${SCHEDULING_BASE}/periods/${encodeURIComponent(periodId)}/finalize`,
      { method: "POST", auth: true },
    )
  },

  unlock(periodId: string, request: UnlockRequest): Promise<UnlockResponse> {
    return apiFetch<UnlockResponse>(
      `${SCHEDULING_BASE}/periods/${encodeURIComponent(periodId)}/unlock`,
      { method: "POST", body: request, auth: true },
    )
  },

  listRooms(): Promise<RoomResponse[]> {
    return fetchSchedulingList<RoomResponse>("/rooms")
  },

  createRoom(request: RoomCreateRequest): Promise<RoomResponse> {
    return apiFetch<RoomResponse>(`${SCHEDULING_BASE}/rooms`, {
      method: "POST",
      body: request,
      auth: true,
    })
  },

  updateRoom(
    roomId: string,
    request: RoomUpdateRequest,
  ): Promise<RoomResponse> {
    return apiFetch<RoomResponse>(
      `${SCHEDULING_BASE}/rooms/${encodeURIComponent(roomId)}`,
      { method: "PATCH", body: request, auth: true },
    )
  },

  listInstructorReferences(
    params: InstructorReferenceListParams,
  ): Promise<InstructorReferenceResponse[]> {
    const query = new URLSearchParams({
      academic_period_id: params.academic_period_id,
    })
    if (params.role) query.set("role", params.role)
    return fetchSchedulingList<InstructorReferenceResponse>(
      "/instructor-references",
      query,
    )
  },

  async listInstructorPeriods(): Promise<InstructorPeriodListResponse> {
    return apiFetch<InstructorPeriodListResponse>(
      `${SCHEDULING_BASE}/instructor-references/periods`,
      { auth: true },
    )
  },

  async listPreferencePeriods(): Promise<PreferencePeriodListResponse> {
    return apiFetch<PreferencePeriodListResponse>(
      `${SCHEDULING_BASE}/preferences/periods`,
      { auth: true },
    )
  },

  getPeriodSettings(
    params: PeriodSettingsParams,
  ): Promise<SchedulePeriodSettings> {
    const query = new URLSearchParams({
      academic_period_id: params.academic_period_id,
    })
    if (params.study_program_id) {
      query.set("study_program_id", params.study_program_id)
    }
    return apiFetch<SchedulePeriodSettings>(
      `${SCHEDULING_BASE}/period-settings?${query}`,
      { auth: true },
    )
  },

  updatePeriodSettings(
    request: PeriodSettingsRequest,
  ): Promise<SchedulePeriodSettings> {
    return apiFetch<SchedulePeriodSettings>(
      `${SCHEDULING_BASE}/period-settings`,
      { method: "PUT", body: request, auth: true },
    )
  },

  getPreferenceSummary(
    params: PeriodSettingsParams,
  ): Promise<PreferenceSummaryResponse> {
    const query = new URLSearchParams({
      academic_period_id: params.academic_period_id,
    })
    if (params.study_program_id) {
      query.set("study_program_id", params.study_program_id)
    }
    return apiFetch<PreferenceSummaryResponse>(
      `${SCHEDULING_BASE}/preferences/summary?${query}`,
      { auth: true },
    )
  },

  previewAssignments(
    academicPeriodId: string,
    curriculumCourseId?: string | null,
  ): Promise<AssignmentPreviewResponse> {
    const query = new URLSearchParams({
      academic_period_id: academicPeriodId,
    })
    if (curriculumCourseId) {
      query.set("curriculum_course_id", curriculumCourseId)
    }
    return apiFetch<AssignmentPreviewResponse>(
      `${SCHEDULING_BASE}/assignments/preview?${query}`,
      { auth: true },
    )
  },

  saveAssignments(
    request: AssignmentUpsertRequest,
  ): Promise<AssignmentUpsertResponse> {
    return apiFetch<AssignmentUpsertResponse>(
      `${SCHEDULING_BASE}/assignments`,
      { method: "PUT", body: request, auth: true },
    )
  },

  deleteAssignment(
    classSectionId: string,
    curriculumCourseId?: string | null,
  ): Promise<void> {
    const query = new URLSearchParams()
    if (curriculumCourseId) {
      query.set("curriculum_course_id", curriculumCourseId)
    }
    const suffix = query.toString()
    return apiFetch<void>(
      `${SCHEDULING_BASE}/assignments/${encodeURIComponent(classSectionId)}${
        suffix ? `?${suffix}` : ""
      }`,
      { method: "DELETE", auth: true },
    )
  },

  listInstructorCandidates(params: {
    academic_period_id: string
    curriculum_course_id?: string
    search?: string
    page?: number
    page_size?: number
  }): Promise<InstructorCandidateItem[]> {
    const query = new URLSearchParams({
      academic_period_id: params.academic_period_id,
    })
    if (params.curriculum_course_id) {
      query.set("curriculum_course_id", params.curriculum_course_id)
    }
    if (params.search) query.set("search", params.search)
    if (params.page !== undefined) query.set("page", String(params.page))
    if (params.page_size !== undefined) {
      query.set("page_size", String(params.page_size))
    }
    return fetchSchedulingList<InstructorCandidateItem>(
      "/instructor-candidates",
      query,
    )
  },

  getMyPreferences(academicPeriodId: string): Promise<PreferenceResponse> {
    const query = new URLSearchParams({ academic_period_id: academicPeriodId })
    return apiFetch<PreferenceResponse>(
      `${SCHEDULING_BASE}/preferences/me?${query}`,
      { auth: true },
    )
  },

  replaceMyPreferences(
    request: PreferenceReplaceRequest,
  ): Promise<PreferenceResponse> {
    return apiFetch<PreferenceResponse>(`${SCHEDULING_BASE}/preferences/me`, {
      method: "PUT",
      body: request,
      auth: true,
    })
  },

  copyMyPreferences(
    request: PreferenceCopyRequest,
  ): Promise<PreferenceResponse> {
    return apiFetch<PreferenceResponse>(
      `${SCHEDULING_BASE}/preferences/me/copy`,
      {
        method: "POST",
        body: request,
        auth: true,
      },
    )
  },

  copyInstructorReferences(
    request: InstructorCopyRequest,
  ): Promise<InstructorCopyResponse> {
    return apiFetch<InstructorCopyResponse>(
      `${SCHEDULING_BASE}/instructor-references/copy`,
      { method: "POST", body: request, auth: true },
    )
  },

  orderInstructorReferences(
    request: InstructorOrderRequest,
  ): Promise<InstructorOrderResponse> {
    return apiFetch<InstructorOrderResponse>(
      `${SCHEDULING_BASE}/instructor-references/order`,
      { method: "PUT", body: request, auth: true },
    )
  },

  updateInstructorReference(
    referenceId: string,
    request: InstructorReferenceUpdateRequest,
  ): Promise<InstructorReferenceResponse> {
    return apiFetch<InstructorReferenceResponse>(
      `${SCHEDULING_BASE}/instructor-references/${encodeURIComponent(referenceId)}`,
      { method: "PATCH", body: request, auth: true },
    )
  },

  createInstructorReference(
    request: InstructorReferenceCreateRequest,
  ): Promise<InstructorReferenceResponse> {
    return apiFetch<InstructorReferenceResponse>(
      `${SCHEDULING_BASE}/instructor-references`,
      { method: "POST", body: request, auth: true },
    )
  },

  deleteInstructorReference(
    referenceId: string,
    academicPeriodId: string,
  ): Promise<void> {
    const query = new URLSearchParams({
      academic_period_id: academicPeriodId,
    })
    return apiFetch<void>(
      `${SCHEDULING_BASE}/instructor-references/${encodeURIComponent(referenceId)}?${query}`,
      { method: "DELETE", auth: true },
    )
  },

  listCurriculumCourses(): Promise<CurriculumCourseOption[]> {
    return fetchSchedulingList<CurriculumCourseOption>("/curriculum-courses")
  },

  getUnassigned(): Promise<UnassignedItem[]> {
    return fetchSchedulingList<UnassignedItem>("/unassigned")
  },

  setClassCountOverride(
    request: ClassCountOverrideRequest,
  ): Promise<ClassCountOverrideResponse> {
    return apiFetch<ClassCountOverrideResponse>(
      `${SCHEDULING_BASE}/class-count-overrides`,
      { method: "POST", body: request, auth: true },
    )
  },
}
