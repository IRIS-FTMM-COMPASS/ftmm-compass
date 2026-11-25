"""Deterministic lecturer-assignment preview and scoped persistence."""

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from audit import record_admin_action
from models import (
    ClassInstructorAssignment,
    ClassSection,
    CourseOffering,
    CourseOfferingEligibility,
    Curriculum,
    CurriculumCourse,
    LecturerProfile,
    OfferingComponent,
    User,
)
from scheduling_assignment_rules import snake_candidate_index, snake_order
from ..assignment_pool import AssignmentPoolItem, class_assignment_pools
from ..scheduler import (
    CurriculumContext,
    bump_input_revisions,
    current_input_revision,
    load_curriculum_contexts,
    scheduling_input_lock,
)
from .errors import ServiceError

_UNPROCESSABLE = 422


@dataclass(frozen=True)
class AssignmentDecision:
    class_section_id: UUID
    user_id: UUID
    source: Literal["auto", "manual"]
    is_pinned: bool
    curriculum_course_id: UUID | None = None


def _deny(status_code: int, code: str, message: str) -> ServiceError:
    return ServiceError(status_code, code, message)


def _field_error(field: str, message: str, code: str) -> ServiceError:
    return ServiceError(
        _UNPROCESSABLE,
        code,
        message,
        details=[{"field": field, "message": message, "code": code}],
    )


def assignment_record(
    assignment: ClassInstructorAssignment, lecturer_name: str | None
) -> dict[str, Any]:
    return {
        "assignment_id": str(assignment.assignment_id),
        "class_section_id": str(assignment.class_section_id),
        "academic_period_id": str(assignment.academic_period_id),
        "curriculum_course_id": (
            str(assignment.curriculum_course_id)
            if assignment.curriculum_course_id
            else None
        ),
        "user_id": str(assignment.user_id),
        "lecturer_name": lecturer_name or "Akun tidak tersedia",
        "source": assignment.source,
        "is_pinned": assignment.is_pinned,
        "is_active": assignment.is_active,
        "assigned_by": str(assignment.assigned_by),
        "assigned_at": assignment.assigned_at.isoformat(),
    }


async def _record_change(
    db: AsyncSession,
    actor: User,
    action: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> None:
    context = after or before
    assert context is not None
    snapshots = {
        key: json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        if value is not None
        else None
        for key, value in (("old", before), ("new", after))
    }
    await record_admin_action(
        db,
        actor=actor,
        target=actor,
        action=f"class_instructor_assignment_{action}",
        reason=(
            f"class_section_id={context['class_section_id']} "
            f"academic_period_id={context['academic_period_id']}"
        ),
        field_name=context["class_section_id"],
        old_value=snapshots["old"],
        new_value=snapshots["new"],
    )


def _program_identities(
    contexts: list[CurriculumContext],
) -> list[dict[str, Any]]:
    programs: dict[UUID, dict[str, Any]] = {}
    for context in contexts:
        programs.setdefault(
            context.study_program_id,
            {
                "study_program_id": str(context.study_program_id),
                "study_program_code": context.study_program_code,
                "study_program_name": context.study_program_name,
            },
        )
    return list(programs.values())


async def existing_assignments(
    db: AsyncSession, class_ids: set[UUID]
) -> dict[UUID, dict[str, Any]]:
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
        assignment.class_section_id: assignment_record(assignment, lecturer_name)
        for assignment, lecturer_name in rows
    }


