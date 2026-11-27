"""Penyimpanan rencana studi (degree plan) di PostgreSQL.

Satu jalur tulis/baca untuk tabel `degree_plans` + `degree_plan_items`; router
HTTP hanya memetakan exception domain ke status code.
"""

import uuid
from typing import Optional, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from academics import parity_of
from catalog import (
    authoritative_curriculum_id,
    get_courses_for_curriculum,
    normalize_course_type,
)
from models import (
    Course,
    Curriculum,
    CurriculumCourse,
    DegreePlan,
    DegreePlanItem,
    StudentCourseRecord,
    StudentCurriculumAssignment,
    StudentProfile,
    StudyProgram,
    User,
)
from schemas import (
    DegreePlanCreateRequest,
    DegreePlanItemRequest,
    DegreePlanItemResponse,
    DegreePlanResponse,
    PlacedCourseModel,
)

PLAN_LIMIT = 10


class DuplicatePlanName(Exception):
    def __init__(self, name: str):
        self.name = name


class PlanLimitReached(Exception):
    pass


class UnknownCourse(Exception):
    def __init__(self, code: str):
        self.code = code


class CurriculumMismatch(Exception):
    def __init__(self, code: str):
        self.code = code


class ParityMismatch(Exception):
    def __init__(self, code: str, semester: int):
        self.code = code
        self.semester = semester


class DuplicateCourse(Exception):
    def __init__(self, code: str):
        self.code = code


