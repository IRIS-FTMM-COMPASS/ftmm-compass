"""Section kelas dan jadwal pertemuan. Didaftarkan dua kali oleh app.py (v1 dan legacy)."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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


@router.get("/class-sections", response_model=ClassSectionListResponse)
async def list_class_sections(
    course_code: str = Query(min_length=1, max_length=30),
    academic_period_id: UUID | None = None,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    course = (
        await db.execute(select(Course).where(Course.course_code == course_code))
    ).scalars().first()
    if course is None:
        message = f"Mata kuliah dengan kode {course_code} tidak ditemukan"
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "detail": message,
                "error": {
                    "code": "course_not_found",
                    "message": message,
                    "details": [],
                },
            },
        )

    period_id = academic_period_id
    if period_id is None:
        period_id = (
            await db.execute(
                select(AcademicPeriod.academic_period_id).where(
                    AcademicPeriod.is_active.is_(True)
                )
            )
        ).scalars().first()

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

    sections: dict[str, ClassSectionResponse] = {}
    for section, component, schedule in rows:
        key = str(section.class_section_id)
        if key not in sections:
            sections[key] = ClassSectionResponse(
                section_id=key,
                section_code=section.section_code,
                component_code=component.component_code,
                component_type=component.component_type,
                capacity=section.capacity,
                enrollment_status=section.enrollment_status,
            )
        if schedule is not None:
            day = schedule.day_of_week
            sections[key].schedules.append(
                SectionScheduleResponse(
                    day_of_week=day,
                    day=DAY_NAMES[day - 1] if 1 <= day <= 5 else str(day),
                    start_time=schedule.start_time.strftime("%H:%M"),
                    end_time=schedule.end_time.strftime("%H:%M"),
                    room=schedule.room_name,
                )
            )

    payload = list(sections.values())
    return ClassSectionListResponse(
        data=payload, meta={"total": len(payload)}
    )