async def build_preview(
    db: AsyncSession,
    period_id: UUID,
    scope: UUID | None,
    curriculum_course_id: UUID | None,
) -> dict[str, Any]:
    contexts_by_class = await load_curriculum_contexts(db, period_id)
    visible_class_ids = {
        class_section_id
        for class_section_id, contexts in contexts_by_class.items()
        if scope is None
        or any(context.study_program_id == scope for context in contexts)
    }
    class_pools = await class_assignment_pools(
        db,
        period_id,
        {
            class_section_id: contexts_by_class[class_section_id]
            for class_section_id in visible_class_ids
        },
    )
    existing = await existing_assignments(db, visible_class_ids)
    groups: dict[UUID, list[CurriculumContext]] = defaultdict(list)
    for class_section_id in visible_class_ids:
        for context in contexts_by_class[class_section_id]:
            if curriculum_course_id is None or context.curriculum_course_id == curriculum_course_id:
                groups[context.curriculum_course_id].append(context)

    data: list[dict[str, Any]] = []
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
        classes: list[dict[str, Any]] = []
        for snake_index, row in enumerate(snake_classes):
            pool = class_pools[row.class_section_id]
            by_user = {item.user_id: item for item in pool}
            assignment = existing.get(row.class_section_id)
            pool_index = snake_candidate_index(len(pool), snake_index)
            candidate = pool[pool_index].model_dump() if pool_index is not None else None
            if assignment is not None and (
                assignment["source"] == "manual" or assignment["is_pinned"]
            ):
                pool_item = by_user.get(assignment["user_id"])
                candidate = pool_item.model_dump() if pool_item is not None else None
            classes.append(
                {
                    "class_section_id": str(row.class_section_id),
                    "section_code": row.section_code,
                    "curriculum_course_id": str(context_id),
                    "can_edit": scope is None or row.study_program_id == scope,
                    "context_required": len(contexts_by_class[row.class_section_id]) > 1,
                    "candidate": candidate,
                    "existing_assignment": assignment,
                }
            )
        first = rows[0]
        involved_contexts = [
            context
            for row in rows
            for context in contexts_by_class[row.class_section_id]
        ]
        data.append(
            {
                "curriculum_course_id": str(context_id),
                "study_program_id": str(first.study_program_id),
                "study_program_code": first.study_program_code,
                "study_program_name": first.study_program_name,
                "programs": _program_identities(involved_contexts),
                "course_code": first.course_code,
                "course_name": first.course_name,
                "can_edit": scope is None or first.study_program_id == scope,
                "pool": [item.model_dump() for item in group_pool],
                "classes": classes,
            }
        )
    return {
        "data": data,
        "meta": {
            "academic_period_id": str(period_id),
            "input_revision": await current_input_revision(db, period_id, scope),
        },
    }


async def _decision_contexts(
    db: AsyncSession,
    period_id: UUID,
    decisions: list[AssignmentDecision],
    scope: UUID | None,
) -> tuple[
    dict[UUID, CurriculumContext],
    dict[UUID, list[AssignmentPoolItem]],
    dict[UUID, set[UUID]],
] | ServiceError:
    class_ids = {decision.class_section_id for decision in decisions}
    contexts_by_class = await load_curriculum_contexts(db, period_id, class_ids)
    if set(contexts_by_class) != class_ids:
        return _deny(404, "class_not_found", "Kelas MK tidak ditemukan.")
    existing = await existing_assignments(db, class_ids)
    selected_by_class: dict[UUID, CurriculumContext] = {}
    for decision in decisions:
        contexts = contexts_by_class[decision.class_section_id]
        requested_context_id = decision.curriculum_course_id
        current = existing.get(decision.class_section_id)
        if requested_context_id is None and current and current["curriculum_course_id"]:
            requested_context_id = UUID(current["curriculum_course_id"])
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
            message = "Dosen harus aktif, berakun, dan menjadi anggota Tim Pengajar kelas MK."
            return ServiceError(
                _UNPROCESSABLE,
                "lecturer_not_in_pool",
                message,
                details=[{"field": "user_id", "message": message, "code": "lecturer_not_in_pool"}],
            )
    program_ids_by_class = {
        class_section_id: {
            context.study_program_id for context in contexts
        }
        for class_section_id, contexts in contexts_by_class.items()
    }
    return selected_by_class, class_pools, program_ids_by_class


