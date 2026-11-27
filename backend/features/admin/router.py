"""Gabungan router admin: akun, jejak wewenang, dan MK PJ prodi."""

from fastapi import APIRouter

from .accounts import router as accounts_router
from .pj_courses import router as pj_courses_router
from .traces import router as traces_router

router = APIRouter()

router.include_router(accounts_router)
router.include_router(pj_courses_router)
router.include_router(traces_router)
