"""Deterministic lecturer-assignment preview and scoped persistence."""

import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.errors import error_response
from audit import record_admin_action
from auth import get_current_user
from database import get_db
from models import (
    AcademicPeriod,
    ClassInstructorAssignment,
    ClassSection,
    CourseOffering,
    LecturerProfile,
    OfferingComponent,
    User,
)
from scheduling_assignment_rules import snake_candidate_index, snake_order
from scheduling_common import current_period_id
from schemas import StudyProgramIdentity
from ..assignment_pool import AssignmentPoolItem, class_assignment_pools
from ..scheduler import (
    CurriculumContext,
    bump_input_revisions,
    current_input_revision,
    load_curriculum_contexts,
    scheduling_input_lock,
)

router = APIRouter()

_UNPROCESSABLE = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)


class AssignmentDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    class_section_id: UUID
    user_id: UUID
    source: Literal["auto", "manual"]
    is_pinned: bool
    curriculum_course_id: UUID | None = None


class AssignmentBulkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decisions: list[AssignmentDecisionRequest] = Field(..., min_length=1, max_length=500)


class AssignmentResponse(BaseModel):
    assignment_id: str
    class_section_id: str
    academic_period_id: str
    curriculum_course_id: str | None
    user_id: str
    lecturer_name: str
    source: Literal["auto", "manual"]
    is_pinned: bool
    is_active: bool
    assigned_by: str
    assigned_at: str


class AssignmentCandidate(BaseModel):
    user_id: str
    lecturer_name: str
    position: int
    is_pjmk: bool
    curriculum_course_id: str


class AssignmentPreviewClass(BaseModel):
    class_section_id: str
    section_code: str
    curriculum_course_id: str
    can_edit: bool
    context_required: bool
    candidate: AssignmentCandidate | None
    existing_assignment: AssignmentResponse | None


class AssignmentPreviewGroup(BaseModel):
    curriculum_course_id: str
    study_program_id: str
    study_program_code: str
    study_program_name: str
    programs: list[StudyProgramIdentity]
    course_code: str
    course_name: str
    can_edit: bool
    pool: list[AssignmentPoolItem]
    classes: list[AssignmentPreviewClass]


class AssignmentPreviewMeta(BaseModel):
    academic_period_id: str
    input_revision: int


class AssignmentPreviewResponse(BaseModel):
    data: list[AssignmentPreviewGroup]
    meta: AssignmentPreviewMeta


class AssignmentBulkMeta(BaseModel):
    academic_period_id: str
    input_revision: int


class AssignmentBulkResponse(BaseModel):
    data: list[AssignmentResponse]
    meta: AssignmentBulkMeta


class AssignmentEnvelope(BaseModel):
    data: AssignmentResponse | None


def _deny(status_code: int, code: str, message: str) -> JSONResponse:
    return error_response(status_code, code, message, detail=message)


def _field_error(field: str, message: str, code: str) -> JSONResponse:
    return error_response(
        _UNPROCESSABLE,
        code,
        message,
        detail=message,
        details=[{"field": field, "message": message, "code": code}],
    )


def _scope(current_user: User) -> UUID | None | JSONResponse:
    if current_user.role == "admin" and current_user.is_active:
        return None
    profile = current_user.lecturer_profile
    if (
        current_user.role == "lecturer"
        and current_user.is_active
        and profile is not None
        and profile.is_program_coordinator
        and profile.study_program_id is not None
    ):
        return profile.study_program_id
    return _deny(
        status.HTTP_403_FORBIDDEN,
        "forbidden",
        "Assignment pengajar hanya tersedia untuk admin dan PJ Prodi.",
    )


async def _period(db: AsyncSession, period_id: UUID | None) -> AcademicPeriod | JSONResponse:
    resolved_id = period_id or await current_period_id(db)
    if resolved_id is None:
        return _deny(404, "period_not_found", "Periode akademik aktif tidak ditemukan.")
    period = await db.get(AcademicPeriod, resolved_id)
    if period is None:
        return _deny(404, "period_not_found", "Periode akademik tidak ditemukan.")
    return period


async def _revision(db: AsyncSession, period_id: UUID, scope: UUID | None) -> int:
    return await current_input_revision(db, period_id, scope)


async def _bump_revisions(
    db: AsyncSession, period_id: UUID, program_ids: set[UUID]
) -> None:
    await bump_input_revisions(db, period_id, program_ids)

