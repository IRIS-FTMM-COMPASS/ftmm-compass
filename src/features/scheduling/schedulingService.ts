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
  user_id?: string | null
  is_mapped: boolean
  lecturer_name?: string | null
}

export interface InstructorMappingRequest {
  user_id: string | null
}

export type InstructorReferenceRole = "pjmk" | "teaching_team" | "lecturer" | "other"

export interface InstructorReferenceCreateRequest {
  curriculum_course_id: string
  instructor_name: string
  instructor_role: InstructorReferenceRole
  user_id?: string | null
}

export interface CurriculumCourseOption {
  curriculum_course_id: string
  course_code: string
  course_name: string
}

export interface InstructorReferenceListResponse {
  data: InstructorReferenceResponse[]
  meta: Record<string, unknown>
}

export interface AvailabilitySlotRequest {
  day_of_week: number
  start_hour: number
  end_hour: number
}

export interface AvailabilityResponse {
  availability_id: string
  day_of_week: number
  start_hour: number
  end_hour: number
  day_name?: string | null
  user_id?: string | null
  lecturer_name?: string | null
}

export interface AvailabilityListResponse {
  data: AvailabilityResponse[]
  meta: Record<string, unknown>
}

export interface AvailabilityLecturerResponse {
  user_id: string
  full_name: string
  study_program_code: string
}

export interface AvailabilityLecturerListResponse {
  data: AvailabilityLecturerResponse[]
  meta: Record<string, unknown>
}

export interface UnassignedItem {
  class_section_id: string
  course_code: string
  reason: string
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
  day_of_week: number
  start_hour: number
  end_hour: number
  room_id: string | null
  room_code: string | null
  lecturers: string[]
  is_manually_edited: boolean
  state: string
}

export interface BoardConflictItem {
  class_section_a_id: string
  class_section_b_id: string
  kind: "lecturer" | "room"
  day_of_week: number
  start_hour: number
  end_hour: number
}

export interface BoardProgramStatus {
  study_program_id: string
  study_program_code: string
  state: string
  label: string
  finalized_at: string | null
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
  meta: Record<string, unknown>
}

export interface GenerateRequest {
  academic_period_id?: string | null
  mode: "fill_empty" | "full_reset"
  confirm_full_reset?: boolean
}

export interface GenerateResponse {
  run_id: string
  assigned: number
  unassigned: UnassignedItem[]
  conflicts: BoardConflictItem[]
  mode: string
  assigned_count: number
  unassigned_count: number
  conflict_count: number
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

export interface FinalizeResponse {
  study_program_id: string
  state: string
  all_final: boolean
}

export interface UnlockRequest {
  reason: string
  confirm?: boolean
}

export interface UnlockResponse {
  state?: string
  message?: string
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

function unwrap<T>(payload: T[] | { data: T[] }): T[] {
  return Array.isArray(payload) ? payload : payload.data
}

async function saveAvailability(
  slots: AvailabilitySlotRequest[],
): Promise<AvailabilityResponse[]> {
  const payload =
    await apiFetch<AvailabilityListResponse | AvailabilityResponse[]>(
      `${SCHEDULING_BASE}/availability/me`,
      { method: "PUT", body: slots, auth: true },
    )
  return unwrap(payload)
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

  async getConflicts(): Promise<BoardConflictItem[]> {
    const payload = await apiFetch<ConflictListResponse | BoardConflictItem[]>(
      `${SCHEDULING_BASE}/conflicts`,
      { auth: true },
    )
    return unwrap(payload)
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

  async listRooms(): Promise<RoomResponse[]> {
    const payload = await apiFetch<RoomListResponse | RoomResponse[]>(
      `${SCHEDULING_BASE}/rooms`,
      { auth: true },
    )
    return unwrap(payload)
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

  async listInstructorReferences(): Promise<InstructorReferenceResponse[]> {
    const payload =
      await apiFetch<InstructorReferenceListResponse | InstructorReferenceResponse[]>(
        `${SCHEDULING_BASE}/instructor-references`,
        { auth: true },
      )
    return unwrap(payload)
  },

  mapInstructor(
    referenceId: string,
    userId: string | null,
  ): Promise<InstructorReferenceResponse> {
    const body: InstructorMappingRequest = { user_id: userId }
    return apiFetch<InstructorReferenceResponse>(
      `${SCHEDULING_BASE}/instructor-references/${encodeURIComponent(referenceId)}`,
      { method: "PATCH", body, auth: true },
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

  deleteInstructorReference(referenceId: string): Promise<void> {
    return apiFetch<void>(
      `${SCHEDULING_BASE}/instructor-references/${encodeURIComponent(referenceId)}`,
      { method: "DELETE", auth: true },
    )
  },

  async listCurriculumCourses(): Promise<CurriculumCourseOption[]> {
    const payload = await apiFetch<{
      data: CurriculumCourseOption[]
    } | CurriculumCourseOption[]>(`${SCHEDULING_BASE}/curriculum-courses`, {
      auth: true,
    })
    return unwrap(payload)
  },

  async getMyAvailability(): Promise<AvailabilityResponse[]> {
    const payload =
      await apiFetch<AvailabilityListResponse | AvailabilityResponse[]>(
        `${SCHEDULING_BASE}/availability/me`,
        { auth: true },
      )
    return unwrap(payload)
  },

  async listAvailabilityLecturers(): Promise<AvailabilityLecturerResponse[]> {
    const payload =
      await apiFetch<AvailabilityLecturerListResponse | AvailabilityLecturerResponse[]>(
        `${SCHEDULING_BASE}/availability/lecturers`,
        { auth: true },
      )
    return unwrap(payload)
  },

  async getLecturerAvailability(
    userId: string,
  ): Promise<AvailabilityResponse[]> {
    const payload =
      await apiFetch<AvailabilityListResponse | AvailabilityResponse[]>(
        `${SCHEDULING_BASE}/availability/${encodeURIComponent(userId)}`,
        { auth: true },
      )
    return unwrap(payload)
  },

  saveMyAvailability(
    slots: AvailabilitySlotRequest[],
  ): Promise<AvailabilityResponse[]> {
    return saveAvailability(slots)
  },

  putMyAvailability(
    slots: AvailabilitySlotRequest[],
  ): Promise<AvailabilityResponse[]> {
    return saveAvailability(slots)
  },

  async getUnassigned(): Promise<UnassignedItem[]> {
    const payload = await apiFetch<UnassignedListResponse | UnassignedItem[]>(
      `${SCHEDULING_BASE}/unassigned`,
      { auth: true },
    )
    return unwrap(payload)
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
