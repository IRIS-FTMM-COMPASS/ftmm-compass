from datetime import date, datetime
from typing import List, Optional, Dict, Literal, Any, Union
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator
from settings import ACCESS_TOKEN_EXPIRE_SECONDS

class OllamaHealthDetail(BaseModel):
    online: bool
    host: str
    default_model: str


class HealthResponse(BaseModel):
    status: str = "healthy"
    service: str = "FTMM Compass AI Planner Gateway"
    chatbot_service_online: bool = False
    chatbot_model: Optional[str] = None
    ollama_online: bool = False
    default_model: Optional[str] = None
    ollama: Optional[OllamaHealthDetail] = None
    database_online: bool = False
    active_streams: int = 0
    first_token_latency_ms: Optional[float] = None
    last_stream_duration_ms: Optional[float] = None

class StudentProfile(BaseModel):
    program_studi: Optional[str] = Field(
        None, description="Nama program studi resmi FTMM (e.g. Rekayasa Perangkat Lunak, Teknologi Sains Data)"
    )
    semester_saat_ini: Optional[int] = Field(
        None, ge=1, le=8, description="Semester yang sedang ditempuh mahasiswa (1-8)"
    )
    riwayat_matkul_lulus: List[str] = Field(
        default_factory=list, description="Daftar nama atau kode mata kuliah yang sudah lulus"
    )
    minat_fokus: List[str] = Field(
        default_factory=list, description="Bidang minat/spesialisasi karir (e.g. Data Science, Machine Learning, Web Backend)"
    )
    target_kelulusan_semester: int = Field(
        8, ge=7, le=8, description="Target semester untuk lulus (7 atau 8)"
    )
    maks_sks_per_semester: int = Field(
        24, ge=12, le=24, description="Batas maksimum SKS per semester"
    )
    is_confirmed_by_user: bool = Field(
        False, description="Apakah mahasiswa sudah mengonfirmasi ringkasan data profil"
    )


class CourseModel(BaseModel):
    id: str = ""
    code: Optional[str] = None
    name: str
    credits: int = 3
    semester: int = 1
    type: Literal["Wajib", "Pilihan"] = "Pilihan"
    parity: Literal["odd", "even"] = "odd"
    desc: str = ""
    program: Optional[str] = None
    lecturer: Optional[str] = None
    prerequisites: List[str] = Field(default_factory=list)
    is_active: bool = True
    course_scope: str = "program_studi"
class AdminCourseCreateRequest(BaseModel):
    course_code: str = Field(..., min_length=1, max_length=30)
    course_name: str = Field(..., min_length=1, max_length=200)
    program_name: str = Field(..., min_length=1)
    credits: int = Field(3, ge=1, le=24)
    recommended_semester: int = Field(1, ge=1, le=8)
    term: Literal["ganjil", "genap"] = "ganjil"
    course_type: Literal["Wajib", "Pilihan"] = "Pilihan"
    description: Optional[str] = ""
    lecturer: Optional[str] = None
    prerequisites: List[str] = Field(default_factory=list)

class AdminCourseUpdateRequest(BaseModel):
    course_code: Optional[str] = Field(None, min_length=1, max_length=30)
    course_name: Optional[str] = Field(None, min_length=1, max_length=200)
    program_name: Optional[str] = Field(None, min_length=1)
    credits: Optional[int] = Field(None, ge=1, le=24)
    recommended_semester: Optional[int] = Field(None, ge=1, le=8)
    term: Optional[Literal["ganjil", "genap"]] = None
    course_type: Optional[Literal["Wajib", "Pilihan"]] = None
    description: Optional[str] = None
    lecturer: Optional[str] = None
    is_active: Optional[bool] = None
    prerequisites: Optional[List[str]] = None


class PlacedCourseModel(CourseModel):
    status: Literal["completed", "planned", "wishlist"] = "planned"


class PlanValidationRequest(BaseModel):
    program_studi: str
    semester_saat_ini: int
    riwayat_matkul_lulus: List[str] = Field(default_factory=list)
    maks_sks_per_semester: int = 24
    plan: Dict[int, List[PlacedCourseModel]]