def _json_snapshot(value: dict[str, Any] | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _assignment_response(
    assignment: ClassInstructorAssignment, lecturer_name: str | None
) -> AssignmentResponse:
    return AssignmentResponse(
        assignment_id=str(assignment.assignment_id),
        class_section_id=str(assignment.class_section_id),
        academic_period_id=str(assignment.academic_period_id),
        user_id=str(assignment.user_id),
        curriculum_course_id=(
            str(assignment.curriculum_course_id)
            if assignment.curriculum_course_id
            else None
        ),
        lecturer_name=lecturer_name or "Akun tidak tersedia",
        source=assignment.source,
        is_pinned=assignment.is_pinned,
        is_active=assignment.is_active,
        assigned_by=str(assignment.assigned_by),
        assigned_at=assignment.assigned_at.isoformat(),
    )


def _assignment_snapshot(response: AssignmentResponse) -> dict[str, Any]:
    return response.model_dump(mode="json")


async def _record_assignment_change(
    db: AsyncSession,
    actor: User,
    action: str,
    before: AssignmentResponse | None,
    after: AssignmentResponse | None,
) -> None:
    context = after or before
    await record_admin_action(
        db,
        actor=actor,
        target=actor,
        action=f"class_instructor_assignment_{action}",
        reason=(
            f"class_section_id={context.class_section_id} "
            f"academic_period_id={context.academic_period_id}"
        ),
        field_name=context.class_section_id,
        old_value=_json_snapshot(_assignment_snapshot(before) if before else None),
        new_value=_json_snapshot(_assignment_snapshot(after) if after else None),
    )


def _program_identities(
    contexts: list[CurriculumContext],
) -> list[StudyProgramIdentity]:
    programs: dict[UUID, StudyProgramIdentity] = {}
    for context in contexts:
        programs.setdefault(
            context.study_program_id,
            StudyProgramIdentity(
                study_program_id=str(context.study_program_id),
                study_program_code=context.study_program_code,
                study_program_name=context.study_program_name,
            ),
        )
    return list(programs.values())


async def _existing_assignments(
    db: AsyncSession, class_ids: set[UUID]
) -> dict[UUID, AssignmentResponse]:
    if not class_ids:
        return {}
    rows = (
        await db.execute(
            select(ClassInstructorAssignment, User.full_name)
            .outerjoin(User, User.user_id == ClassInstructorAssignment.user_id)
            .where(
                ClassInstructorAssignment.class_section_id.in_(class_ids),
                ClassInstructorAssignment.is_active.is_(True),
            )
            .order_by(ClassInstructorAssignment.class_section_id)
        )
    ).all()
    return {
        assignment.class_section_id: _assignment_response(assignment, lecturer_name)
        for assignment, lecturer_name in rows
    }


def _pool_candidate(
    pool: list[AssignmentPoolItem], class_index: int
) -> AssignmentCandidate | None:
    pool_index = snake_candidate_index(len(pool), class_index)
    if pool_index is None:
        return None
    return AssignmentCandidate(**pool[pool_index].model_dump())


@router.get(
    "/scheduling/assignments/preview", response_model=AssignmentPreviewResponse
)
async def preview_assignments(
    academic_period_id: UUID | None = Query(None),
    curriculum_course_id: UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = _scope(current_user)
    if isinstance(scope, JSONResponse):
        return scope
    period = await _period(db, academic_period_id)
    if isinstance(period, JSONResponse):
        return period
    contexts_by_class = await load_curriculum_contexts(
        db, period.academic_period_id
    )
    visible_class_ids = {
        class_section_id
        for class_section_id, contexts in contexts_by_class.items()
        if scope is None
        or any(context.study_program_id == scope for context in contexts)
    }
    class_pools = await class_assignment_pools(
        db,
        period.academic_period_id,
        {
            class_section_id: contexts_by_class[class_section_id]
            for class_section_id in visible_class_ids
        },
    )
    existing = await _existing_assignments(db, visible_class_ids)
    groups: dict[UUID, list[CurriculumContext]] = defaultdict(list)
    for class_section_id in visible_class_ids:
        for context in contexts_by_class[class_section_id]:
            if curriculum_course_id is None or context.curriculum_course_id == curriculum_course_id:
                groups[context.curriculum_course_id].append(context)

    data: list[AssignmentPreviewGroup] = []
    ordered_groups = sorted(
        groups.items(),
        key=lambda item: (
            item[1][0].study_program_code,
            item[1][0].course_code,
            str(item[0]),
        ),
    )
    for context_id, rows in ordered_groups:
        ascending_classes = sorted(
            rows, key=lambda row: (row.section_code, str(row.class_section_id))
        )
        snake_classes = snake_order(ascending_classes)
        group_pool: list[AssignmentPoolItem] = []
        seen_users: set[str] = set()
        for row in snake_classes:
            for item in class_pools[row.class_section_id]:
                if item.user_id in seen_users:
                    continue
                seen_users.add(item.user_id)
                group_pool.append(item.model_copy(update={"position": len(group_pool) + 1}))
        classes: list[AssignmentPreviewClass] = []
        for snake_index, row in enumerate(snake_classes):
            pool = class_pools[row.class_section_id]
            by_user = {item.user_id: item for item in pool}
            assignment = existing.get(row.class_section_id)
            candidate = _pool_candidate(pool, snake_index)
            if assignment is not None and (
                assignment.source == "manual" or assignment.is_pinned
            ):
                pool_item = by_user.get(assignment.user_id)
                candidate = (
                    AssignmentCandidate.model_validate(pool_item.model_dump())
                    if pool_item is not None
                    else None
                )
            classes.append(
                AssignmentPreviewClass(
                    class_section_id=str(row.class_section_id),
                    section_code=row.section_code,
                    curriculum_course_id=str(context_id),
                    can_edit=scope is None or row.study_program_id == scope,
                    context_required=len(contexts_by_class[row.class_section_id]) > 1,
                    candidate=candidate,
                    existing_assignment=assignment,
                )
            )
        first = rows[0]
        involved_contexts = [
            context
            for row in rows
            for context in contexts_by_class[row.class_section_id]
        ]
        data.append(
            AssignmentPreviewGroup(
                curriculum_course_id=str(context_id),
                study_program_id=str(first.study_program_id),
                study_program_code=first.study_program_code,
                study_program_name=first.study_program_name,
                programs=_program_identities(involved_contexts),
                course_code=first.course_code,
                course_name=first.course_name,
                can_edit=scope is None or first.study_program_id == scope,
                pool=group_pool,
                classes=classes,
            )
        )
    return AssignmentPreviewResponse(
        data=data,
        meta=AssignmentPreviewMeta(
            academic_period_id=str(period.academic_period_id),
            input_revision=await _revision(db, period.academic_period_id, scope),
        ),
    )


async def _decision_contexts(
    db: AsyncSession,
    period_id: UUID,
    decisions: list[AssignmentDecisionRequest],
    scope: UUID | None,
) -> tuple[
    dict[UUID, CurriculumContext],
    dict[UUID, list[AssignmentPoolItem]],
    dict[UUID, set[UUID]],
] | JSONResponse:
    class_ids = {decision.class_section_id for decision in decisions}
    contexts_by_class = await load_curriculum_contexts(db, period_id, class_ids)
    if set(contexts_by_class) != class_ids:
        return _deny(404, "class_not_found", "Kelas MK tidak ditemukan.")
    existing = await _existing_assignments(db, class_ids)
    selected_by_class: dict[UUID, CurriculumContext] = {}
    for decision in decisions:
        contexts = contexts_by_class[decision.class_section_id]
        requested_context_id = decision.curriculum_course_id
        current = existing.get(decision.class_section_id)
        if requested_context_id is None and current and current.curriculum_course_id:
            requested_context_id = UUID(current.curriculum_course_id)
        if requested_context_id is None and len(contexts) > 1:
            return _deny(
                409,
                "curriculum_context_required",
                "Kelas MK memiliki beberapa konteks kurikulum atau prodi.",
            )
        selected = next(
            (
                context
                for context in contexts
                if requested_context_id is None
                or context.curriculum_course_id == requested_context_id
            ),
            None,
        )
        if selected is None:
            return _field_error(
                "curriculum_course_id",
                "Konteks kurikulum harus merupakan eligibility kelas MK.",
                "invalid_curriculum_context",
            )
        if scope is not None and selected.study_program_id != scope:
            return _deny(
                403, "forbidden", "Kelas MK berada di luar program studi Anda."
            )
        selected_by_class[decision.class_section_id] = selected

    class_pools = await class_assignment_pools(db, period_id, contexts_by_class)
    eligible = set(
        (
            await db.execute(
                select(User.user_id)
                .join(LecturerProfile, LecturerProfile.user_id == User.user_id)
                .where(
                    User.user_id.in_({decision.user_id for decision in decisions}),
                    User.role == "lecturer",
                    User.is_active.is_(True),
                )
            )
        ).scalars().all()
    )
    for decision in decisions:
        if decision.user_id not in eligible:
            return _field_error(
                "user_id",
                "Dosen harus memiliki akun dosen aktif.",
                "invalid_lecturer",
            )
        pool = class_pools[decision.class_section_id]
        if str(decision.user_id) not in {item.user_id for item in pool}:
            return error_response(
                _UNPROCESSABLE,
                "lecturer_not_in_pool",
                "Dosen harus aktif, berakun, dan menjadi anggota Tim Pengajar kelas MK.",
                detail="Dosen harus aktif, berakun, dan menjadi anggota Tim Pengajar kelas MK.",
                details=[
                    {
                        "field": "user_id",
                        "message": "Dosen harus aktif, berakun, dan menjadi anggota Tim Pengajar kelas MK.",
                        "code": "lecturer_not_in_pool",
                    }
                ],
            )
    program_ids_by_class = {
        class_section_id: {
            context.study_program_id for context in contexts
        }
        for class_section_id, contexts in contexts_by_class.items()
    }
    return selected_by_class, class_pools, program_ids_by_class


@router.put("/scheduling/assignments", response_model=AssignmentBulkResponse)
async def save_assignments(
    payload: AssignmentBulkRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = _scope(current_user)
    if isinstance(scope, JSONResponse):
        return scope
    class_ids = [decision.class_section_id for decision in payload.decisions]
    if len(class_ids) != len(set(class_ids)):
        return _field_error(
            "decisions", "Kelas MK hanya boleh muncul sekali.", "duplicate_class"
        )
    class_periods = (
        await db.execute(
            select(ClassSection.class_section_id, CourseOffering.academic_period_id)
            .select_from(ClassSection)
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
            .where(ClassSection.class_section_id.in_(class_ids))
        )
    ).all()
    periods = {row.class_section_id: row.academic_period_id for row in class_periods}
    for decision in payload.decisions:
        if decision.class_section_id not in periods:
            return _deny(404, "class_not_found", "Kelas MK tidak ditemukan.")
    period_ids = set(periods.values())
    if len(period_ids) != 1:
        return _field_error(
            "decisions", "Semua kelas harus berasal dari satu periode.", "period_mismatch"
        )
    period_id = next(iter(period_ids))
    resolved = await _decision_contexts(db, period_id, payload.decisions, scope)
    if isinstance(resolved, JSONResponse):
        return resolved
    contexts, pools, program_ids_by_class = resolved
    locked = await scheduling_input_lock(
        db,
        period_id,
        {
            program_id
            for ids in program_ids_by_class.values()
            for program_id in ids
        },
    )
    if locked is not None:
        code, message = locked
        return _deny(409, code, message)


    locked_classes = (
        await db.execute(
            select(ClassSection.class_section_id)
            .where(ClassSection.class_section_id.in_(class_ids))
            .order_by(ClassSection.class_section_id)
            .with_for_update()
        )
    ).scalars().all()
    existing = await _existing_assignments(db, set(locked_classes))
    changed: list[tuple[ClassInstructorAssignment, AssignmentResponse | None]] = []
    now = datetime.now(timezone.utc)
    try:
        for decision in sorted(payload.decisions, key=lambda item: str(item.class_section_id)):
            assignment = (
                await db.execute(
                    select(ClassInstructorAssignment)
                    .where(
                        ClassInstructorAssignment.class_section_id
                        == decision.class_section_id,
                        ClassInstructorAssignment.is_active.is_(True),
                    )
                    .with_for_update()
                )
            ).scalars().first()
            if assignment is None:
                assignment = ClassInstructorAssignment(
                    class_section_id=decision.class_section_id,
                    academic_period_id=period_id,
                    curriculum_course_id=contexts[
                        decision.class_section_id
                    ].curriculum_course_id,
                    user_id=decision.user_id,
                    source=decision.source,
                    is_pinned=decision.is_pinned,
                    is_active=True,
                    assigned_by=current_user.user_id,
                    assigned_at=now,
                )
                db.add(assignment)
                changed.append((assignment, None))
            else:
                before = existing[decision.class_section_id]
                if (
                    assignment.user_id == decision.user_id
                    and assignment.curriculum_course_id
                    == contexts[decision.class_section_id].curriculum_course_id
                    and assignment.source == decision.source
                    and assignment.is_pinned == decision.is_pinned
                    and assignment.assigned_by == current_user.user_id
                ):
                    continue
                assignment.user_id = decision.user_id
                assignment.curriculum_course_id = contexts[
                    decision.class_section_id
                ].curriculum_course_id
                assignment.source = decision.source
                assignment.is_pinned = decision.is_pinned
                assignment.assigned_by = current_user.user_id
                assignment.assigned_at = now
                changed.append((assignment, before))

        await db.flush()
        for assignment, before in changed:
            name = next(
                item.lecturer_name
                for item in pools[assignment.class_section_id]
                if item.user_id == str(assignment.user_id)
            )
            after = _assignment_response(assignment, name)
            await _record_assignment_change(db, current_user, "upsert", before, after)
        await _bump_revisions(
            db,
            period_id,
            {
                program_id
                for assignment, _ in changed
                for program_id in program_ids_by_class[assignment.class_section_id]
            },
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return _deny(
            409,
            "assignment_conflict",
            "Kelas MK sudah memiliki assignment pengajar aktif.",
        )
    saved = (
        await db.execute(
            select(ClassInstructorAssignment, User.full_name)
            .join(User, User.user_id == ClassInstructorAssignment.user_id)
            .where(
                ClassInstructorAssignment.class_section_id.in_(class_ids),
                ClassInstructorAssignment.is_active.is_(True),
            )
            .order_by(ClassInstructorAssignment.class_section_id)
        )
    ).all()
    return AssignmentBulkResponse(
        data=[_assignment_response(row[0], row[1]) for row in saved],
        meta=AssignmentBulkMeta(
            academic_period_id=str(period_id),
            input_revision=await _revision(db, period_id, scope),
        ),
    )


@router.delete(
    "/scheduling/assignments/{class_section_id}", response_model=AssignmentEnvelope
)
async def delete_assignment(
    class_section_id: UUID,
    curriculum_course_id: UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = _scope(current_user)
    if isinstance(scope, JSONResponse):
        return scope
    period_row = (
        await db.execute(
            select(CourseOffering.academic_period_id)
            .select_from(ClassSection)
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
            .where(ClassSection.class_section_id == class_section_id)
            .limit(1)
        )
    ).first()
    if period_row is None:
        return _deny(404, "class_not_found", "Kelas MK tidak ditemukan.")
    period_id = period_row.academic_period_id
    contexts_by_class = await load_curriculum_contexts(
        db, period_id, {class_section_id}
    )
    contexts = contexts_by_class.get(class_section_id, [])
    if not contexts:
        return _deny(404, "class_not_found", "Kelas MK tidak ditemukan.")
    existing = await _existing_assignments(db, {class_section_id})
    assignment_response = existing.get(class_section_id)
    if (
        assignment_response
        and assignment_response.curriculum_course_id
        and curriculum_course_id is not None
        and assignment_response.curriculum_course_id != str(curriculum_course_id)
    ):
        return _field_error(
            "curriculum_course_id",
            "Konteks kurikulum harus sama dengan assignment aktif.",
            "curriculum_context_mismatch",
        )
    requested_context_id = curriculum_course_id
    if assignment_response and assignment_response.curriculum_course_id:
        requested_context_id = UUID(assignment_response.curriculum_course_id)
    if requested_context_id is None and len(contexts) > 1:
        return _deny(
            409,
            "curriculum_context_required",
            "Kelas MK memiliki beberapa konteks kurikulum atau prodi.",
        )
    context = next(
        (
            item
            for item in contexts
            if requested_context_id is None
            or item.curriculum_course_id == requested_context_id
        ),
        None,
    )
    if context is None:
        return _field_error(
            "curriculum_course_id",
            "Konteks kurikulum harus merupakan eligibility kelas MK.",
            "invalid_curriculum_context",
        )
    if scope is not None and context.study_program_id != scope:
        return _deny(403, "forbidden", "Kelas MK berada di luar program studi Anda.")
    program_ids = {item.study_program_id for item in contexts}
    locked = await scheduling_input_lock(db, period_id, program_ids)
    if locked is not None:
        code, message = locked
        return _deny(409, code, message)
    assignment = (
        await db.execute(
            select(ClassInstructorAssignment)
            .where(
                ClassInstructorAssignment.class_section_id == class_section_id,
                ClassInstructorAssignment.is_active.is_(True),
            )
            .with_for_update()
        )
    ).scalars().first()
    if assignment is None:
        return AssignmentEnvelope(data=None)
    lecturer_name = (
        await db.execute(select(User.full_name).where(User.user_id == assignment.user_id))
    ).scalar_one()
    before = _assignment_response(assignment, lecturer_name)
    assignment.is_active = False
    await db.flush()
    after = _assignment_response(assignment, lecturer_name)
    try:
        await _record_assignment_change(db, current_user, "delete", before, after)
        await _bump_revisions(db, period_id, program_ids)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return _deny(409, "assignment_conflict", "Assignment pengajar tidak dapat dihapus.")
    return AssignmentEnvelope(data=None)
