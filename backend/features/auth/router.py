"""Router HTTP. Setiap modul didaftarkan dua kali oleh app.py (v1 dan legacy)."""

import sys
from functools import wraps
import secrets
import uuid

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
from sqlalchemy import and_, cast, func, inspect, or_, select, String, update
from settings import ACCESS_TOKEN_EXPIRE_SECONDS
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from schemas import (
    LoginRequest,
    LoginResponse,
    UserResponse,
    UserProfileUpdateRequest,
    UserStudentProfileResponse,
    NotificationItemResponse,
    NotificationListResponse,
    RegisterRequest,
    RegisterResponse,
    RecoverRequest,
    RecoverResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,
    AccountResponse,
    AccountListResponse,
    AccountUpdateRequest,
    AccountUpdateResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)
from database import get_db
from models import (
    User,
    StudentProfile as StudentProfileModel,
    LecturerProfile,
    StudyProgram,
    AcademicPeriod,
    Curriculum,
    StudentCurriculumAssignment,
    UserNotification,
)
from auth import (
    authenticate_user,
    bump_token_version,
    create_access_token,
    find_user_by_recovery_code,
    get_current_user,
    get_password_hash,
    get_token_version,
    new_recovery_code,
    save_recovery_code,
    verify_password,
)
from audit import record_admin_action
from api.errors import error_response
from rate_limit import limiter
from slowapi.errors import RateLimitExceeded


router = APIRouter()


def _retry_after_seconds(exc: RateLimitExceeded) -> int:
    try:
        limit = getattr(exc, "limit", None)
        item = getattr(limit, "limit", None)
        get_expiry = getattr(item, "get_expiry", None)
        if callable(get_expiry):
            return max(1, int(get_expiry()))
    except (TypeError, ValueError):
        pass
    return 60


def auth_rate_limit(rate: str):
    """Batas laju hanya untuk endpoint autentikasi yang diberi penanda."""

    def decorator(func):
        limited = limiter.limit(rate, override_defaults=False)(func)

        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await limited(*args, **kwargs)
            except RateLimitExceeded as exc:
                retry_after = _retry_after_seconds(exc)
                message = (
                    "Terlalu banyak permintaan autentikasi. "
                    f"Coba lagi dalam {retry_after} detik."
                )
                return error_response(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    "rate_limited",
                    message,
                    detail="Batas laju autentikasi terlampaui.",
                    retry_after=retry_after,
                    top_level={"retry_after": retry_after},
                    headers={"Retry-After": str(retry_after)},
                )

        return wrapper

    return decorator


def _field_error(field: str, message: str, code: str) -> JSONResponse:
    return error_response(
        getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
        "validation_error",
        "Data yang dikirim tidak valid.",
        detail="Data yang dikirim tidak valid.",
        details=[{"field": field, "message": message, "code": code}],
    )


def _derive_current_semester(admission_year: int, period) -> int:
    now = datetime.now()
    year = period.academic_year_start if period is not None else now.year
    term = period.term if period is not None else ("ganjil" if now.month < 8 else "genap")
    offset = 1 if str(term).lower() == "ganjil" else 2
    return max(1, min(14, (year - admission_year) * 2 + offset))


def _require_admin(current_user: User) -> None:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akses manajemen akun hanya tersedia untuk admin.",
        )


