"""Resolver kurikulum untuk koreksi data akademik mahasiswa oleh admin."""

import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from models import DegreePlan, StudentCurriculumAssignment


async def resolve_cohort_curriculum_id(
    db: AsyncSession,
    *,
    study_program_id: uuid.UUID,
    admission_year: int,
) -> uuid.UUID | None:
    """Kurikulum yang berlaku untuk program studi dan tahun angkatan."""
    value = (
        await db.execute(
            text(
                "SELECT ccr.curriculum_id FROM curriculum_cohort_rules ccr "
                "WHERE ccr.study_program_id = CAST(:program AS uuid) "
                "AND ccr.is_active "
                "AND :year >= ccr.admission_year_from "
                "AND (ccr.admission_year_to IS NULL OR :year <= ccr.admission_year_to) "
                "ORDER BY ccr.priority ASC, ccr.curriculum_id ASC "
                "LIMIT 1"
            ),
            {"program": str(study_program_id), "year": admission_year},
        )
    ).scalar_one_or_none()
    if value is not None:
        return uuid.UUID(str(value))
    # Seed data belum selalu mengisi curriculum_cohort_rules; pilih kurikulum
    # program yang paling dekat dengan tahun angkatan sebagai fallback.
    value = (
        await db.execute(
            text(
                "SELECT curriculum_id FROM curricula "
                "WHERE study_program_id = CAST(:program AS uuid) AND is_active "
                "ORDER BY CASE WHEN curriculum_year = :year THEN 0 ELSE 1 END, "
                "ABS(curriculum_year - :year) ASC, curriculum_year DESC "
                "LIMIT 1"
            ),
            {"program": str(study_program_id), "year": admission_year},
        )
    ).scalar_one_or_none()
    return uuid.UUID(str(value)) if value is not None else None


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