async def save_assignments(
    db: AsyncSession,
    decisions: list[AssignmentDecision],
    scope: UUID | None,
    actor: User,
) -> dict[str, Any] | ServiceError:
    class_ids = [decision.class_section_id for decision in decisions]
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
    for decision in decisions:
        if decision.class_section_id not in periods:
            return _deny(404, "class_not_found", "Kelas MK tidak ditemukan.")
    period_ids = set(periods.values())
    if len(period_ids) != 1:
        return _field_error(
            "decisions", "Semua kelas harus berasal dari satu periode.", "period_mismatch"
        )
    period_id = next(iter(period_ids))
    resolved = await _decision_contexts(db, period_id, decisions, scope)
    if isinstance(resolved, ServiceError):
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
    existing = await existing_assignments(db, set(locked_classes))
    changed: list[tuple[ClassInstructorAssignment, dict[str, Any] | None]] = []
    now = datetime.now(timezone.utc)
    try:
        for decision in sorted(decisions, key=lambda item: str(item.class_section_id)):
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
                    assigned_by=actor.user_id,
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
                    and assignment.assigned_by == actor.user_id
                ):
                    continue
                assignment.user_id = decision.user_id
                assignment.curriculum_course_id = contexts[
                    decision.class_section_id
                ].curriculum_course_id
                assignment.source = decision.source
                assignment.is_pinned = decision.is_pinned
                assignment.assigned_by = actor.user_id
                assignment.assigned_at = now
                changed.append((assignment, before))

        await db.flush()
        for assignment, before in changed:
            name = next(
                item.lecturer_name
                for item in pools[assignment.class_section_id]
                if item.user_id == str(assignment.user_id)
            )
            after = assignment_record(assignment, name)
            await _record_change(db, actor, "upsert", before, after)
        await bump_input_revisions(
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
    return {
        "data": [assignment_record(row[0], row[1]) for row in saved],
        "meta": {
            "academic_period_id": str(period_id),
            "input_revision": await current_input_revision(db, period_id, scope),
        },
    }


async def delete_assignment(
    db: AsyncSession,
    class_section_id: UUID,
    curriculum_course_id: UUID | None,
    scope: UUID | None,
    actor: User,
) -> ServiceError | None:
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
    existing = await existing_assignments(db, {class_section_id})
    assignment_response = existing.get(class_section_id)
    if (
        assignment_response
        and assignment_response["curriculum_course_id"]
        and curriculum_course_id is not None
        and assignment_response["curriculum_course_id"] != str(curriculum_course_id)
    ):
        return _field_error(
            "curriculum_course_id",
            "Konteks kurikulum harus sama dengan assignment aktif.",
            "curriculum_context_mismatch",
        )
    requested_context_id = curriculum_course_id
    if assignment_response and assignment_response["curriculum_course_id"]:
        requested_context_id = UUID(assignment_response["curriculum_course_id"])
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
        return None
    lecturer_name = (
        await db.execute(select(User.full_name).where(User.user_id == assignment.user_id))
    ).scalar_one()
    before = assignment_record(assignment, lecturer_name)
    assignment.is_active = False
    await db.flush()
    after = assignment_record(assignment, lecturer_name)
    try:
        await _record_change(db, actor, "delete", before, after)
        await bump_input_revisions(db, period_id, program_ids)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return _deny(409, "assignment_conflict", "Assignment pengajar tidak dapat dihapus.")
    return None


async def _class_context(
    db: AsyncSession,
    class_section_id: UUID,
    scope: UUID | None,
) -> tuple[UUID, UUID | None] | ServiceError:
    rows = (
        await db.execute(
            select(
                CourseOffering.academic_period_id,
                Curriculum.study_program_id,
                CurriculumCourse.curriculum_course_id,
            )
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
            .join(
                CourseOfferingEligibility,
                CourseOfferingEligibility.course_offering_id
                == CourseOffering.course_offering_id,
            )
            .join(
                CurriculumCourse,
                CurriculumCourse.curriculum_course_id
                == CourseOfferingEligibility.curriculum_course_id,
            )
            .join(Curriculum, Curriculum.curriculum_id == CurriculumCourse.curriculum_id)
            .where(ClassSection.class_section_id == class_section_id)
        )
    ).all()
    if not rows:
        return _deny(404, "class_not_found", "Kelas MK tidak ditemukan.")
    program_ids = {row.study_program_id for row in rows}
    curriculum_ids = {row.curriculum_course_id for row in rows}
    if len(program_ids) > 1 or len(curriculum_ids) > 1:
        return _deny(
            409,
            "curriculum_context_required",
            "Kelas MK memiliki beberapa konteks kurikulum atau prodi.",
        )
    program_id = rows[0].study_program_id
    if scope is not None and program_id != scope:
        return _deny(403, "forbidden", "Kelas MK berada di luar program studi Anda.")
    return rows[0].academic_period_id, program_id


async def get_class_assignment(
    db: AsyncSession, class_section_id: UUID, scope: UUID | None
) -> dict[str, Any] | ServiceError | None:
    context = await _class_context(db, class_section_id, scope)
    if isinstance(context, ServiceError):
        return context
    row = (
        await db.execute(
            select(ClassInstructorAssignment, User.full_name)
            .join(User, User.user_id == ClassInstructorAssignment.user_id)
            .where(
                ClassInstructorAssignment.class_section_id == class_section_id,
                ClassInstructorAssignment.is_active.is_(True),
            )
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    return assignment_record(row[0], row[1])


async def upsert_class_assignment(
    db: AsyncSession,
    class_section_id: UUID,
    academic_period_id: UUID,
    user_id: UUID,
    source: Literal["auto", "manual"],
    is_pinned: bool,
    scope: UUID | None,
    actor: User,
) -> dict[str, Any] | ServiceError:
    context = await _class_context(db, class_section_id, scope)
    if isinstance(context, ServiceError):
        return context
    class_period_id, program_id = context
    if academic_period_id != class_period_id:
        return _field_error(
            "academic_period_id",
            "Periode akademik tidak sesuai dengan periode kelas MK.",
            "period_mismatch",
        )
    locked = await scheduling_input_lock(
        db,
        class_period_id,
        {program_id} if program_id is not None else None,
    )
    if locked is not None:
        code, message = locked
        return _deny(409, code, message)

    lecturer = (
        await db.execute(
            select(User)
            .join(LecturerProfile, LecturerProfile.user_id == User.user_id)
            .where(
                User.user_id == user_id,
                User.role == "lecturer",
                User.is_active.is_(True),
            )
        )
    ).scalars().first()
    if lecturer is None:
        return _field_error(
            "user_id",
            "Dosen harus memiliki akun dosen aktif.",
            "invalid_lecturer",
        )

    contexts = await load_curriculum_contexts(
        db, class_period_id, {class_section_id}
    )
    class_pool = await class_assignment_pools(db, class_period_id, contexts)
    if str(user_id) not in {
        item.user_id for item in class_pool.get(class_section_id, [])
    }:
        message = "Dosen harus aktif, berakun, dan menjadi anggota Tim Pengajar kelas MK."
        return ServiceError(
            _UNPROCESSABLE,
            "lecturer_not_in_pool",
            message,
            details=[{"field": "user_id", "message": message, "code": "lecturer_not_in_pool"}],
        )

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
    changed = False
    if assignment is None:
        assignment = ClassInstructorAssignment(
            class_section_id=class_section_id,
            academic_period_id=class_period_id,
            user_id=user_id,
            source=source,
            is_pinned=is_pinned,
            is_active=True,
            assigned_by=actor.user_id,
        )
        db.add(assignment)
        changed = True
    elif (
        assignment.user_id != user_id
        or assignment.source != source
        or assignment.is_pinned != is_pinned
        or assignment.assigned_by != actor.user_id
    ):
        assignment.user_id = user_id
        assignment.source = source
        assignment.is_pinned = is_pinned
        assignment.assigned_by = actor.user_id
        assignment.assigned_at = datetime.now(timezone.utc)
        changed = True

    if changed:
        await bump_input_revisions(
            db,
            class_period_id,
            {program_id} if program_id is not None else None,
        )

    try:
        await db.flush()
        await db.refresh(assignment)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return _deny(
            409,
            "assignment_conflict",
            "Kelas MK sudah memiliki assignment pengajar aktif.",
        )
    return assignment_record(assignment, lecturer.full_name)
