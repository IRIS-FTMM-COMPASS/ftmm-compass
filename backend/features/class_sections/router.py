"""Section kelas dan jadwal pertemuan. Didaftarkan dua kali oleh app.py (v1 dan legacy)."""

from collections.abc import Iterable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.errors import error_response
from auth import get_current_user
from database import get_db
from models import (
    AcademicPeriod,
    ClassSchedule,
    ClassSection,
    Course,
    CourseOffering,
    OfferingComponent,
    User,
)
from scheduling_common import university_course_ids

router = APIRouter()

DAY_NAMES = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat")


class SectionScheduleResponse(BaseModel):
    day_of_week: int
    day: str
    start_time: str
    end_time: str
    room: str | None = None


class ClassSectionResponse(BaseModel):
    section_id: str
    section_code: str
    component_code: str
    component_type: str
    capacity: int | None = None
    enrollment_status: str
    schedules: list[SectionScheduleResponse] = Field(default_factory=list)


class ClassSectionListResponse(BaseModel):
    data: list[ClassSectionResponse] = Field(default_factory=list)
    meta: dict[str, int] = Field(default_factory=dict)


def _schedule_response(schedule) -> SectionScheduleResponse:
    day = schedule.day_of_week
    return SectionScheduleResponse(
        day_of_week=day,
        day=DAY_NAMES[day - 1] if 1 <= day <= 5 else str(day),
        start_time=schedule.start_time.strftime("%H:%M"),
        end_time=schedule.end_time.strftime("%H:%M"),
        room=schedule.room_name,
    )


def _section_response(section, component) -> ClassSectionResponse:
    return ClassSectionResponse(
        section_id=str(section.class_section_id),
        section_code=section.section_code,
        component_code=component.component_code,
        component_type=component.component_type,
        capacity=section.capacity,
        enrollment_status=section.enrollment_status,
    )


def _assemble_sections(
    rows: Iterable,
) -> dict[str, ClassSectionResponse]:
    sections: dict[str, ClassSectionResponse] = {}
    for row in rows:
        section, component, schedule = row[-3:]
        key = str(section.class_section_id)
        if key not in sections:
            sections[key] = _section_response(section, component)
        if schedule is not None:
            sections[key].schedules.append(_schedule_response(schedule))
    return sections


async def _resolve_period_id(
    db: AsyncSession, requested: UUID | None, *, required: bool = False
) -> UUID | None:
    if requested is not None:
        return requested
    period_id = (
        await db.execute(
            select(AcademicPeriod.academic_period_id).where(
                AcademicPeriod.is_active.is_(True)
            )
        )
    ).scalars().first()
    if period_id is None and required:
        raise HTTPException(
            status_code=getattr(
                status, "HTTP_422_UNPROCESSABLE_CONTENT", 422
            ),
            detail=(
                "Tidak ada periode akademik aktif. Hubungi admin untuk mengaktifkan "
                "periode sebelum memvalidasi jadwal kelas."
            ),
        )
    return period_id


