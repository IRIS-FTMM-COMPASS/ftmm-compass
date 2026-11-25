"""Catalog reads backing instructor-candidate and curriculum-course endpoints."""

from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    Course,
    CourseInstructorReference,
    Curriculum,
    CurriculumCourse,
    LecturerProfile,
    StudyProgram,
    User,
)
from .errors import ServiceError
from .instructor_references import (
    _PJMK_ROLE,
    _period_filter,
    _resolve_candidate_course,
)


async def list_candidates(
    db: AsyncSession,
    scope: UUID | None,
    academic_period_id: UUID,
    curriculum_course_id: str | None,
    search: str | None,
    page: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], int] | ServiceError:
    period_id = await _period_filter(db, academic_period_id)
    if isinstance(period_id, ServiceError):
        return period_id

    pjmk_user_ids: list[UUID] = []
    if curriculum_course_id is not None:
        resolved_course_id = await _resolve_candidate_course(
            db, curriculum_course_id, scope
        )
        if isinstance(resolved_course_id, ServiceError):
            return resolved_course_id
        stmt = select(CourseInstructorReference.user_id).where(
            CourseInstructorReference.curriculum_course_id == resolved_course_id,
            CourseInstructorReference.instructor_role == _PJMK_ROLE,
            CourseInstructorReference.user_id.is_not(None),
        )
        stmt = stmt.where(
            CourseInstructorReference.academic_period_id == period_id
        )
        pjmk_user_ids = list((await db.execute(stmt)).scalars().all())

    base = (
        select(User, LecturerProfile, StudyProgram)
        .join(LecturerProfile, LecturerProfile.user_id == User.user_id)
        .outerjoin(
            StudyProgram,
            StudyProgram.study_program_id == LecturerProfile.study_program_id,
        )
        .where(User.role == "lecturer", User.is_active.is_(True))
    )
    count_stmt = (
        select(func.count())
        .select_from(User)
        .join(LecturerProfile, LecturerProfile.user_id == User.user_id)
        .outerjoin(
            StudyProgram,
            StudyProgram.study_program_id == LecturerProfile.study_program_id,
        )
        .where(User.role == "lecturer", User.is_active.is_(True))
    )
    if scope is not None:
        base = base.where(LecturerProfile.study_program_id == scope)
        count_stmt = count_stmt.where(LecturerProfile.study_program_id == scope)
    if pjmk_user_ids:
        base = base.where(User.user_id.not_in(pjmk_user_ids))
        count_stmt = count_stmt.where(User.user_id.not_in(pjmk_user_ids))
    if search and search.strip():
        term = f"%{search.strip()}%"
        condition = or_(
            User.full_name.ilike(term),
            User.email.ilike(term),
            LecturerProfile.employee_number.ilike(term),
        )
        base = base.where(condition)
        count_stmt = count_stmt.where(condition)

    total = int((await db.execute(count_stmt)).scalar_one())
    rows = (
        await db.execute(
            base.order_by(User.full_name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    items = [
        {
            "user_id": str(user.user_id),
            "full_name": user.full_name,
            "email": user.email,
            "employee_number": profile.employee_number,
            "study_program_id": (
                str(profile.study_program_id)
                if profile.study_program_id is not None
                else None
            ),
            "study_program_code": program.program_code if program is not None else None,
            "is_active": user.is_active,
        }
        for user, profile, program in rows
    ]
    return items, total


async def list_curriculum_courses(
    db: AsyncSession, scope: UUID | None
) -> list[dict[str, Any]]:
    stmt = (
        select(
            CurriculumCourse.curriculum_course_id.label("curriculum_course_id"),
            Course.course_id.label("course_id"),
            Curriculum.study_program_id.label("study_program_id"),
            Course.course_code.label("course_code"),
            Course.course_name.label("course_name"),
        )
        .join(Curriculum, Curriculum.curriculum_id == CurriculumCourse.curriculum_id)
        .join(Course, Course.course_id == CurriculumCourse.course_id)
        .where(CurriculumCourse.is_active.is_(True))
    )
    if scope is not None:
        stmt = stmt.where(Curriculum.study_program_id == scope)
    rows = (await db.execute(stmt.order_by(Course.course_code))).all()
    return [
        {
            "curriculum_course_id": str(row.curriculum_course_id),
            "course_id": str(row.course_id),
            "study_program_id": str(row.study_program_id),
            "course_code": row.course_code,
            "course_name": row.course_name,
        }
        for row in rows
    ]
