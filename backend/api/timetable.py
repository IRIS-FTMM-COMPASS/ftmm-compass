"""Jadwal kelas aktif mahasiswa. Didaftarkan dua kali oleh app.py (v1 dan legacy)."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.errors import error_response
from auth import get_current_user
from database import get_db
from models import (
    AcademicPeriod,
    ClassSection,
    Course,
    CourseOffering,
    CourseOfferingEligibility,
    Curriculum,
    CurriculumCourse,
    OfferingComponent,
    Timetable,
    TimetableItem,
    User,
)
from plan_storage import NoCurriculumAssignment, ensure_assignment
from schemas import TimetableResponse, TimetableSelectionInput, TimetableSelectionResponse

router = APIRouter()

UNPROCESSABLE = getattr(
    status, "HTTP_422_UNPROCESSABLE_CONTENT", 422
)


class TimetableSaveRequest(BaseModel):
    selections: list[TimetableSelectionInput] = Field(default_factory=list)


def _fail(code: str, message: str, status_code: int = UNPROCESSABLE) -> JSONResponse:
    return error_response(status_code, code, message, detail=message)


def _non_student() -> JSONResponse:
    return _fail("forbidden", "Hanya mahasiswa yang dapat mengakses jadwal kelas.", 403)


def _no_assignment() -> JSONResponse:
    return _fail(
        "no_curriculum_assignment",
        "Profil prodi mahasiswa belum terdaftar pada kurikulum mana pun",
    )


def _no_period() -> JSONResponse:
    return _fail(
        "period_not_found",
        "Tidak ada periode akademik aktif. Hubungi admin untuk mengaktifkan "
        "periode sebelum menyimpan jadwal kelas.",
    )


async def _active_period_id(db: AsyncSession) -> UUID | None:
    return (
        await db.execute(
            select(AcademicPeriod.academic_period_id).where(
                AcademicPeriod.is_active.is_(True)
            )
        )
    ).scalars().first()


async def _assignment(db: AsyncSession, user: User):
    try:
        return await ensure_assignment(db, user)
    except NoCurriculumAssignment:
        return None


def _updated_at(timetable: Timetable) -> str | None:
    value = getattr(timetable, "updated_at", None)
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


@router.get("/me/timetable", response_model=TimetableResponse)
async def get_my_timetable(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "student":
        return _non_student()
    if await _assignment(db, current_user) is None:
        return _no_assignment()

    period_id = await _active_period_id(db)
    if period_id is None:
        return _no_period()

    timetable = (
        await db.execute(
            select(Timetable).where(
                Timetable.user_id == current_user.user_id,
                Timetable.academic_period_id == period_id,
                Timetable.is_active.is_(True),
            )
        )
    ).scalars().first()
    if timetable is None:
        return TimetableResponse(academic_period_id=str(period_id))

    rows = (
        await db.execute(
            select(
                Course.course_code,
                ClassSection.class_section_id,
                ClassSection.section_code,
            )
            .join(
                TimetableItem,
                TimetableItem.class_section_id == ClassSection.class_section_id,
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
            .where(TimetableItem.timetable_id == timetable.timetable_id)
            .order_by(Course.course_code, ClassSection.section_code)
        )
    ).all()
    return TimetableResponse(
        academic_period_id=str(period_id),
        selections=[
            TimetableSelectionResponse(
                course_code=code,
                section_id=str(section_id),
                section_code=section_code,
            )
            for code, section_id, section_code in rows
        ],
        updated_at=_updated_at(timetable),
    )


@router.put("/me/timetable", response_model=TimetableResponse)
async def replace_my_timetable(
    request: TimetableSaveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "student":
        return _non_student()
    assignment = await _assignment(db, current_user)
    if assignment is None:
        return _no_assignment()

    period_id = await _active_period_id(db)
    if period_id is None:
        return _no_period()

    seen_codes: set[str] = set()
    for selection in request.selections:
        if selection.course_code in seen_codes:
            return _fail(
                "duplicate_course",
                "Setiap mata kuliah hanya boleh memiliki satu section",
            )
        seen_codes.add(selection.course_code)

    student_profile = current_user.student_profile
    curriculum_codes: set[str] = set()
    if student_profile is not None:
        curriculum_codes = set(
            (
                await db.execute(
                    select(Course.course_code)
                    .join(
                        CurriculumCourse,
                        CurriculumCourse.course_id == Course.course_id,
                    )
                    .join(
                        Curriculum,
                        Curriculum.curriculum_id == CurriculumCourse.curriculum_id,
                    )
                    .where(
                        Curriculum.study_program_id
                        == student_profile.study_program_id,
                        Curriculum.is_active.is_(True),
                    )
                )
            ).scalars().all()
        )
    for selection in request.selections:
        if selection.course_code not in curriculum_codes:
            return _fail(
                "curriculum_mismatch",
                f"Mata kuliah {selection.course_code} tidak termasuk kurikulum "
                "yang ditetapkan",
            )

    section_ids = [selection.section_id for selection in request.selections]
    available: dict[UUID, tuple[str, str]] = {}
    if section_ids:
        rows = (
            await db.execute(
                select(
                    ClassSection.class_section_id,
                    ClassSection.section_code,
                    Course.course_code,
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
                .where(
                    ClassSection.class_section_id.in_(section_ids),
                    CourseOffering.academic_period_id == period_id,
                )
            )
        ).all()
        available = {
            section_id: (section_code, code)
            for section_id, section_code, code in rows
        }

    selections: list[TimetableSelectionResponse] = []
    for selection in request.selections:
        found = available.get(selection.section_id)
        if found is None or found[1] != selection.course_code:
            return _fail(
                "section_not_found",
                f"Section {selection.section_id} tidak tersedia untuk "
                f"{selection.course_code} pada periode ini",
            )
        selections.append(
            TimetableSelectionResponse(
                course_code=selection.course_code,
                section_id=str(selection.section_id),
                section_code=found[0],
            )
        )

    eligible_section_ids: set[UUID] = set()
    if section_ids:
        eligible_section_ids = set(
            (
                await db.execute(
                    select(ClassSection.class_section_id)
                    .join(
                        OfferingComponent,
                        OfferingComponent.offering_component_id
                        == ClassSection.offering_component_id,
                    )
                    .join(
                        CourseOfferingEligibility,
                        CourseOfferingEligibility.course_offering_id
                        == OfferingComponent.course_offering_id,
                    )
                    .join(
                        CurriculumCourse,
                        CurriculumCourse.curriculum_course_id
                        == CourseOfferingEligibility.curriculum_course_id,
                    )
                    .where(
                        ClassSection.class_section_id.in_(section_ids),
                        CurriculumCourse.curriculum_id == assignment.curriculum_id,
                    )
                )
            ).scalars().all()
        )
    for selection in request.selections:
        if selection.section_id not in eligible_section_ids:
            return _fail(
                "section_not_eligible",
                f"Section untuk {selection.course_code} tidak memenuhi syarat "
                "kurikulum mahasiswa",
            )

    timetable = (
        await db.execute(
            select(Timetable).where(
                Timetable.user_id == current_user.user_id,
                Timetable.academic_period_id == period_id,
            )
        )
    ).scalars().first()
    if timetable is None:
        timetable = Timetable(
            user_id=current_user.user_id,
            student_curriculum_assignment_id=assignment.student_curriculum_assignment_id,
            academic_period_id=period_id,
            timetable_name="Jadwal Utama",
            is_active=False,
        )
        db.add(timetable)
        await db.flush()
    elif timetable.is_active:
        timetable.is_active = False
        await db.flush()

    await db.execute(
        delete(TimetableItem).where(TimetableItem.timetable_id == timetable.timetable_id)
    )
    await db.flush()
    db.add_all(
        [
            TimetableItem(
                timetable_id=timetable.timetable_id,
                class_section_id=selection.section_id,
            )
            for selection in request.selections
        ]
    )
    await db.flush()

    if request.selections:
        timetable.is_active = True
        await db.flush()

    await db.commit()

    return TimetableResponse(
        academic_period_id=str(period_id),
        selections=selections,
        updated_at=_updated_at(timetable),
    )