class PlanValidationResponse(BaseModel):
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    total_credits: int = 0
    total_sks_planned: int = 0
    semester_credits: Dict[int, int] = Field(default_factory=dict)
    details_per_semester: Dict[int, Dict[str, Any]] = Field(default_factory=dict)


class CourseSearchItem(CourseModel):
    score: float = 0.0


class CourseSearchResponse(BaseModel):
    source: str = "chatbot_ssot"
    query: str
    program_studi: Optional[str] = None
    total_hits: int = 0
    results: List[CourseSearchItem] = Field(default_factory=list)

class PlanPayloadSummary(BaseModel):
    program_studi: str
    current_semester: int
    target_semester: int
    total_credits: int
    focus_tracks: List[str] = Field(default_factory=list)
    note: Optional[str] = ""


class DegreePlanPayload(BaseModel):
    action: Literal["APPLY_DEGREE_PLAN"] = "APPLY_DEGREE_PLAN"
    summary: PlanPayloadSummary
    plan: Dict[int, List[PlacedCourseModel]] = Field(default_factory=dict)


PlanningStatus = Literal["planned", "wishlist"]


class DegreePlanItemRequest(BaseModel):
    course_code: str = Field(min_length=1, max_length=40)
    planned_semester: int = Field(ge=1, le=14)
    planning_status: PlanningStatus = "planned"


class DegreePlanItemsRequest(BaseModel):
    items: List[DegreePlanItemRequest] = Field(default_factory=list, max_length=200)


class DegreePlanCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    items: List[DegreePlanItemRequest] = Field(default_factory=list, max_length=200)


class DegreePlanUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    status: Optional[Literal["draft", "active"]] = None


class DegreePlanItemResponse(BaseModel):
    id: str
    course_id: str
    code: str
    name: str
    credits: int
    semester: int
    type: Literal["Wajib", "Pilihan"]
    parity: Literal["odd", "even"]
    desc: str = ""
    planning_status: PlanningStatus = "planned"


class DegreePlanResponse(BaseModel):
    id: str
    name: str
    status: Literal["draft", "active", "archived"]
    updated_at: datetime
    items: List[DegreePlanItemResponse] = Field(default_factory=list)


class DegreePlanListResponse(BaseModel):
    data: List[DegreePlanResponse] = Field(default_factory=list)
    meta: Dict[str, int] = Field(default_factory=dict)


class DegreePlanCatalogResponse(BaseModel):
    data: List[CourseModel] = Field(default_factory=list)


RecordStatus = Literal["taking", "passed", "failed", "transferred"]


class CourseRecordPeriod(BaseModel):
    academic_year_start: int
    term: str
    label: str


class CourseRecordResponse(BaseModel):
    id: str
    course_id: str
    code: str
    name: str
    credits: int
    semester: int
    type: Literal["Wajib", "Pilihan"]
    parity: Literal["odd", "even"]
    desc: str = ""
    record_status: RecordStatus
    final_grade: Optional[str] = None
    completed_at: Optional[date] = None
    period: CourseRecordPeriod


class CourseRecordListResponse(BaseModel):
    data: List[CourseRecordResponse] = Field(default_factory=list)
    meta: Dict[str, int] = Field(default_factory=dict)


class CourseRecordCreateRequest(BaseModel):
    course_code: str = Field(min_length=1, max_length=40)
    final_grade: str = Field(min_length=1, max_length=2)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    plan_payload: Optional[DegreePlanPayload] = None


class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = Field(default_factory=list)
    student_profile: Optional[StudentProfile] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    updated_profile: StudentProfile
    plan_payload: Optional[DegreePlanPayload] = None
    action_type: Optional[str] = None
    missing_slots: List[str] = Field(default_factory=list)
    routing_mode: Optional[str] = None
    latency_ms: Optional[float] = None


class LoginRequest(BaseModel):
    identifier: str
    password: str


class UserStudentProfileResponse(BaseModel):
    student_number: Optional[str] = None
    study_program: Optional[str] = None
    program_code: Optional[str] = None
    admission_year: Optional[int] = None
    current_semester: Optional[int] = None

class UserProfileUpdateRequest(BaseModel):
    phone_number: Optional[str] = Field(None, max_length=30, description="Nomor telepon atau WhatsApp aktif")
    bio: Optional[str] = Field(None, max_length=500, description="Bio atau deskripsi singkat akademik")
    career_interests: Optional[List[str]] = Field(default_factory=list, description="Minat atau fokus bidang karir")
    model_config = ConfigDict(extra="forbid")



