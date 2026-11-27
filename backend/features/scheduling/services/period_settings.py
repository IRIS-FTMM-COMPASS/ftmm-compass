"""Period-scoped preference deadline settings."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import AcademicPeriod, SchedulePeriodSettings, StudyProgram
from ..scheduler import scheduling_input_lock
from .errors import ServiceError


async def get_settings(
    db: AsyncSession,
    period_id: UUID,
    scope: UUID | None,
    program: StudyProgram | None,
) -> dict[str, Any]:
    settings = (
        await db.execute(
            select(SchedulePeriodSettings).where(
                SchedulePeriodSettings.academic_period_id == period_id,
                (
                    SchedulePeriodSettings.study_program_id.is_(None)
                    if scope is None
                    else SchedulePeriodSettings.study_program_id == scope
                ),
            )
        )
    ).scalar_one_or_none()
    return _settings_response(period_id, scope, program, settings)


async def put_settings(
    db: AsyncSession,
    period_id: UUID,
    scope: UUID | None,
    program: StudyProgram | None,
    preference_deadline: datetime | None,
) -> dict[str, Any] | ServiceError:
    locked = await scheduling_input_lock(
        db, period_id, {scope} if scope is not None else None
    )
    if locked is not None:
        code, message = locked
        return ServiceError(409, code, message)

    await db.execute(
        select(AcademicPeriod.academic_period_id)
        .where(AcademicPeriod.academic_period_id == period_id)
        .with_for_update()
    )
    settings = (
        await db.execute(
            select(SchedulePeriodSettings)
            .where(
                SchedulePeriodSettings.academic_period_id == period_id,
                (
                    SchedulePeriodSettings.study_program_id.is_(None)
                    if scope is None
                    else SchedulePeriodSettings.study_program_id == scope
                ),
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if settings is None:
        settings = SchedulePeriodSettings(
            academic_period_id=period_id,
            study_program_id=scope,
            preference_deadline=preference_deadline,
        )
        db.add(settings)
    else:
        settings.preference_deadline = preference_deadline
    await db.flush()
    await db.refresh(settings)
    response = _settings_response(period_id, scope, program, settings)
    await db.commit()
    return response


def _settings_response(
    period_id: UUID,
    study_program_id: UUID | None,
    study_program: StudyProgram | None,
    settings: SchedulePeriodSettings | None,
) -> dict[str, Any]:
    return {
        "academic_period_id": str(period_id),
        "study_program_id": str(study_program_id) if study_program_id else None,
        "study_program_code": study_program.program_code if study_program else None,
        "study_program_name": study_program.program_name if study_program else None,
        "preference_deadline": settings.preference_deadline if settings else None,
        "input_revision": settings.input_revision if settings else 0,
        "finalized_at": settings.finalized_at if settings else None,
        "updated_at": settings.updated_at if settings else None,
    }