def _account_response(
    user: User, student_number: str | None = None
) -> AccountResponse:
    profile = None
    if "student_profile" not in inspect(user).unloaded:
        profile = user.student_profile
        if profile is not None and student_number is None:
            student_number = profile.student_number
    study_program = None
    if profile is not None and "study_program" not in inspect(profile).unloaded:
        program = profile.study_program
        if program is not None:
            study_program = program.program_name or program.program_code
    return AccountResponse(
        user_id=str(user.user_id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        status="active" if user.is_active else "inactive",
        student_number=student_number,
        study_program=study_program,
        admission_year=profile.admission_year if profile is not None else None,
        current_semester=profile.current_semester if profile is not None else None,
        needs_revalidation=getattr(user, "needs_revalidation", False),
        created_at=user.created_at.isoformat() if user.created_at else None,
    )


def _temporary_password() -> str:
    return f"Tmp{secrets.token_urlsafe(9)}!"


def _build_user_response(user: User) -> UserResponse:
    student_profile_data = None
    is_program_coordinator = False
    if user.student_profile:
        sp = user.student_profile
        student_profile_data = UserStudentProfileResponse(
            student_number=sp.student_number,
            study_program=sp.study_program.program_name if sp.study_program else None,
            program_code=sp.study_program.program_code if sp.study_program else None,
            admission_year=sp.admission_year,
            current_semester=sp.current_semester,
        )

    if user.role == "student":
        academic_id = user.student_profile.student_number if user.student_profile else None
        unit_name = (
            user.student_profile.study_program.program_name
            if (user.student_profile and user.student_profile.study_program)
            else None
        )
        permissions = ["view_catalog", "plan_courses", "vote_electives", "use_chatbot"]
    elif user.role == "lecturer":
        lecturer_profile = user.lecturer_profile
        academic_id = lecturer_profile.employee_number if lecturer_profile else None
        unit_name = (
            lecturer_profile.study_program.program_name
            if (lecturer_profile and lecturer_profile.study_program)
            else None
        )
        is_program_coordinator = (
            bool(lecturer_profile.is_program_coordinator) if lecturer_profile else False
        )
        permissions = ["view_catalog", "view_demand_analytics", "review_study_plans", "use_chatbot"]
    else:
        academic_id = None
        unit_name = None
        permissions = [
            "view_catalog",
            "view_demand_analytics",
            "manage_polling",
            "export_reports",
            "inspect_curricula",
            "use_chatbot",
        ]

    return UserResponse(
        user_id=str(user.user_id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        auth_provider="Kata sandi lokal",
        academic_identifier=academic_id,
        unit_name=unit_name,
        phone_number=user.phone_number,
        bio=user.bio,
        career_interests=user.career_interests or [],
        permissions=permissions,
        student_profile=student_profile_data,
        needs_revalidation=getattr(user, "needs_revalidation", False),
        is_program_coordinator=is_program_coordinator,
    )


@router.post("/auth/login", response_model=LoginResponse)
@auth_rate_limit("5/minute")
async def v1_login(
    request: Request,
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    user = await authenticate_user(db, payload.identifier, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="NIM/Email atau kata sandi tidak valid",
        )

    if not user.is_active:
        return error_response(
            status.HTTP_401_UNAUTHORIZED,
            "account_inactive",
            "Akun Anda dinonaktifkan oleh admin",
            detail="Akun Anda dinonaktifkan oleh admin",
        )

    version = await get_token_version(db, user.user_id)
    access_token = create_access_token(
        data={"sub": str(user.user_id), "role": user.role, "ver": version}
    )

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_SECONDS,
        user=_build_user_response(user),
    )


@router.post(
    "/auth/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED
)
@auth_rate_limit("3/minute")
async def v1_register(
    request: Request,
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    email = payload.email.strip().lower()
    if (
        email.count("@") != 1
        or not email.endswith("@ftmm.unair.ac.id")
        or not email.split("@")[0].strip()
    ):
        return _field_error(
            "email",
            "Email harus menggunakan domain @ftmm.unair.ac.id.",
            "invalid_email_domain",
        )

    if payload.admission_year < 2000 or payload.admission_year > datetime.now().year + 1:
        return _field_error(
            "admission_year",
            "Tahun angkatan di luar rentang yang didukung.",
            "invalid_admission_year",
        )

    student_number = payload.student_number.strip()
    if not student_number:
        return _field_error(
            "student_number", "NIM wajib diisi.", "invalid_student_number"
        )

    existing_email = (
        await db.execute(select(User).where(User.email == email))
    ).scalars().first()
    if existing_email is not None:
        return _field_error("email", "Email sudah terdaftar.", "duplicate_email")

    existing_nim = (
        await db.execute(
            select(StudentProfileModel).where(
                StudentProfileModel.student_number == student_number
            )
        )
    ).scalars().first()
    if existing_nim is not None:
        return _field_error(
            "student_number", "NIM sudah terdaftar.", "duplicate_student_number"
        )

    program_stmt = select(StudyProgram).where(StudyProgram.is_active.is_(True))
    if payload.study_program_code:
        program_stmt = program_stmt.where(
            StudyProgram.program_code
            == payload.study_program_code.strip().upper()
        )
    program = (
        await db.execute(program_stmt.order_by(StudyProgram.program_code))
    ).scalars().first()
    if program is None:
        return _field_error(
            "study_program_code",
            "Program studi aktif tidak ditemukan.",
            "unknown_study_program",
        )

    active_period = (
        await db.execute(
            select(AcademicPeriod)
            .where(AcademicPeriod.is_active.is_(True))
            .order_by(AcademicPeriod.academic_year_start.desc())
        )
    ).scalars().first()
    semester = _derive_current_semester(payload.admission_year, active_period)

    recovery_code = new_recovery_code()
    user = User(
        email=email,
        full_name=payload.full_name.strip(),
        password_hash=get_password_hash(payload.password),
        role="student",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await save_recovery_code(db, user.user_id, recovery_code)

    profile = StudentProfileModel(
        user_id=user.user_id,
        study_program_id=program.study_program_id,
        student_number=student_number,
        admission_year=payload.admission_year,
        current_semester=semester,
    )
    db.add(profile)
    user.student_profile = profile
    profile.study_program = program

    curriculum = (
        await db.execute(
            select(Curriculum)
            .where(
                Curriculum.study_program_id == program.study_program_id,
                Curriculum.is_active.is_(True),
            )
            .order_by(Curriculum.curriculum_year.desc())
        )
    ).scalars().first()
    if curriculum is not None:
        db.add(
            StudentCurriculumAssignment(
                user_id=user.user_id,
                curriculum_id=curriculum.curriculum_id,
                is_current=True,
                assignment_source="cohort_rule",
            )
        )

    access_token = create_access_token(
        data={"sub": str(user.user_id), "role": user.role, "ver": 0}
    )
    await db.commit()
    return RegisterResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_SECONDS,
        user=_build_user_response(user),
        recovery_code=recovery_code,
    )


@router.post("/auth/recover", response_model=RecoverResponse)
@auth_rate_limit("3/minute")
async def v1_recover(
    request: Request,
    payload: RecoverRequest,
    db: AsyncSession = Depends(get_db),
):
    code = payload.recovery_code.strip()
    user_id = await find_user_by_recovery_code(db, code)
    if user_id is None:
        return error_response(
            status.HTTP_400_BAD_REQUEST,
            "invalid_recovery_code",
            "Kode pemulihan tidak valid.",
            detail="Kode pemulihan tidak valid.",
        )

    user = (
        await db.execute(select(User).where(User.user_id == user_id))
    ).scalars().first()
    if user is None:
        return error_response(
            status.HTTP_400_BAD_REQUEST,
            "invalid_recovery_code",
            "Kode pemulihan tidak valid.",
            detail="Kode pemulihan tidak valid.",
        )

    user.password_hash = get_password_hash(payload.new_password)
    rotated_code = new_recovery_code()
    await save_recovery_code(db, user.user_id, rotated_code)
    await bump_token_version(db, user.user_id)
    await db.commit()
    return RecoverResponse(
        message="Kata sandi berhasil dipulihkan dan kode pemulihan diperbarui.",
        recovery_code=rotated_code,
    )


@router.post("/auth/change-password", response_model=ChangePasswordResponse)
async def v1_change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.password_hash or not verify_password(
        payload.current_password, current_user.password_hash
    ):
        return error_response(
            status.HTTP_400_BAD_REQUEST,
            "invalid_current_password",
            "Kata sandi saat ini tidak valid.",
            detail="Kata sandi saat ini tidak valid.",
        )

    current_user.password_hash = get_password_hash(payload.new_password)
    version = await bump_token_version(db, current_user.user_id)
    access_token = create_access_token(
        data={
            "sub": str(current_user.user_id),
            "role": current_user.role,
            "ver": version,
        }
    )
    await db.commit()
    return ChangePasswordResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_SECONDS,
        message="Kata sandi berhasil diubah. Gunakan token baru untuk sesi ini.",
    )


@router.get("/auth/me", response_model=UserResponse)
async def v1_me(current_user: User = Depends(get_current_user)):
    return _build_user_response(current_user)


@router.patch("/auth/me/profile", response_model=UserResponse)
async def v1_update_profile(
    payload: UserProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.phone_number is not None:
        current_user.phone_number = payload.phone_number.strip()
    if payload.bio is not None:
        current_user.bio = payload.bio.strip()
    if payload.career_interests is not None:
        current_user.career_interests = [
            ci.strip() for ci in payload.career_interests if ci and ci.strip()
        ]

    await db.commit()
    stmt = (
        select(User)
        .options(
            selectinload(User.student_profile).selectinload(StudentProfileModel.study_program),
            selectinload(User.lecturer_profile).selectinload(LecturerProfile.study_program),
        )
        .where(User.user_id == current_user.user_id)
    )
    res = await db.execute(stmt)
    refreshed_user = res.scalars().first() or current_user
    return _build_user_response(refreshed_user)


@router.get("/admin/accounts", response_model=AccountListResponse)
async def list_accounts(
    search: str = "",
    role: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(current_user)
    page = max(1, page)
    page_size = max(1, min(100, page_size))

    base = select(User).outerjoin(
        StudentProfileModel, User.user_id == StudentProfileModel.user_id
    )
    count_stmt = select(func.count()).select_from(User).outerjoin(
        StudentProfileModel, User.user_id == StudentProfileModel.user_id
    )

    if search.strip():
        term = f"%{search.strip()}%"
        condition = or_(
            User.email.ilike(term),
            User.full_name.ilike(term),
            StudentProfileModel.student_number.ilike(term),
        )
        base = base.where(condition)
        count_stmt = count_stmt.where(condition)
    if role and role.strip():
        base = base.where(User.role == role.strip().lower())
        count_stmt = count_stmt.where(User.role == role.strip().lower())
    if status_filter and status_filter.strip():
        is_active = status_filter.strip().lower() in ("active", "aktif", "true", "1")
        base = base.where(User.is_active.is_(is_active))
        count_stmt = count_stmt.where(User.is_active.is_(is_active))

    total = int((await db.execute(count_stmt)).scalar_one())
    users = (
        await db.execute(
            base.options(
                selectinload(User.student_profile).selectinload(
                    StudentProfileModel.study_program
                )
            )
            .order_by(User.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().unique().all()
    return AccountListResponse(
        data=[_account_response(user) for user in users],
        meta={
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        },
    )


@router.patch("/admin/accounts/{user_id}", response_model=AccountUpdateResponse)
async def update_account(
    user_id: uuid.UUID,
    payload: AccountUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(current_user)

    if payload.is_active is False and not (payload.reason or "").strip():
        reason_message = "Alasan wajib diisi saat menonaktifkan akun."
        return error_response(
            getattr(
                status,
                "HTTP_422_UNPROCESSABLE_CONTENT",
                422,
            ),
            "validation_error",
            reason_message,
            detail=reason_message,
            details=[
                {
                    "field": "reason",
                    "message": reason_message,
                    "code": "required_reason",
                }
            ],
        )
    user = (
        await db.execute(
            select(User)
            .options(
                selectinload(User.student_profile).selectinload(
                    StudentProfileModel.study_program
                )
            )
            .where(User.user_id == user_id)
        )
    ).scalars().first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Akun tidak ditemukan."
        )

    is_deactivation = not payload.is_active
    guard_message = None
    if is_deactivation and current_user.user_id == user.user_id:
        guard_message = "Anda tidak dapat menonaktifkan akun Anda sendiri."
    elif is_deactivation and user.is_active and user.role == "admin":
        other_active_admins = (
            await db.execute(
                select(func.count())
                .select_from(User)
                .where(
                    User.role == "admin",
                    User.is_active.is_(True),
                    User.user_id != user.user_id,
                )
            )
        ).scalar_one()
        if other_active_admins == 0:
            guard_message = "Admin aktif terakhir tidak dapat dinonaktifkan."
    if guard_message is not None:
        return error_response(
            status.HTTP_409_CONFLICT,
            "admin_guard",
            guard_message,
            detail=guard_message,
        )

    old_value = str(user.is_active).lower()
    await record_admin_action(
        db,
        actor=current_user,
        target=user,
        action="status_change",
        reason=payload.reason,
        field_name="is_active",
        old_value=old_value,
        new_value=str(payload.is_active).lower(),
    )
    user.is_active = payload.is_active
    await bump_token_version(db, user.user_id)
    await db.commit()
    return AccountUpdateResponse(data=_account_response(user))


@router.post(
    "/admin/accounts/{user_id}/reset-password",
    response_model=ResetPasswordResponse,
)
async def reset_account_password(
    user_id: uuid.UUID,
    payload: ResetPasswordRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(current_user)
    user = (
        await db.execute(select(User).where(User.user_id == user_id))
    ).scalars().first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Akun tidak ditemukan."
        )

    await record_admin_action(
        db,
        actor=current_user,
        target=user,
        action="password_reset",
        reason=payload.reason if payload is not None else None,
    )
    temporary_password = _temporary_password()
    user.password_hash = get_password_hash(temporary_password)
    await bump_token_version(db, user.user_id)
    await db.commit()
    return ResetPasswordResponse(
        message="Kata sandi sementara telah dibuat. Sesi lama akun ini dicabut.",
        temporary_password=temporary_password,
    )

def _format_relative_time(dt: datetime) -> str:
    now = datetime.now(dt.tzinfo or timezone.utc)
    diff = now - dt
    secs = int(diff.total_seconds())
    if secs < 60:
        return "Baru saja"
    if secs < 3600:
        return f"{secs // 60} menit lalu"
    if secs < 86400:
        return f"{secs // 3600} jam lalu"
    days = secs // 86400
    if days < 7:
        return f"{days} hari lalu"
    return dt.strftime("%d %b %Y")


def _visible_notification_filter(current_user: User):
    """Satu-satunya definisi notifikasi yang boleh dilihat dan diubah pengguna."""
    return or_(
        UserNotification.user_id == current_user.user_id,
        UserNotification.target_role == current_user.role,
        and_(UserNotification.user_id == None, UserNotification.target_role == None),
    )


@router.get("/notifications/me", response_model=NotificationListResponse)
async def get_my_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(UserNotification)
        .where(_visible_notification_filter(current_user))
        .order_by(UserNotification.created_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    unread_count = sum(1 for r in rows if not r.is_read)

    items = [
        NotificationItemResponse(
            id=str(r.notification_id),
            title=r.title,
            message=r.message,
            type=r.type if r.type in ("warning", "deadline", "info", "success") else "info",
            is_read=r.is_read,
            action_url=r.action_url,
            timestamp=_format_relative_time(r.created_at),
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]

    return NotificationListResponse(unread_count=unread_count, items=items)


@router.patch("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(UserNotification).where(
        cast(UserNotification.notification_id, String) == notification_id,
        _visible_notification_filter(current_user),
    )
    notif = (await db.execute(stmt)).scalars().first()
    if not notif:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notifikasi tidak ditemukan.",
        )
    notif.is_read = True
    await db.commit()
    return {"status": "success", "message": "Notifikasi ditandai sebagai telah dibaca."}


@router.post("/notifications/mark-all-read")
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        update(UserNotification)
        .where(_visible_notification_filter(current_user))
        .values(is_read=True)
    )
    await db.execute(stmt)
    await db.commit()
    return {"status": "success", "message": "Semua notifikasi telah ditandai dibaca."}