class UserResponse(BaseModel):
    user_id: str
    email: str
    full_name: str
    role: str
    auth_provider: str = "Cybercampus SSO UNAIR"
    academic_identifier: Optional[str] = None
    unit_name: Optional[str] = None
    phone_number: Optional[str] = None
    bio: Optional[str] = None
    career_interests: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    student_profile: Optional[UserStudentProfileResponse] = None
    needs_revalidation: bool = False
    is_program_coordinator: bool = False

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = ACCESS_TOKEN_EXPIRE_SECONDS
    user: UserResponse


class RegisterRequest(BaseModel):
    email: str = Field(..., max_length=255)
    full_name: str = Field(..., min_length=2, max_length=150)
    student_number: str = Field(..., min_length=3, max_length=30)
    admission_year: int = Field(...)
    password: str = Field(..., min_length=8, max_length=128)
    study_program_code: Optional[str] = Field(None, max_length=20)


class RegisterResponse(LoginResponse):
    recovery_code: str


class RecoverRequest(BaseModel):
    recovery_code: str = Field(..., min_length=1, max_length=64)
    new_password: str = Field(..., min_length=8, max_length=128)


class RecoverResponse(BaseModel):
    message: str
    recovery_code: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class ChangePasswordResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = ACCESS_TOKEN_EXPIRE_SECONDS
    message: str


class AccountResponse(BaseModel):
    user_id: str
    email: str
    full_name: str
    role: str
    is_active: bool = True
    status: str = "active"
    student_number: Optional[str] = None
    created_at: Optional[str] = None
    needs_revalidation: bool = False
    study_program: Optional[str] = None
    admission_year: Optional[int] = None
    current_semester: Optional[int] = None


class AccountListResponse(BaseModel):
    data: List[AccountResponse] = Field(default_factory=list)
    meta: Dict[str, int] = Field(default_factory=dict)


class AccountUpdateRequest(BaseModel):
    is_active: bool
    reason: Optional[str] = None


class AccountUpdateResponse(BaseModel):
    data: AccountResponse


class ResetPasswordResponse(BaseModel):
    message: str
    temporary_password: str

class ResetPasswordRequest(BaseModel):
    reason: Optional[str] = None


class AdminAuthorityTraceResponse(BaseModel):
    trace_id: str
    actor_user_id: str
    actor_snapshot: str
    target_user_id: str
    target_snapshot: str
    action: str
    field_name: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    reason: Optional[str] = None
    created_at: str


class AdminProfileUpdateRequest(BaseModel):
    study_program_id: UUID
    admission_year: int
    student_number: str
    current_semester: int
    reason: str
    model_config = ConfigDict(extra="forbid")


class AnonymizeRequest(BaseModel):
    confirmation: str
    reason: str

class PollingPeriodResponse(BaseModel):
    period_id: str
    academic_year: str
    term: Literal["ganjil", "genap"]
    target_semester_type: Literal["ganjil", "genap"]
    start_date: str
    end_date: str
    is_active: bool
    min_quorum: int
    max_votes_per_student: int
    description: Optional[str] = None


class CreatePollingPeriodRequest(BaseModel):
    title: str
    academic_year: str
    target_term: Literal["ganjil", "genap"]
    target_semester: int = Field(..., ge=1, le=8)
    start_date: str
    end_date: str
    status: Literal["upcoming", "open", "closed"] = "upcoming"
    min_quota_threshold: int = 15
    max_votes_per_student: int = 3
    description: Optional[str] = None


class ElectiveVoteRequest(BaseModel):
    course_id: str
    priority: int = Field(..., ge=1, le=3)


class ElectiveVoteResponse(BaseModel):
    vote_id: str
    course_id: str
    course_code: Optional[str] = None
    course_name: Optional[str] = None
    priority: int
    created_at: str


class CourseDemandItem(BaseModel):
    course_id: str
    course_code: str
    course_name: str
    study_program: str
    program_code: Optional[str] = None
    credits: int = 3
    total_votes: int = 0
    priority_1_votes: int = 0
    priority_2_votes: int = 0
    priority_3_votes: int = 0
    min_quorum: int = 15
    status: Literal["QUALIFIED", "BORDERLINE", "UNQUALIFIED"]
    projected_classes: int = 0