class PlanValidationFailed(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors


class NoCurriculumAssignment(Exception):
    pass


class AssignmentNotCurrent(Exception):
    pass


async def ensure_assignment(
    db: AsyncSession, user: User
) -> StudentCurriculumAssignment:
    stmt = (
        select(StudentCurriculumAssignment)
        .where(StudentCurriculumAssignment.user_id == user.user_id)
        .order_by(StudentCurriculumAssignment.is_current.desc())
    )
    assignment = (await db.execute(stmt)).scalars().first()
    if assignment:
        return assignment

    profile = await db.get(StudentProfile, user.user_id)
    if profile is None:
        raise NoCurriculumAssignment()

    program_name = (
        await db.execute(
            select(StudyProgram.program_name).where(
                StudyProgram.study_program_id == profile.study_program_id
            )
        )
    ).scalar_one_or_none()
    curriculum_id = (
        await authoritative_curriculum_id(db, program_name)
        if program_name
        else None
    )

    if curriculum_id is None:
        curriculum = (
            await db.execute(
                select(Curriculum)
                .where(
                    Curriculum.study_program_id == profile.study_program_id,
                    Curriculum.is_active.is_(True),
                )
                .order_by(Curriculum.curriculum_year.desc())
            )
        ).scalars().first()
        if curriculum is None:
            raise NoCurriculumAssignment()
        curriculum_id = curriculum.curriculum_id

    assignment = StudentCurriculumAssignment(
        user_id=user.user_id,
        curriculum_id=curriculum_id,
        is_current=True,
    )
    db.add(assignment)
    await db.flush()
    return assignment


def _plan_query(user_id: uuid.UUID):
    return (
        select(DegreePlan)
        .where(DegreePlan.user_id == user_id)
        .options(
            selectinload(DegreePlan.items)
            .selectinload(DegreePlanItem.curriculum_course)
            .selectinload(CurriculumCourse.course)
        )
        .execution_options(populate_existing=True)
    )


async def list_plans(db: AsyncSession, user: User) -> Sequence[DegreePlan]:
    stmt = _plan_query(user.user_id).order_by(
        (DegreePlan.status == "active").desc(),
        DegreePlan.updated_at.desc(),
    )
    return (await db.execute(stmt)).scalars().all()


async def get_plan(
    db: AsyncSession, user_id: uuid.UUID, plan_id: uuid.UUID
) -> Optional[DegreePlan]:
    stmt = _plan_query(user_id).where(DegreePlan.degree_plan_id == plan_id)
    return (await db.execute(stmt)).scalars().first()


async def _curriculum_id(db: AsyncSession, plan: DegreePlan) -> uuid.UUID:
    curriculum_id = (
        await db.execute(
            select(StudentCurriculumAssignment.curriculum_id).where(
                StudentCurriculumAssignment.student_curriculum_assignment_id
                == plan.student_curriculum_assignment_id
            )
        )
    ).scalar_one_or_none()
    if curriculum_id is None:
        raise NoCurriculumAssignment()
    return curriculum_id


async def _resolve_courses(
    db: AsyncSession,
    curriculum_id: uuid.UUID,
    items: Sequence[DegreePlanItemRequest],
) -> dict[str, CurriculumCourse]:
    codes = [item.course_code.strip().upper() for item in items]
    if len(set(codes)) != len(codes):
        seen: set[str] = set()
        for code in codes:
            if code in seen:
                raise DuplicateCourse(code)
            seen.add(code)

    rows = (
        await db.execute(
            select(CurriculumCourse)
            .join(Course, Course.course_id == CurriculumCourse.course_id)
            .options(selectinload(CurriculumCourse.course))
            .where(
                CurriculumCourse.curriculum_id == curriculum_id,
                Course.course_code.in_(codes),
            )
        )
    ).scalars().all()
    by_code = {row.course.course_code.upper(): row for row in rows}

    missing = [code for code in codes if code not in by_code]
    if missing:
        other = (
            await db.execute(
                select(Course.course_code)
                .join(
                    CurriculumCourse,
                    CurriculumCourse.course_id == Course.course_id,
                )
                .where(Course.course_code.in_(missing))
            )
        ).scalars().all()
        if other:
            raise CurriculumMismatch(other[0])
        raise UnknownCourse(missing[0])

    for item in items:
        code = item.course_code.strip().upper()
        term = by_code[code].term
        if term and (term == "ganjil") != (item.planned_semester % 2 == 1):
            raise ParityMismatch(code, item.planned_semester)

    return by_code


async def _completed_course_labels(db: AsyncSession, plan: DegreePlan) -> list[str]:
    rows = (
        await db.execute(
            select(Course.course_name, Course.course_code)
            .join(
                CurriculumCourse,
                CurriculumCourse.course_id == Course.course_id,
            )
            .join(
                StudentCourseRecord,
                StudentCourseRecord.curriculum_course_id
                == CurriculumCourse.curriculum_course_id,
            )
            .where(
                StudentCourseRecord.user_id == plan.user_id,
                StudentCourseRecord.student_curriculum_assignment_id
                == plan.student_curriculum_assignment_id,
                StudentCourseRecord.record_status == "passed",
            )
        )
    ).all()
    return list(
        dict.fromkeys(label for row in rows for label in row if label)
    )


async def _apply_items(
    db: AsyncSession,
    plan: DegreePlan,
    items: Sequence[DegreePlanItemRequest],
) -> None:
    curriculum_id = await _curriculum_id(db, plan)
    by_code = await _resolve_courses(db, curriculum_id, items)
    desired = {
        by_code[item.course_code.strip().upper()]: item for item in items
    }

    catalog_by_code = {
        course.code.upper(): course
        for course in await get_courses_for_curriculum(db, curriculum_id)
        if course.code
    }
    validation_plan: dict[int, list[PlacedCourseModel]] = {}
    for course, request_item in desired.items():
        if request_item.planning_status != "planned":
            continue
        code = course.course.course_code
        meta = catalog_by_code.get(code.upper())
        prerequisites = [
            item
            for item in (meta.prerequisites if meta else [])
            if not item.startswith("Minimal ")
        ]
        term = (course.term or "").lower()
        parity = (
            "odd"
            if term == "ganjil"
            else "even"
            if term == "genap"
            else parity_of(request_item.planned_semester)
        )
        validation_plan.setdefault(request_item.planned_semester, []).append(
            PlacedCourseModel(
                id=str(course.curriculum_course_id),
                code=code,
                name=course.course.course_name,
                credits=course.credits_total,
                semester=request_item.planned_semester,
                type=normalize_course_type(course.course_type),
                parity=parity,
                prerequisites=prerequisites,
                status="planned",
            )
        )

    if validation_plan:
        from features.planning.validator import validate_plan_constraints

        validation = validate_plan_constraints(
            validation_plan,
            await _completed_course_labels(db, plan),
            maks_sks_per_semester=24,
        )
        if not validation.is_valid:
            raise PlanValidationFailed(validation.errors)

    for existing in list(plan.items):
        if existing.curriculum_course_id not in {
            course.curriculum_course_id for course in desired
        }:
            plan.items.remove(existing)

    placed = {item.curriculum_course_id: item for item in plan.items}
    for course, request_item in desired.items():
        current = placed.get(course.curriculum_course_id)
        if current is None:
            plan.items.append(
                DegreePlanItem(
                    curriculum_course_id=course.curriculum_course_id,
                    planned_semester=request_item.planned_semester,
                    planning_status=request_item.planning_status,
                )
            )
        else:
            current.planned_semester = request_item.planned_semester
            current.planning_status = request_item.planning_status

    await db.flush()
    await db.execute(
        update(DegreePlan)
        .where(DegreePlan.degree_plan_id == plan.degree_plan_id)
        .values(updated_at=func.now())
    )
    await db.flush()


async def create_plan(
    db: AsyncSession, user: User, payload: DegreePlanCreateRequest
) -> DegreePlan:
    assignment = await ensure_assignment(db, user)

    total = (
        await db.execute(
            select(func.count())
            .select_from(DegreePlan)
            .where(DegreePlan.user_id == user.user_id)
        )
    ).scalar_one()
    if total >= PLAN_LIMIT:
        raise PlanLimitReached()

    name = payload.name.strip()
    exists = (
        await db.execute(
            select(DegreePlan.degree_plan_id).where(
                DegreePlan.user_id == user.user_id,
                DegreePlan.student_curriculum_assignment_id
                == assignment.student_curriculum_assignment_id,
                DegreePlan.plan_name == name,
            )
        )
    ).first()
    if exists:
        raise DuplicatePlanName(name)

    plan = DegreePlan(
        user_id=user.user_id,
        student_curriculum_assignment_id=assignment.student_curriculum_assignment_id,
        plan_name=name,
        status="draft",
    )
    plan.items = []
    db.add(plan)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise DuplicatePlanName(name) from exc

    try:
        await _apply_items(db, plan, payload.items)
    except Exception:
        await db.rollback()
        raise
    loaded = await get_plan(db, user.user_id, plan.degree_plan_id)
    assert loaded is not None
    return loaded


async def replace_items(
    db: AsyncSession,
    user: User,
    plan: DegreePlan,
    items: Sequence[DegreePlanItemRequest],
) -> DegreePlan:
    await _apply_items(db, plan, items)
    loaded = await get_plan(db, user.user_id, plan.degree_plan_id)
    assert loaded is not None
    return loaded


async def update_plan(
    db: AsyncSession,
    user: User,
    plan: DegreePlan,
    *,
    name: Optional[str] = None,
    status_value: Optional[str] = None,
) -> DegreePlan:
    if name is not None:
        clean_name = name.strip()
        conflict = (
            await db.execute(
                select(DegreePlan.degree_plan_id).where(
                    DegreePlan.user_id == user.user_id,
                    DegreePlan.student_curriculum_assignment_id
                    == plan.student_curriculum_assignment_id,
                    DegreePlan.plan_name == clean_name,
                    DegreePlan.degree_plan_id != plan.degree_plan_id,
                )
            )
        ).first()
        if conflict:
            raise DuplicatePlanName(clean_name)
        plan.plan_name = clean_name

    if status_value == "active":
        await db.execute(
            update(DegreePlan)
            .where(
                DegreePlan.user_id == user.user_id,
                DegreePlan.status == "active",
                DegreePlan.degree_plan_id != plan.degree_plan_id,
            )
            .values(status="draft")
        )
    if status_value is not None:
        plan.status = status_value

    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise DuplicatePlanName(plan.plan_name) from exc
    except DBAPIError as exc:
        await db.rollback()
        if "current curriculum assignment" in str(exc.orig):
            raise AssignmentNotCurrent() from exc
        raise

    loaded = await get_plan(db, user.user_id, plan.degree_plan_id)
    assert loaded is not None
    return loaded


async def delete_plan(db: AsyncSession, plan: DegreePlan) -> None:
    await db.delete(plan)
    await db.flush()


def to_response(plan: DegreePlan) -> DegreePlanResponse:
    items = []
    for item in plan.items:
        course = item.curriculum_course
        items.append(
            DegreePlanItemResponse(
                id=str(course.curriculum_course_id),
                course_id=str(course.course_id),
                code=course.course.course_code,
                name=course.course.course_name,
                credits=course.credits_total,
                semester=item.planned_semester,
                type=normalize_course_type(course.course_type),
                parity=(
                    "odd"
                    if course.term == "ganjil"
                    else "even"
                    if course.term == "genap"
                    else parity_of(item.planned_semester)
                ),
                desc=course.description or "",
                planning_status=item.planning_status,
            )
        )
    items.sort(key=lambda entry: (entry.semester, entry.code))
    return DegreePlanResponse(
        id=str(plan.degree_plan_id),
        name=plan.plan_name,
        status=plan.status,
        updated_at=plan.updated_at,
        items=items,
    )
