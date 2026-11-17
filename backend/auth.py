import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models import StudentProfile, User

from settings import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM as ALGORITHM,
    JWT_SECRET_KEY as SECRET_KEY,
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)



async def get_token_version(db: AsyncSession, user_id) -> int:
    """Versi token berasal dari kolom users.token_version (tabel tanpa model ORM)."""
    result = await db.execute(
        text("SELECT token_version FROM users WHERE user_id = CAST(:uid AS uuid)"),
        {"uid": str(user_id)},
    )
    value = result.scalar_one_or_none()
    return int(value or 0)


async def bump_token_version(db: AsyncSession, user_id) -> int:
    await db.execute(
        text(
            "UPDATE users SET token_version = COALESCE(token_version, 0) + 1 "
            "WHERE user_id = CAST(:uid AS uuid)"
        ),
        {"uid": str(user_id)},
    )
    return await get_token_version(db, user_id)


def hash_recovery_code(code: str) -> str:
    return hashlib.sha256(code.strip().encode("utf-8")).hexdigest()


def new_recovery_code() -> str:
    raw = secrets.token_urlsafe(12).replace("-", "").replace("_", "").upper()[:12]
    return f"FTMM-{raw[:4]}-{raw[4:8]}-{raw[8:12]}"


async def save_recovery_code(db: AsyncSession, user_id, code: str) -> None:
    await db.execute(
        text(
            "UPDATE users SET recovery_code_hash = :code_hash "
            "WHERE user_id = CAST(:uid AS uuid)"
        ),
        {"code_hash": hash_recovery_code(code), "uid": str(user_id)},
    )


async def find_user_by_recovery_code(db: AsyncSession, code: str):
    result = await db.execute(
        text(
            "SELECT user_id FROM users "
            "WHERE recovery_code_hash = :code_hash"
        ),
        {"code_hash": hash_recovery_code(code)},
    )
    return result.scalar_one_or_none()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def authenticate_user(
    db: AsyncSession, identifier: str, password: str
) -> Optional[User]:
    clean_identifier = identifier.strip()
    stmt = (
        select(User)
        .outerjoin(StudentProfile, User.user_id == StudentProfile.user_id)
        .options(
            selectinload(User.student_profile).selectinload(StudentProfile.study_program)
        )
        .where(
            or_(
                User.email == clean_identifier,
                StudentProfile.student_number == clean_identifier,
            )
        )
    )
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user:
        return None
    if not user.password_hash or not verify_password(password, user.password_hash):
        return None
    if not user.is_active:
        return None
    return user


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Kredensial autentikasi tidak valid atau telah kedaluwarsa",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        user_id = uuid.UUID(user_id_str)
    except (jwt.PyJWTError, ValueError):
        raise credentials_exception

    stmt = (
        select(User)
        .options(
            selectinload(User.student_profile).selectinload(StudentProfile.study_program)
        )
        .where(User.user_id == user_id)
    )
    result = await db.execute(stmt)
    user = result.scalars().first()

    if user is None or not user.is_active:
        raise credentials_exception

    try:
        claimed_version = int(payload.get("ver", 0))
    except (TypeError, ValueError):
        raise credentials_exception
    if claimed_version != await get_token_version(db, user.user_id):
        raise credentials_exception
    return user