@router.get("/class-sections", response_model=ClassSectionListResponse)
async def list_class_sections(
    course_code: str = Query(min_length=1, max_length=30),
    academic_period_id: UUID | None = None,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    course = (
        await db.execute(
            select(
                Course.course_id,
                Course.course_id.in_(university_course_ids()).label("is_university"),
            ).where(Course.course_code == course_code)
        )
    ).first()
    if course is None:
        message = f"Mata kuliah dengan kode {course_code} tidak ditemukan"
        return error_response(
            status.HTTP_404_NOT_FOUND,
            "course_not_found",
            message,
            detail=message,
        )

    if course.is_university:
        return ClassSectionListResponse(data=[], meta={"total": 0})
    period_id = await _resolve_period_id(db, academic_period_id)

    rows = (
        await db.execute(
            select(ClassSection, OfferingComponent, ClassSchedule)
            .join(
                OfferingComponent,
                OfferingComponent.offering_component_id
                == ClassSection.offering_component_id,
            )
            .join(
                CourseOffering,
                CourseOffering.course_offering_id
                == OfferingComponent.course_offering_id,
            )
            .outerjoin(
                ClassSchedule,
                ClassSchedule.class_section_id == ClassSection.class_section_id,
            )
            .where(
                CourseOffering.course_id == course.course_id,
                CourseOffering.academic_period_id == period_id,
            )
            .order_by(
                OfferingComponent.component_code,
                ClassSection.section_code,
                ClassSchedule.day_of_week,
                ClassSchedule.start_time,
            )
        )
    ).all()

    payload = list(_assemble_sections(rows).values())
    return ClassSectionListResponse(
        data=payload, meta={"total": len(payload)}
    )


class SelectedSectionInput(BaseModel):
    course_code: str = Field(min_length=1, max_length=30)
    section_id: UUID


class ScheduleValidationRequest(BaseModel):
    academic_period_id: UUID | None = None
    selections: list[SelectedSectionInput] = Field(min_length=1)

    @field_validator("selections")
    @classmethod
    def one_section_per_course(cls, value: list[SelectedSectionInput]):
        codes = [item.course_code for item in value]
        if len(codes) != len(set(codes)):
            raise ValueError("Setiap mata kuliah hanya boleh memiliki satu section")
        return value


class SectionConflictResponse(BaseModel):
    course_a_code: str
    course_a_name: str
    section_a_id: str
    section_a_code: str
    course_b_code: str
    course_b_name: str
    section_b_id: str
    section_b_code: str
    day: str
    start_time: str
    end_time: str


class AlternativeSectionResponse(BaseModel):
    course_code: str
    course_name: str
    replaces_section_id: str
    section: ClassSectionResponse


class ScheduleValidationResponse(BaseModel):
    data: list[SectionConflictResponse] = Field(default_factory=list)
    alternatives: list[AlternativeSectionResponse] = Field(default_factory=list)
    meta: dict[str, int] = Field(default_factory=dict)


def _minutes(clock: str) -> int:
    hour, minute = (int(part) for part in clock.split(":"))
    return hour * 60 + minute


def _clock(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _schedule_overlaps(
    first: list[SectionScheduleResponse], second: list[SectionScheduleResponse]
) -> bool:
    return any(
        a.day_of_week == b.day_of_week
        and _minutes(a.start_time) < _minutes(b.end_time)
        and _minutes(b.start_time) < _minutes(a.end_time)
        for a in first
        for b in second
    )


def _compatible_with(
    section: ClassSectionResponse, chosen: dict[str, ClassSectionResponse], code: str
) -> bool:
    return not any(
        _schedule_overlaps(section.schedules, other.schedules)
        for other_code, other in chosen.items()
        if other_code != code
    )


@router.post("/class-sections/validations", response_model=ScheduleValidationResponse)
async def validate_class_sections(
    request: ScheduleValidationRequest,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    period_id = await _resolve_period_id(db, request.academic_period_id, required=True)

    codes = [selection.course_code for selection in request.selections]
    rows = (
        await db.execute(
            select(
                Course.course_code,
                Course.course_name,
                ClassSection,
                OfferingComponent,
                ClassSchedule,
            )
            .join(
                OfferingComponent,
                OfferingComponent.offering_component_id
                == ClassSection.offering_component_id,
            )
            .join(
                CourseOffering,
                CourseOffering.course_offering_id
                == OfferingComponent.course_offering_id,
            )
            .join(Course, Course.course_id == CourseOffering.course_id)
            .outerjoin(
                ClassSchedule,
                ClassSchedule.class_section_id == ClassSection.class_section_id,
            )
            .where(
                Course.course_code.in_(codes),
                CourseOffering.academic_period_id == period_id,
            )
            .order_by(
                Course.course_code,
                OfferingComponent.component_code,
                ClassSection.section_code,
                ClassSchedule.day_of_week,
                ClassSchedule.start_time,
            )
        )
    ).all()

    grouped: dict[str, list] = {}
    names: dict[str, str] = {}
    for row in rows:
        code, name = row[0], row[1]
        names[code] = name
        grouped.setdefault(code, []).append(row)
    catalog = {
        code: {"name": names[code], "sections": _assemble_sections(section_rows)}
        for code, section_rows in grouped.items()
    }

    missing_courses = [code for code in codes if code not in catalog]
    if missing_courses:
        message = (
            "Mata kuliah tidak ditemukan: " + ", ".join(missing_courses)
            if len(missing_courses) > 1
            else f"Mata kuliah dengan kode {missing_courses[0]} tidak ditemukan"
        )
        return error_response(
            status.HTTP_404_NOT_FOUND,
            "course_not_found",
            message,
            detail=message,
        )

    selected: dict[str, ClassSectionResponse] = {}
    for selection in request.selections:
        section_id = str(selection.section_id)
        section = catalog[selection.course_code]["sections"].get(section_id)
        if section is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Section {section_id} tidak tersedia untuk "
                    f"{selection.course_code} pada periode ini"
                ),
            )
        selected[selection.course_code] = section

    conflicts: list[SectionConflictResponse] = []
    course_codes = list(selected)
    for index, code_a in enumerate(course_codes):
        section_a = selected[code_a]
        for code_b in course_codes[index + 1 :]:
            section_b = selected[code_b]
            for slot_a in section_a.schedules:
                for slot_b in section_b.schedules:
                    if slot_a.day_of_week != slot_b.day_of_week:
                        continue
                    start = max(_minutes(slot_a.start_time), _minutes(slot_b.start_time))
                    end = min(_minutes(slot_a.end_time), _minutes(slot_b.end_time))
                    if start >= end:
                        continue
                    conflicts.append(
                        SectionConflictResponse(
                            course_a_code=code_a,
                            course_a_name=catalog[code_a]["name"],
                            section_a_id=section_a.section_id,
                            section_a_code=section_a.section_code,
                            course_b_code=code_b,
                            course_b_name=catalog[code_b]["name"],
                            section_b_id=section_b.section_id,
                            section_b_code=section_b.section_code,
                            day=slot_a.day,
                            start_time=_clock(start),
                            end_time=_clock(end),
                        )
                    )

    conflicting_codes = sorted(
        code
        for code in selected
        if any(
            code in (conflict.course_a_code, conflict.course_b_code)
            for conflict in conflicts
        )
    )
    candidates: dict[str, list[ClassSectionResponse]] = {}
    for code in conflicting_codes:
        current_id = selected[code].section_id
        candidates[code] = [
            section
            for section in catalog[code]["sections"].values()
            if section.section_id != current_id
            and section.schedules
            and _compatible_with(section, selected, code)
        ]

    # Satu solusi per matkul dipilih lebih dulu, lalu kandidat lain disaring
    # terhadap solusi itu agar penerapan batch tidak menciptakan bentrok baru.
    batch: dict[str, ClassSectionResponse] = {}
    for code in conflicting_codes:
        compatible = [
            section
            for section in candidates[code]
            if _compatible_with(section, batch, code)
        ]
        if compatible:
            batch[code] = compatible[0]
    for code in conflicting_codes:
        candidates[code] = [
            section
            for section in candidates[code]
            if _compatible_with(section, batch, code)
        ]

    alternatives = [
        AlternativeSectionResponse(
            course_code=code,
            course_name=catalog[code]["name"],
            replaces_section_id=selected[code].section_id,
            section=section,
        )
        for code in conflicting_codes
        for section in candidates[code]
    ]

    return ScheduleValidationResponse(
        data=conflicts,
        alternatives=alternatives,
        meta={
            "total_conflicts": len(conflicts),
            "total_alternatives": len(alternatives),
        },
    )
