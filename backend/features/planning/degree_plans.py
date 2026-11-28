"""Router HTTP. Setiap modul didaftarkan dua kali oleh app.py (v1 dan legacy)."""

import uuid

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user
from database import get_db
from models import Curriculum, StudyProgram, User
from catalog import get_courses_for_curriculum, normalize_prodi
from prodi_access import resolve_catalog_prodi
from plan_storage import (
    PLAN_LIMIT,
    AssignmentNotCurrent,
    CurriculumMismatch,
    DuplicateCourse,
    DuplicatePlanName,
    NoCurriculumAssignment,
    ParityMismatch,
    PlanLimitReached,
    PlanValidationFailed,
    UnknownCourse,
    create_plan,
    delete_plan,
    ensure_assignment,
    get_plan,
    list_plans,
    replace_items,
    to_response,
    update_plan,
)
from schemas import (
    DegreePlanCatalogResponse,
    DegreePlanCreateRequest,
    DegreePlanItemsRequest,
    DegreePlanListResponse,
    DegreePlanResponse,
    DegreePlanUpdateRequest,
)

router = APIRouter()

ITEM_ERRORS = (
    UnknownCourse,
    CurriculumMismatch,
    ParityMismatch,
    DuplicateCourse,
    PlanValidationFailed,
)


def _fail(
    status_code: int,
    code: str,
    message: str,
    details: list[dict] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "detail": message,
            "error": {"code": code, "message": message, "details": details or []},
        },
    )


def _item_error(exc: Exception) -> JSONResponse:
    if isinstance(exc, NoCurriculumAssignment):
        return _fail(
            422,
            "no_curriculum_assignment",
            "Profil prodi mahasiswa belum terdaftar pada kurikulum mana pun",
        )
    if isinstance(exc, UnknownCourse):
        message = f"Mata kuliah '{exc.code}' tidak ditemukan"
        code = "unknown_course"
    elif isinstance(exc, CurriculumMismatch):
        message = f"Mata kuliah '{exc.code}' bukan bagian kurikulum mahasiswa"
        code = "curriculum_mismatch"
    elif isinstance(exc, ParityMismatch):
        message = (
            f"Mata kuliah '{exc.code}' tidak sesuai paritas semester {exc.semester}"
        )
        code = "parity_mismatch"
    elif isinstance(exc, PlanValidationFailed):
        return _fail(
            422,
            "plan_validation_failed",
            "Rencana studi tidak lolos validasi.",
            [
                {
                    "field": "items",
                    "code": "plan_validation_failed",
                    "message": error,
                }
                for error in exc.errors
            ],
        )
    else:
        assert isinstance(exc, DuplicateCourse)
        message = f"Mata kuliah '{exc.code}' dikirim lebih dari sekali"
        code = "duplicate_course"
    return _fail(
        422,
        code,
        message,
        [{"field": "items", "code": code, "message": exc.code}],
    )


def _parse_id(raw: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError:
        return uuid.UUID(int=0)


@router.get("/degree-plans", response_model=DegreePlanListResponse)
async def list_degree_plans(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plans = await list_plans(db, current_user)
    return DegreePlanListResponse(
        data=[to_response(plan) for plan in plans],
        meta={"total": len(plans), "limit": PLAN_LIMIT},
    )


@router.post(
    "/degree-plans",
    response_model=DegreePlanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_degree_plan(
    payload: DegreePlanCreateRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        plan = await create_plan(db, current_user, payload)
    except DuplicatePlanName as exc:
        return _fail(
            409,
            "duplicate_plan_name",
            f"Nama skenario '{exc.name}' sudah dipakai",
        )
    except PlanLimitReached:
        return _fail(
            422,
            "plan_limit_reached",
            f"Maksimal {PLAN_LIMIT} skenario per mahasiswa",
        )
    except ITEM_ERRORS as exc:
        return _item_error(exc)

    response.headers["Location"] = f"/api/v1/degree-plans/{plan.degree_plan_id}"
    return to_response(plan)


@router.get("/degree-plans/catalog", response_model=DegreePlanCatalogResponse)
async def get_degree_plan_catalog(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        assignment = await ensure_assignment(db, current_user)
    except NoCurriculumAssignment:
        return _item_error(NoCurriculumAssignment())

    scoped = resolve_catalog_prodi(current_user)
    if isinstance(scoped, JSONResponse):
        return scoped

    scoped_prodi = normalize_prodi(scoped) if scoped is not None else None
    if scoped is not None:
        curriculum = await db.get(Curriculum, assignment.curriculum_id)
        program = (
            await db.get(StudyProgram, curriculum.study_program_id)
            if curriculum is not None
            else None
        )
        if program is None or normalize_prodi(program.program_name) != scoped_prodi:
            return _fail(
                status.HTTP_403_FORBIDDEN,
                "akses_prodi_ditolak",
                "Katalog yang diminta tidak sesuai dengan prodi akun Anda.",
            )

    courses = await get_courses_for_curriculum(db, assignment.curriculum_id)
    if scoped is not None:
        courses = [
            course for course in courses if normalize_prodi(course.program) == scoped_prodi
        ]
    return DegreePlanCatalogResponse(data=courses)


@router.get("/degree-plans/{plan_id}", response_model=DegreePlanResponse)
async def get_degree_plan(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await get_plan(db, current_user.user_id, _parse_id(plan_id))
    if plan is None:
        return _fail(404, "not_found", "Skenario tidak ditemukan")
    return to_response(plan)


@router.put("/degree-plans/{plan_id}/items", response_model=DegreePlanResponse)
async def replace_degree_plan_items(
    plan_id: str,
    payload: DegreePlanItemsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await get_plan(db, current_user.user_id, _parse_id(plan_id))
    if plan is None:
        return _fail(404, "not_found", "Skenario tidak ditemukan")

    try:
        updated = await replace_items(db, current_user, plan, payload.items)
    except ITEM_ERRORS as exc:
        return _item_error(exc)

    return to_response(updated)


@router.patch("/degree-plans/{plan_id}", response_model=DegreePlanResponse)
async def update_degree_plan(
    plan_id: str,
    payload: DegreePlanUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await get_plan(db, current_user.user_id, _parse_id(plan_id))
    if plan is None:
        return _fail(404, "not_found", "Skenario tidak ditemukan")

    try:
        updated = await update_plan(
            db,
            current_user,
            plan,
            name=payload.name,
            status_value=payload.status,
        )
    except DuplicatePlanName as exc:
        return _fail(
            409,
            "duplicate_plan_name",
            f"Nama skenario '{exc.name}' sudah dipakai",
        )
    except AssignmentNotCurrent:
        return _fail(
            409,
            "assignment_not_current",
            "Kurikulum mahasiswa pada skenario ini bukan kurikulum aktif",
        )

    return to_response(updated)


@router.delete("/degree-plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_degree_plan(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await get_plan(db, current_user.user_id, _parse_id(plan_id))
    if plan is None:
        return _fail(404, "not_found", "Skenario tidak ditemukan")
    await delete_plan(db, plan)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
