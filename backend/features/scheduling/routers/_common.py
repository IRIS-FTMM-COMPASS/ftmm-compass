"""HTTP helpers shared by the scheduling preference routers."""

from collections.abc import Callable
from uuid import UUID

from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from models import AcademicPeriod
from scheduling_common import current_period_id
from ..services.errors import ServiceError


async def resolve_period(
    db: AsyncSession,
    requested_period_id: UUID | None,
    failure: Callable[[ServiceError], JSONResponse],
) -> AcademicPeriod | JSONResponse:
    period_id = requested_period_id or await current_period_id(db)
    if period_id is None:
        return failure(
            ServiceError(
                404,
                "period_not_found",
                "Periode akademik aktif tidak ditemukan.",
            )
        )
    period = await db.get(AcademicPeriod, period_id)
    if period is None:
        return failure(
            ServiceError(404, "period_not_found", "Periode akademik tidak ditemukan.")
        )
    return period
