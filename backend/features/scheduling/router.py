"""Router HTTP penjadwalan lintas program studi.

Setiap sub-router mempertahankan path aslinya; modul ini hanya menggabungkan
kelompok endpoint tanpa prefix agar komposisi di app.py tetap sama.
"""

from fastapi import APIRouter

from .routers import (
    scheduling_board,
    scheduling_edits,
    scheduling_generate,
    scheduling_instructors,
    scheduling_rooms,
)

router = APIRouter()

router.include_router(scheduling_board.router)
router.include_router(scheduling_edits.router)
router.include_router(scheduling_generate.router)
router.include_router(scheduling_instructors.router)
router.include_router(scheduling_rooms.router)
