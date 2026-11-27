"""Schemas for the instructor-reference scheduling endpoints."""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InstructorReferenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference_id: str
    instructor_name: str
    instructor_role: str = "other"
    course_code: str | None = None
    course_name: str | None = None
    curriculum_course_id: str | None = None
    study_program_id: str | None = None
    study_program_code: str | None = None
    study_program_name: str | None = None
    user_id: str | None = None
    is_mapped: bool = False
    lecturer_name: str | None = None
    academic_period_id: str
    position: int | None = None
    can_auto_assign: bool
    eligibility_reason: str
    source_reference_id: str | None = None


class InstructorReferenceCreateRequest(BaseModel):
    curriculum_course_id: str
    instructor_name: str = Field(..., min_length=1, max_length=200)
    instructor_role: Literal["pjmk", "teaching_team", "lecturer", "other"] = "pjmk"
    user_id: str | None = None
    academic_period_id: UUID
    position: int | None = Field(None, ge=1, le=32767)


class InstructorReferenceUpdateRequest(BaseModel):
    instructor_name: str | None = Field(None, min_length=1, max_length=200)
    instructor_role: Literal["pjmk", "teaching_team", "lecturer", "other"] | None = None
    curriculum_course_id: str | None = None
    user_id: str | None = None
    academic_period_id: UUID
    position: int | None = Field(None, ge=1, le=32767)


class InstructorReferenceListResponse(BaseModel):
    data: list[InstructorReferenceResponse] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class InstructorReferenceCopyRequest(BaseModel):
    from_academic_period_id: UUID
    academic_period_id: UUID


class InstructorReferenceCopyResponse(BaseModel):
    data: list[InstructorReferenceResponse] = Field(default_factory=list)
    meta: dict[str, int]


class InstructorReferenceOrderRequest(BaseModel):
    curriculum_course_id: str
    academic_period_id: UUID
    ordered_reference_ids: list[UUID] = Field(..., min_length=1)
