"""Resolver kurikulum untuk koreksi data akademik mahasiswa oleh admin."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from catalog import cohort_curriculum_id
from models import DegreePlan, StudentCurriculumAssignment


async def resolve_cohort_curriculum_id(
    db: AsyncSession,
    *,
    study_program_id: uuid.UUID,
    admission_year: int,
) -> uuid.UUID | None:
    """Kurikulum yang berlaku untuk program studi dan tahun angkatan."""
    return await cohort_curriculum_id(db, study_program_id, admission_year)


async def current_curriculum_id(
    db: AsyncSession, user_id: uuid.UUID
) -> uuid.UUID | None:
    """Kurikulum pada penugasan aktif mahasiswa (sama seperti view kurikulum saat ini)."""
    return (
        await db.execute(
            select(StudentCurriculumAssignment.curriculum_id).where(
                StudentCurriculumAssignment.user_id == user_id,
                StudentCurriculumAssignment.is_current.is_(True),
            )
        )
    ).scalar_one_or_none()


async def active_plan_target_semester(
    db: AsyncSession, user_id: uuid.UUID
) -> int | None:
    """Target semester kelulusan pada rencana studi aktif, bila ada."""
    return (
        await db.execute(
            select(DegreePlan.target_graduation_semester)
            .where(
                DegreePlan.user_id == user_id,
                DegreePlan.status == "active",
                DegreePlan.target_graduation_semester.is_not(None),
            )
            .order_by(DegreePlan.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
