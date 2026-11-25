"""Period-scoped teaching pools for class instructor assignments."""

from collections import defaultdict
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import CourseInstructorReference, LecturerProfile, User
from .scheduler import CurriculumContext

_POOL_ROLES = ("pjmk", "teaching_team")


class AssignmentPoolItem(BaseModel):
    user_id: str
    lecturer_name: str
    position: int
    is_pjmk: bool
    curriculum_course_id: str


async def class_assignment_pools(
    db: AsyncSession,
    period_id: UUID,
    contexts_by_class: dict[UUID, list[CurriculumContext]],
) -> dict[UUID, list[AssignmentPoolItem]]:
    """Resolve one deduplicated teaching pool per class, in curriculum order."""
    curriculum_course_ids = {
        context.curriculum_course_id
        for contexts in contexts_by_class.values()
        for context in contexts
    }
    by_course: dict[UUID, list[AssignmentPoolItem]] = defaultdict(list)
    if curriculum_course_ids:
        rows = (
            await db.execute(
                select(
                    CourseInstructorReference.curriculum_course_id,
                    CourseInstructorReference.instructor_role,
                    User.user_id,
                    User.full_name,
                )
                .join(User, User.user_id == CourseInstructorReference.user_id)
                .join(LecturerProfile, LecturerProfile.user_id == User.user_id)
                .where(
                    CourseInstructorReference.curriculum_course_id.in_(
                        curriculum_course_ids
                    ),
                    CourseInstructorReference.academic_period_id == period_id,
                    CourseInstructorReference.instructor_role.in_(_POOL_ROLES),
                    User.role == "lecturer",
                    User.is_active.is_(True),
                )
                .order_by(
                    CourseInstructorReference.curriculum_course_id,
                    CourseInstructorReference.instructor_role != "pjmk",
                    CourseInstructorReference.position.is_(None),
                    CourseInstructorReference.position,
                    CourseInstructorReference.instructor_reference_id,
                )
            )
        ).all()
        seen: dict[UUID, set[UUID]] = defaultdict(set)
        for row in rows:
            course_id = row.curriculum_course_id
            if row.user_id in seen[course_id]:
                continue
            seen[course_id].add(row.user_id)
            by_course[course_id].append(
                AssignmentPoolItem(
                    user_id=str(row.user_id),
                    lecturer_name=row.full_name,
                    position=len(by_course[course_id]) + 1,
                    is_pjmk=row.instructor_role == "pjmk",
                    curriculum_course_id=str(course_id),
                )
            )

    pools: dict[UUID, list[AssignmentPoolItem]] = {}
    for class_section_id, contexts in contexts_by_class.items():
        pool: list[AssignmentPoolItem] = []
        seen_users: set[str] = set()
        for context in contexts:
            for item in by_course.get(context.curriculum_course_id, []):
                if item.user_id in seen_users:
                    continue
                seen_users.add(item.user_id)
                pool.append(item.model_copy(update={"position": len(pool) + 1}))
        pools[class_section_id] = pool
    return pools