class DemandAnalyticsResponse(BaseModel):
    period: PollingPeriodResponse
    total_students_voted: int
    items: List[CourseDemandItem] = Field(default_factory=list)


class DashboardScheduleItem(BaseModel):
    id: str
    course_id: str
    course_code: str
    course_name: str
    credits: int
    day: str
    start_time: str
    end_time: str
    time: str
    room: str
    lecturer: Optional[str] = None
    class_name: Optional[str] = None
    enrolled_students: Optional[int] = None
    color: Optional[str] = "teal"


class AcademicPeriodResponse(BaseModel):
    academic_year: str
    term: Literal["ganjil", "genap", "pendek"]
    label: str
    term_label: str
    week_label: str
    start_date: date
    end_date: date
    first_week_monday: date
    semester_weeks: int
    semester_number: Optional[int] = None


class StudentDashboardStats(BaseModel):
    type: Literal["student"] = "student"
    sks_completed: int
    sks_target: int = 144
    completion_percentage: float
    current_semester: int
    courses_planned: int
    sks_planned: int
    gpa: float
    predicate: str


class LecturerDashboardStats(BaseModel):
    type: Literal["lecturer"] = "lecturer"
    courses_taught: int
    sks_taught: int
    total_students: int
    advisee_students: int
    status: str


class AdminDashboardStats(BaseModel):
    type: Literal["admin"] = "admin"
    total_active_students: int
    total_lecturers: int
    total_courses: int
    total_study_programs: int
    system_status: str


class DashboardMeResponse(BaseModel):
    user_id: str
    full_name: str
    role: str
    email: str
    student_number: Optional[str] = None
    study_program: Optional[str] = None
    stats: Union[StudentDashboardStats, LecturerDashboardStats, AdminDashboardStats]
    schedule: List[DashboardScheduleItem] = Field(default_factory=list)
    schedule_status: str = "Jadwal masih dalam proses"


class NotificationItemResponse(BaseModel):
    id: str
    title: str
    message: str
    type: Literal["warning", "deadline", "info", "success"] = "info"
    is_read: bool = False
    action_url: Optional[str] = None
    timestamp: str
    created_at: str


class NotificationListResponse(BaseModel):
    unread_count: int
    items: List[NotificationItemResponse]


class TimetableSelectionInput(BaseModel):
    course_code: str = Field(min_length=1, max_length=30)
    section_id: UUID


class TimetableSelectionResponse(BaseModel):
    course_code: str
    section_id: str
    section_code: str


class TimetableResponse(BaseModel):
    academic_period_id: Optional[str] = None
    selections: List[TimetableSelectionResponse] = Field(default_factory=list)
    updated_at: Optional[str] = None


# --- Penjadwalan lintas program studi (Papan Jadwal Bersama) ---


class RoomCreateRequest(BaseModel):
    room_code: str = Field(..., min_length=1, max_length=50)
    building: str = Field(..., min_length=1, max_length=50)
    floor: Optional[str] = Field(None, max_length=20)
    capacity: int = Field(..., ge=1, le=32767)
    owner_study_program_id: Optional[str] = None
    is_active: bool = True


class RoomUpdateRequest(BaseModel):
    room_code: Optional[str] = Field(None, min_length=1, max_length=50)
    building: Optional[str] = Field(None, min_length=1, max_length=50)
    floor: Optional[str] = Field(None, max_length=20)
    capacity: Optional[int] = Field(None, ge=1, le=32767)
    owner_study_program_id: Optional[str] = None
    is_active: Optional[bool] = None


class RoomResponse(BaseModel):
    room_code: str
    room_id: str
    building: str = "NANO"
    floor: Optional[str] = None
    capacity: int
    owner_study_program_id: Optional[str] = None
    is_active: bool = True


class RoomListResponse(BaseModel):
    data: List[RoomResponse] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)


