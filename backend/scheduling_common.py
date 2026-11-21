"""Aturan bersama untuk penjadwalan lintas program studi.

Blok jadwal memakai satu jam penuh per SKS (ADR 0004). Modul ini sengaja
tidak mengimpor modul router/endpoint lain agar dapat dipakai solver, papan
jadwal, dan admin tanpa siklus impor.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import AcademicPeriod, StudyProgram

DAY_NAMES = {1: "Senin", 2: "Selasa", 3: "Rabu", 4: "Kamis", 5: "Jumat"}
START_HOUR_MIN = 7
END_HOUR_MAX = 17

_STATUS_LABELS = {
    "draft": "Jadwal masih dalam proses",
    "in_progress": "Jadwal masih dalam proses",
    "final": "Jadwal final",
}


def hour_end(start_hour: int, credits: int) -> int:
    """Akhir blok dalam jam penuh; satu SKS memesan satu jam (ADR 0004)."""
    return start_hour + credits


def blocks_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    """Dua blok bertabrakan bila rentangnya beririsan, bukan hanya bersentuhan."""
    return a_start < b_end and b_start < a_end


def is_valid_block(start_hour: int, credits: int) -> bool:
    """Blok sah bila SKS positif dan seluruh jamnya berada dalam rentang kuliah."""
    return (
        isinstance(start_hour, int)
        and isinstance(credits, int)
        and credits > 0
        and start_hour >= START_HOUR_MIN
        and hour_end(start_hour, credits) <= END_HOUR_MAX
    )


def status_label(state: str) -> str:
    """Label status jadwal untuk PJ Prodi dan PJ MK."""
    return _STATUS_LABELS.get(state, "Jadwal masih dalam proses")


async def current_period_id(db: AsyncSession) -> UUID | None:
    """Periode akademik aktif yang menjadi konteks Papan Jadwal Bersama."""
    result = await db.execute(
        select(AcademicPeriod.academic_period_id)
        .where(AcademicPeriod.is_active.is_(True))
        .order_by(
            AcademicPeriod.academic_year_start.desc(),
            AcademicPeriod.created_at.desc(),
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def all_study_program_ids(db: AsyncSession) -> list[UUID]:
    """Seluruh prodi aktif yang diwakili pada Papan Jadwal Bersama."""
    result = await db.execute(
        select(StudyProgram.study_program_id)
        .where(StudyProgram.is_active.is_(True))
        .order_by(StudyProgram.program_code)
    )
    return list(result.scalars().all())
