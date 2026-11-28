"""Jejak wewenang admin: pencatatan aksi manajemen akun."""

import json
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from models import User


def _identity_snapshot(user: User) -> str:
    values = getattr(user, "__dict__", {})
    payload: dict[str, Any] = {
        "user_id": str(values.get("user_id")),
        "email": values.get("email"),
        "full_name": values.get("full_name"),
        "role": values.get("role"),
        "is_active": values.get("is_active"),
        "phone_number": values.get("phone_number"),
        "bio": values.get("bio"),
        "career_interests": values.get("career_interests"),
    }

    profile = values.get("student_profile")
    if profile is not None:
        profile_values = getattr(profile, "__dict__", {})
        study_program_id = profile_values.get("study_program_id")
        payload.update(
            {
                "student_number": profile_values.get("student_number"),
                "study_program_id": (
                    str(study_program_id) if study_program_id is not None else None
                ),
                "admission_year": profile_values.get("admission_year"),
                "current_semester": profile_values.get("current_semester"),
            }
        )

    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def redact_trace_snapshot(raw: str) -> str:
    try:
        values = json.loads(raw)
    except (TypeError, ValueError):
        return raw
    if not isinstance(values, dict):
        return raw
    payload = {
        key: values.get(key) for key in ("user_id", "role", "is_active")
    }
    payload["redacted"] = True
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def _redacted_identity_snapshot(user: User) -> str:
    return redact_trace_snapshot(_identity_snapshot(user))


async def record_admin_action(
    db: AsyncSession,
    *,
    actor: User,
    target: User,
    action: str,
    reason: str,
    field_name: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
) -> None:
    """Tulis satu baris jejak wewenang; committer tetap berada di caller."""
    target_snapshot = (
        _redacted_identity_snapshot(target)
        if action == "anonymize"
        else _identity_snapshot(target)
    )
    await db.execute(
        text(
            "INSERT INTO admin_authority_traces "
            "(trace_id, actor_user_id, actor_snapshot, target_user_id, target_snapshot, "
            "action, field_name, old_value, new_value, reason) "
            "VALUES (CAST(:trace_id AS uuid), CAST(:actor_user_id AS uuid), "
            ":actor_snapshot, CAST(:target_user_id AS uuid), :target_snapshot, "
            ":action, :field_name, :old_value, :new_value, :reason)"
        ),
        {
            "trace_id": str(uuid.uuid4()),
            "actor_user_id": str(actor.user_id),
            "actor_snapshot": _identity_snapshot(actor),
            "target_user_id": str(target.user_id),
            "target_snapshot": target_snapshot,
            "action": action,
            "field_name": field_name,
            "old_value": old_value,
            "new_value": new_value,
            "reason": reason,
        },
    )