class InstructorReferenceResponse(BaseModel):
    reference_id: str
    instructor_name: str
    instructor_role: str = "other"
    course_code: Optional[str] = None
    course_name: Optional[str] = None
    curriculum_course_id: Optional[str] = None
    study_program_id: Optional[str] = None
    study_program_code: Optional[str] = None
    study_program_name: Optional[str] = None
    user_id: Optional[str] = None
    is_mapped: bool = False
    lecturer_name: Optional[str] = None


class InstructorReferenceCreateRequest(BaseModel):
    curriculum_course_id: str
    instructor_name: str = Field(..., min_length=1, max_length=200)
    instructor_role: Literal["pjmk", "teaching_team", "lecturer", "other"] = "pjmk"
    user_id: Optional[str] = None


class InstructorReferenceUpdateRequest(BaseModel):
    instructor_name: Optional[str] = Field(None, min_length=1, max_length=200)
    instructor_role: Optional[
        Literal["pjmk", "teaching_team", "lecturer", "other"]
    ] = None
    curriculum_course_id: Optional[str] = None
    # Null eksplisit pada user_id memutus pemetaan; field lain diabaikan bila null.
    user_id: Optional[str] = None


class InstructorReferenceListResponse(BaseModel):
    data: List[InstructorReferenceResponse] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)


class CurriculumCourseOption(BaseModel):
    curriculum_course_id: str
    course_code: str
    course_name: str
    course_id: str
    study_program_id: str


class CurriculumCourseListResponse(BaseModel):
    data: List[CurriculumCourseOption] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)


class InstructorCandidateItem(BaseModel):
    user_id: str
    full_name: str
    email: str
    employee_number: Optional[str] = None
    study_program_id: Optional[str] = None
    study_program_code: Optional[str] = None
    is_active: bool = True


class InstructorCandidateListResponse(BaseModel):
    data: List[InstructorCandidateItem] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)




class StudyProgramIdentity(BaseModel):
    study_program_id: str
    study_program_code: str = ""
    study_program_name: str = ""


class CurriculumContextItem(StudyProgramIdentity):
    curriculum_course_id: str
    curriculum_id: str
    course_code: str = ""
    course_name: str = ""
    pjmk_reference_id: Optional[str] = None


class UnassignedItem(BaseModel):
    class_section_id: str
    course_id: str = ""
    course_code: str = ""
    course_name: str = ""
    section_code: str = ""
    reason: str = ""
    reason_code: str = ""
    programs: List[StudyProgramIdentity] = Field(default_factory=list)
    eligible_curriculum_contexts: List[CurriculumContextItem] = Field(
        default_factory=list
    )
    action: Literal[
        "open_pjmk_form",
        "edit_pjmk",
        "open_assignment",
        "open_room_detail",
        "open_course_detail",
    ] = "open_course_detail"
    pjmk_reference_id: Optional[str] = None


class BoardClassProgram(StudyProgramIdentity):
    state: str = "draft"
    label: str = "Jadwal masih dalam proses"


class BoardClassItem(BaseModel):
    class_section_id: str
    section_code: str = ""
    course_code: str = ""
    course_name: str = ""
    credits: int = 0
    face_to_face_minutes: int = 0
    course_id: str = ""
    study_program_id: str = ""
    study_program_code: str = ""
    study_program_name: str = ""
    program_ids: List[str] = Field(default_factory=list)
    programs: List[BoardClassProgram] = Field(default_factory=list)
    day_of_week: int = 0
    start_hour: int = 0
    end_hour: int = 0
    room_id: Optional[str] = None
    room_code: Optional[str] = None
    lecturers: List[str] = Field(default_factory=list)
    assigned_lecturer_id: Optional[str] = None
    assigned_lecturer_name: Optional[str] = None
    assigned_curriculum_course_id: Optional[str] = None
    can_edit: bool = False
    read_only: bool = True
    is_manually_edited: bool = False
    state: str = "draft"
    is_stale: bool = False
    run_id: Optional[str] = None
    input_revision: int = 0

    @model_validator(mode="after")
    def derive_face_to_face_minutes(self) -> "BoardClassItem":
        if self.face_to_face_minutes == 0 and self.credits > 0:
            self.face_to_face_minutes = self.credits * 50
        return self


