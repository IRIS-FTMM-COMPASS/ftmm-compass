"""Router jejak wewenang admin."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.errors import error_response
from auth import get_current_user
from database import get_db
from models import User
from schemas import AdminAuthorityTraceResponse

router = APIRouter()


@router.get("/admin/authority-traces")
async def list_authority_traces(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "admin":
        return error_response(
            status.HTTP_403_FORBIDDEN,
            "forbidden",
            "Akses jejak wewenang admin hanya tersedia untuk admin.",
        )

    total = (
        await db.execute(text("SELECT COUNT(*) FROM admin_authority_traces"))
    ).scalar_one()
    rows = (
        await db.execute(
            text(
                "SELECT trace_id, actor_user_id, actor_snapshot, target_user_id, "
                "target_snapshot, action, field_name, old_value, new_value, reason, "
                "created_at FROM admin_authority_traces "
                "ORDER BY created_at DESC, trace_id DESC "
                "LIMIT :limit OFFSET :offset"
            ),
            {"limit": page_size, "offset": (page - 1) * page_size},
        )
    ).mappings().all()

    data = [
        AdminAuthorityTraceResponse(
            trace_id=str(row["trace_id"]),
            actor_user_id=str(row["actor_user_id"]),
            actor_snapshot=row["actor_snapshot"],
            target_user_id=str(row["target_user_id"]),
            target_snapshot=row["target_snapshot"],
            action=row["action"],
            field_name=row["field_name"],
            old_value=row["old_value"],
            new_value=row["new_value"],
            reason=row["reason"],
            created_at=str(row["created_at"]),
        ).model_dump()
        for row in rows
    ]
    return {
        "data": data,
        "meta": {"total": int(total), "page": page, "page_size": page_size},
    }