class BoardConflictItem(BaseModel):
    class_section_a_id: str
    class_section_b_id: str
    kind: Literal["lecturer", "room"]
    day_of_week: int
    start_hour: int
    end_hour: int
    object_id: Optional[str] = None
    object_name: str = ""
    object_label: str = ""
    class_section_a_label: str = ""
    class_section_b_label: str = ""
    day_name: str = ""
    label: str = ""


class BoardProgramStatus(StudyProgramIdentity):
    study_program_id: str
    study_program_code: str = ""
    study_program_name: str = ""
    state: str = "draft"
    label: str = "Jadwal masih dalam proses"
    finalized_at: Optional[str] = None
    is_stale: bool = False
    run_id: Optional[str] = None
    input_revision: int = 0


class BoardData(BaseModel):
    academic_period_id: str
    period_label: str = ""
    classes: List[BoardClassItem] = Field(default_factory=list)
    conflicts: List[BoardConflictItem] = Field(default_factory=list)
    programs: List[BoardProgramStatus] = Field(default_factory=list)
    unassigned: List[UnassignedItem] = Field(default_factory=list)


class BoardResponse(BaseModel):
    data: BoardData
    meta: Dict[str, Any] = Field(default_factory=dict)


class GenerateRequest(BaseModel):
    academic_period_id: Optional[str] = None
    mode: Literal["fill_empty", "regenerate", "full_reset"] = "fill_empty"
    study_program_id: Optional[str] = None
    confirm_full_reset: bool = False


class GenerateResponse(BaseModel):
    run_id: str
    assigned: int = 0
    unassigned: List[UnassignedItem] = Field(default_factory=list)
    conflicts: List[BoardConflictItem] = Field(default_factory=list)
    mode: str = "fill_empty"
    assigned_count: int = 0
    unassigned_count: int = 0
    conflict_count: int = 0
    input_revision: int = 0
    study_program_id: Optional[str] = None
    regenerated_count: int = 0
    preserved_final_count: int = 0
    preserved_manual_count: int = 0


class CourseQuotaUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    academic_period_id: Optional[str] = None
    class_count: int = Field(..., ge=1, le=3)
    capacity_per_class: int = Field(40, ge=1, le=100)
    reason: Optional[str] = None


class CourseQuotaResponse(BaseModel):
    curriculum_course_id: str
    study_program_id: str
    academic_period_id: str
    class_count: int
    capacity_per_class: int
    total_quota: int
    enrolled_count: int = 0
    created: bool = False


class ClassMoveRequest(BaseModel):
    day_of_week: int = Field(..., ge=1, le=5)
    start_hour: int = Field(..., ge=7, le=16)
    room_id: str = ""
    reason: str = Field(..., min_length=1, max_length=500)


class ClassMoveResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    class_: BoardClassItem = Field(..., alias="class")
    conflicts: List[BoardConflictItem] = Field(default_factory=list)


class FinalizeWarning(BaseModel):
    code: str
    message: str
    class_section_id: Optional[str] = None
    user_id: Optional[str] = None


class FinalizeClassCompleteness(BaseModel):
    total: int = 0
    scheduled: int = 0


class FinalizePreferenceCompleteness(BaseModel):
    expected: int = 0
    submitted: int = 0
    complete: int = 0
    missing_user_ids: List[str] = Field(default_factory=list)


class FinalizeCompleteness(BaseModel):
    classes: FinalizeClassCompleteness = Field(default_factory=FinalizeClassCompleteness)
    preferences: FinalizePreferenceCompleteness = Field(
        default_factory=FinalizePreferenceCompleteness
    )


class FinalizeResponse(BaseModel):
    study_program_id: str = ""
    state: str = "final"
    all_final: bool = False
    warnings: List[FinalizeWarning] = Field(default_factory=list)
    completeness: FinalizeCompleteness = Field(default_factory=FinalizeCompleteness)

class UnlockRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)
    confirm: bool = False


class ConflictListResponse(BaseModel):
    data: List[BoardConflictItem] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)


class EditLogEntry(BaseModel):
    id: str
    class_section_id: str
    changed_by: str
    changed_by_name: str
    reason: str
    before_state: Optional[Dict[str, Any]] = None
    after_state: Optional[Dict[str, Any]] = None
    created_at: str


class EditLogResponse(BaseModel):
    data: List[EditLogEntry] = Field(default_factory=list)
    meta: Dict[str, int] = Field(default_factory=dict)
