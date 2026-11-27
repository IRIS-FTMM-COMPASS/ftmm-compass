"""Copy legacy scheduling inputs into one recorded academic period."""

from dataclasses import asdict, dataclass, field
from datetime import time
import hashlib
import json
from typing import Any
import uuid

from sqlalchemy import Connection, text

MIGRATION_REVISION = "9d5e2f3a4b61"
_STATE_TABLE = "scheduling_legacy_migration_state"
_AVAILABILITY_MAP = "legacy_availability_migration_map"
_REFERENCE_MAP = "legacy_instructor_reference_migration_map"
_NAME_TITLES = {"dr", "ir", "prof", "drs", "dra", "eng", "hj", "h", "cand", "sp", "btkv", "k"}


class LegacyMigrationError(RuntimeError):
    code = "legacy_migration_error"


class ActivePeriodAmbiguityError(LegacyMigrationError):
    code = "active_period_ambiguous"

    def __init__(self, period_ids: list[uuid.UUID]):
        self.period_ids = tuple(period_ids)
        super().__init__(f"Expected exactly one active period, found {len(period_ids)}")


class ActivePeriodMismatchError(LegacyMigrationError):
    code = "active_period_mismatch"

    def __init__(self, recorded: uuid.UUID, active: uuid.UUID | None):
        self.recorded_period_id = recorded
        self.active_period_id = active
        super().__init__("The active period no longer matches the recorded migration target")


@dataclass(frozen=True)
class PreferenceConflict:
    reason: str
    user_id: uuid.UUID
    day_of_week: int
    start_hour: int
    end_hour: int
    other_source_id: uuid.UUID | None = None
    other_preference_id: uuid.UUID | None = None
    other_kind: str | None = None
    other_start_hour: int | None = None
    other_end_hour: int | None = None


class LegacyPreferenceConflictError(LegacyMigrationError):
    code = "legacy_preference_conflict"

    def __init__(self, conflicts: list[PreferenceConflict]):
        self.conflicts = tuple(sorted(conflicts, key=lambda item: repr(item)))
        super().__init__(f"Legacy availability has {len(conflicts)} unresolved overlap(s)")


@dataclass(frozen=True)
class LegacyMigrationResult:
    status: str
    academic_period_id: uuid.UUID | None
    availability_sources: int = 0
    reference_sources: int = 0
    availability_inserted: int = 0
    availability_skipped_existing: int = 0
    availability_conflicts: int = 0
    availability_rerun: int = 0
    references_inserted: int = 0
    references_skipped_existing: int = 0
    references_conflicts: int = 0
    references_rerun: int = 0
    provenance_copied: int = 0
    provenance_skipped: int = 0
    cleared_preference_copies: int = 0
    modified_preference_copies: int = 0
    cleared_reference_copies: int = 0
    modified_reference_copies: int = 0
    integrity_errors: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LegacyRollbackResult:
    status: str
    preferences_deleted: int = 0
    preferences_preserved_modified: int = 0
    preferences_already_deleted: int = 0
    references_deleted: int = 0
    references_preserved_modified: int = 0
    references_already_deleted: int = 0
    provenance_deleted: int = 0
    integrity_errors: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class _AvailabilityPlan:
    availability_id: uuid.UUID
    user_id: uuid.UUID
    day_of_week: int
    start_hour: int
    end_hour: int
    action: str
    skip_reason: str | None = None


@dataclass(frozen=True)
class _ReferencePlan:
    instructor_reference_id: uuid.UUID
    curriculum_course_id: uuid.UUID
    source_document_id: uuid.UUID | None
    instructor_name: str
    instructor_role: str
    user_id: uuid.UUID | None
    action: str
    skip_reason: str | None = None


def _rows(bind: Connection, statement: str, **params: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in bind.execute(text(statement), params).mappings().all()]


def _scalar(bind: Connection, statement: str, **params: Any) -> int:
    return int(bind.execute(text(statement), params).scalar_one())


def _lock_migration(bind: Connection) -> None:
    bind.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended('scheduling-legacy-migration', 0))")
    )


def _state(bind: Connection) -> dict[str, Any] | None:
    rows = _rows(
        bind,
        f"""
        SELECT target_academic_period_id, migration_revision
        FROM {_STATE_TABLE}
        WHERE singleton = TRUE
        """,
    )
    return rows[0] if rows else None


def _target_period(bind: Connection) -> uuid.UUID | None:
    bind.execute(text("LOCK TABLE academic_periods IN SHARE MODE"))
    active_ids = [
        row["academic_period_id"]
        for row in _rows(
            bind,
            """
            SELECT academic_period_id
            FROM academic_periods
            WHERE is_active = TRUE
            ORDER BY academic_period_id
            FOR UPDATE
            """,
        )
    ]
    if len(active_ids) > 1:
        raise ActivePeriodAmbiguityError(active_ids)
    state = _state(bind)
    if not active_ids:
        if state is not None:
            raise ActivePeriodMismatchError(state["target_academic_period_id"], None)
        return None
    if state is not None and state["target_academic_period_id"] != active_ids[0]:
        raise ActivePeriodMismatchError(state["target_academic_period_id"], active_ids[0])
    if state is not None and state["migration_revision"] != MIGRATION_REVISION:
        raise LegacyMigrationError("The recorded migration revision does not match")
    return active_ids[0]


def _fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _uuid_value(value: uuid.UUID | None) -> str | None:
    return str(value) if value is not None else None


def _preference_payload(
    user_id: uuid.UUID,
    period_id: uuid.UUID,
    day_of_week: int,
    start_hour: int,
    end_hour: int,
) -> dict[str, Any]:
    return {
        "user_id": str(user_id),
        "academic_period_id": str(period_id),
        "day_of_week": day_of_week,
        "start_time": f"{start_hour:02d}:00:00",
        "end_time": f"{end_hour:02d}:00:00",
        "kind": "preferred",
    }


def _reference_payload(
    curriculum_course_id: uuid.UUID,
    period_id: uuid.UUID,
    source_document_id: uuid.UUID | None,
    instructor_name: str,
    instructor_role: str,
    user_id: uuid.UUID | None,
) -> dict[str, Any]:
    return {
        "curriculum_course_id": str(curriculum_course_id),
        "academic_period_id": str(period_id),
        "source_document_id": _uuid_value(source_document_id),
        "instructor_name": instructor_name,
        "instructor_role": instructor_role,
        "user_id": _uuid_value(user_id),
    }


def _current_preference_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": str(row["user_id"]),
        "academic_period_id": str(row["academic_period_id"]),
        "day_of_week": row["day_of_week"],
        "start_time": row["start_time"].strftime("%H:%M:%S"),
        "end_time": row["end_time"].strftime("%H:%M:%S"),
        "kind": row["kind"],
    }


def _current_reference_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "curriculum_course_id": str(row["curriculum_course_id"]),
        "academic_period_id": str(row["academic_period_id"]),
        "source_document_id": _uuid_value(row["source_document_id"]),
        "instructor_name": row["instructor_name"],
        "instructor_role": row["instructor_role"],
        "user_id": _uuid_value(row["user_id"]),
    }


def _normalize_name(raw: str) -> str:
    head = raw.split(",", 1)[0].lower()
    cleaned = "".join(
        character if character.isascii() and character.isalpha() else " "
        for character in head
    )
    return " ".join(
        token
        for token in cleaned.split()
        if len(token) > 1 and token not in _NAME_TITLES
    )


def _availability_plans(
    bind: Connection, period_id: uuid.UUID
) -> tuple[list[_AvailabilityPlan], int]:
    sources = _rows(
        bind,
        """
        SELECT availability_id, user_id, day_of_week, start_hour, end_hour
        FROM lecturer_availability
        ORDER BY availability_id
        """,
    )
    mapped = {
        row["availability_id"]
        for row in _rows(
            bind,
            f"""
            SELECT availability_id
            FROM {_AVAILABILITY_MAP}
            WHERE academic_period_id = :period_id
            """,
            period_id=period_id,
        )
    }
    existing = _rows(
        bind,
        """
        SELECT preference_id, user_id, day_of_week, start_time, end_time, kind
        FROM lecturer_schedule_preferences
        WHERE academic_period_id = :period_id
        ORDER BY preference_id
        """,
        period_id=period_id,
    )
    existing_ranges = [
        (
            row,
            row["start_time"].hour,
            row["end_time"].hour,
        )
        for row in existing
    ]
    plans: list[_AvailabilityPlan] = []
    planned: list[tuple[uuid.UUID, uuid.UUID, int, int, int]] = []
    conflicts: list[PreferenceConflict] = []
    for source in sources:
        if source["availability_id"] in mapped:
            plans.append(_AvailabilityPlan(action="rerun", **source))
            continue
        overlaps = [
            (row, start, end)
            for row, start, end in existing_ranges
            if row["user_id"] == source["user_id"]
            and row["day_of_week"] == source["day_of_week"]
            and source["start_hour"] < end
            and start < source["end_hour"]
        ]
        exact = [
            row
            for row, start, end in overlaps
            if row["kind"] == "preferred"
            and start == source["start_hour"]
            and end == source["end_hour"]
        ]
        if exact:
            plans.append(
                _AvailabilityPlan(
                    action="skip_existing",
                    skip_reason="equivalent_preference",
                    **source,
                )
            )
            continue
        if overlaps:
            for row, start, end in overlaps:
                conflicts.append(
                    PreferenceConflict(
                        reason="existing_preference_overlap",
                        user_id=source["user_id"],
                        day_of_week=source["day_of_week"],
                        start_hour=source["start_hour"],
                        end_hour=source["end_hour"],
                        other_preference_id=row["preference_id"],
                        other_kind=row["kind"],
                        other_start_hour=start,
                        other_end_hour=end,
                    )
                )
            continue
        legacy_overlaps = [
            item
            for item in planned
            if item[1] == source["user_id"]
            and item[2] == source["day_of_week"]
            and source["start_hour"] < item[4]
            and item[3] < source["end_hour"]
        ]
        if legacy_overlaps:
            for other_id, _, _, start, end in legacy_overlaps:
                conflicts.append(
                    PreferenceConflict(
                        reason="legacy_availability_overlap",
                        user_id=source["user_id"],
                        day_of_week=source["day_of_week"],
                        start_hour=source["start_hour"],
                        end_hour=source["end_hour"],
                        other_source_id=other_id,
                        other_start_hour=start,
                        other_end_hour=end,
                    )
                )
            continue
        planned.append(
            (
                source["availability_id"],
                source["user_id"],
                source["day_of_week"],
                source["start_hour"],
                source["end_hour"],
            )
        )
        plans.append(_AvailabilityPlan(action="copy", **source))
    if conflicts:
        raise LegacyPreferenceConflictError(conflicts)
    return plans, len(sources)


def _reference_match(
    candidate: dict[str, Any], existing: dict[str, Any]
) -> str | None:
    same_user = (
        candidate["user_id"] is not None
        and candidate["user_id"] == existing["user_id"]
    )
    candidate_name = _normalize_name(candidate["instructor_name"])
    existing_name = _normalize_name(existing["instructor_name"])
    same_name = bool(candidate_name) and candidate_name == existing_name
    same_unlinked_name = (
        same_name and candidate["user_id"] is None and existing["user_id"] is None
    )
    same_cross_role_identity = same_user or (
        same_name and (candidate["user_id"] is None or existing["user_id"] is None)
    )
    if candidate["instructor_role"] == "pjmk":
        if existing["instructor_role"] == "pjmk":
            if same_user or same_unlinked_name:
                return "equivalent"
            return "pjmk_conflict"
        if existing["instructor_role"] == "teaching_team" and same_cross_role_identity:
            return "pjmk_is_team"
        return None
    if candidate["instructor_role"] == "teaching_team":
        if existing["instructor_role"] == "pjmk" and same_cross_role_identity:
            return "pjmk_is_team"
        if existing["instructor_role"] != "teaching_team":
            return None
        if same_user or same_unlinked_name:
            return "equivalent"
        if same_name:
            return "instructor_identity_conflict"
        return None
    return (
        "equivalent"
        if all(
            candidate[key] == existing[key]
            for key in (
                "curriculum_course_id",
                "source_document_id",
                "instructor_name",
                "instructor_role",
                "user_id",
            )
        )
        else None
    )


def _reference_plans(
    bind: Connection, period_id: uuid.UUID
) -> tuple[list[_ReferencePlan], int]:
    sources = _rows(
        bind,
        """
        SELECT instructor_reference_id, curriculum_course_id, source_document_id,
               instructor_name, instructor_role, user_id
        FROM course_instructor_references
        WHERE academic_period_id IS NULL
        ORDER BY instructor_reference_id
        """,
    )
    mapped = {
        row["instructor_reference_id"]
        for row in _rows(
            bind,
            f"""
            SELECT instructor_reference_id
            FROM {_REFERENCE_MAP}
            WHERE academic_period_id = :period_id
            """,
            period_id=period_id,
        )
    }
    existing = _rows(
        bind,
        """
        SELECT instructor_reference_id, curriculum_course_id, source_document_id,
               instructor_name, instructor_role, user_id
        FROM course_instructor_references
        WHERE academic_period_id = :period_id
        ORDER BY instructor_reference_id
        """,
        period_id=period_id,
    )
    plans: list[_ReferencePlan] = []
    planned: list[dict[str, Any]] = []
    for source in sources:
        if source["instructor_reference_id"] in mapped:
            plans.append(
                _ReferencePlan(action="rerun", skip_reason=None, **source)
            )
            continue
        candidates = [
            row
            for row in [*existing, *planned]
            if row["curriculum_course_id"] == source["curriculum_course_id"]
        ]
        equivalent = False
        conflict_reason: str | None = None
        for candidate in candidates:
            match = _reference_match(source, candidate)
            if match == "equivalent":
                equivalent = True
                break
            if match is not None:
                conflict_reason = match
        if equivalent:
            plans.append(
                _ReferencePlan(
                    action="skip_existing",
                    skip_reason="equivalent_reference",
                    **source,
                )
            )
        elif conflict_reason is not None:
            plans.append(
                _ReferencePlan(
                    action="skip_conflict",
                    skip_reason=conflict_reason,
                    **source,
                )
            )
        else:
            plans.append(_ReferencePlan(action="copy", skip_reason=None, **source))
            planned.append(source)
    return plans, len(sources)


def _insert_availability(bind: Connection, period_id: uuid.UUID, plan: _AvailabilityPlan) -> None:
    payload = _preference_payload(
        plan.user_id, period_id, plan.day_of_week, plan.start_hour, plan.end_hour
    )
    bind_payload = {
        **payload,
        "start_time": time(plan.start_hour),
        "end_time": time(plan.end_hour),
    }
    with bind.begin_nested():
        target_id = bind.execute(
            text(
                """
                INSERT INTO lecturer_schedule_preferences (
                    user_id, academic_period_id, day_of_week,
                    start_time, end_time, kind
                ) VALUES (
                    :user_id, :academic_period_id, :day_of_week,
                    :start_time, :end_time, 'preferred'
                )
                RETURNING preference_id
                """
            ),
            bind_payload,
        ).scalar_one()
        bind.execute(
            text(
                f"""
                INSERT INTO {_AVAILABILITY_MAP} (
                    availability_id, preference_id, academic_period_id,
                    payload_fingerprint, migration_revision, status
                ) VALUES (
                    :availability_id, :preference_id, :academic_period_id,
                    :payload_fingerprint, :migration_revision, 'copied'
                )
                """
            ),
            {
                "availability_id": plan.availability_id,
                "preference_id": target_id,
                "academic_period_id": period_id,
                "payload_fingerprint": _fingerprint(payload),
                "migration_revision": MIGRATION_REVISION,
            },
        )


def _insert_reference(bind: Connection, period_id: uuid.UUID, plan: _ReferencePlan) -> None:
    payload = _reference_payload(
        plan.curriculum_course_id,
        period_id,
        plan.source_document_id,
        plan.instructor_name,
        plan.instructor_role,
        plan.user_id,
    )
    with bind.begin_nested():
        target_id = bind.execute(
            text(
                """
                INSERT INTO course_instructor_references (
                    curriculum_course_id, academic_period_id, source_document_id,
                    instructor_name, instructor_role, user_id
                ) VALUES (
                    :curriculum_course_id, :academic_period_id, :source_document_id,
                    :instructor_name, :instructor_role, :user_id
                )
                RETURNING instructor_reference_id
                """
            ),
            payload,
        ).scalar_one()
        bind.execute(
            text(
                f"""
                INSERT INTO {_REFERENCE_MAP} (
                    instructor_reference_id, target_reference_id, academic_period_id,
                    payload_fingerprint, migration_revision, status, skip_reason
                ) VALUES (
                    :instructor_reference_id, :target_reference_id, :academic_period_id,
                    :payload_fingerprint, :migration_revision, 'copied', NULL
                )
                """
            ),
            {
                "instructor_reference_id": plan.instructor_reference_id,
                "target_reference_id": target_id,
                "academic_period_id": period_id,
                "payload_fingerprint": _fingerprint(payload),
                "migration_revision": MIGRATION_REVISION,
            },
        )


def _record_availability_skip(
    bind: Connection, period_id: uuid.UUID, plan: _AvailabilityPlan
) -> None:
    bind.execute(
        text(
            f"""
            INSERT INTO {_AVAILABILITY_MAP} (
                availability_id, academic_period_id, migration_revision, status, skip_reason
            ) VALUES (
                :availability_id, :academic_period_id, :migration_revision, 'skipped', :skip_reason
            )
            """
        ),
        {
            "availability_id": plan.availability_id,
            "academic_period_id": period_id,
            "migration_revision": MIGRATION_REVISION,
            "skip_reason": plan.skip_reason,
        },
    )


def _record_reference_skip(
    bind: Connection, period_id: uuid.UUID, plan: _ReferencePlan
) -> None:
    bind.execute(
        text(
            f"""
            INSERT INTO {_REFERENCE_MAP} (
                instructor_reference_id, academic_period_id, migration_revision,
                status, skip_reason
            ) VALUES (
                :instructor_reference_id, :academic_period_id, :migration_revision,
                'skipped', :skip_reason
            )
            """
        ),
        {
            "instructor_reference_id": plan.instructor_reference_id,
            "academic_period_id": period_id,
            "migration_revision": MIGRATION_REVISION,
            "skip_reason": plan.skip_reason,
        },
    )


def _inspect_provenance(
    bind: Connection, period_id: uuid.UUID
) -> dict[str, Any]:
    preference_rows = _rows(
        bind,
        f"""
        SELECT m.status, m.payload_fingerprint,
               t.preference_id, t.user_id, t.academic_period_id, t.day_of_week,
               t.start_time, t.end_time, t.kind
        FROM {_AVAILABILITY_MAP} m
        LEFT JOIN lecturer_schedule_preferences t
          ON t.preference_id = m.preference_id
        WHERE m.academic_period_id = :period_id
        """,
        period_id=period_id,
    )
    reference_rows = _rows(
        bind,
        f"""
        SELECT m.status, m.payload_fingerprint,
               t.instructor_reference_id AS target_reference_id,
               t.curriculum_course_id, t.academic_period_id, t.source_document_id,
               t.instructor_name, t.instructor_role, t.user_id
        FROM {_REFERENCE_MAP} m
        LEFT JOIN course_instructor_references t
          ON t.instructor_reference_id = m.target_reference_id
        WHERE m.academic_period_id = :period_id
        """,
        period_id=period_id,
    )
    result: dict[str, Any] = {
        "provenance_copied": sum(row["status"] == "copied" for row in preference_rows + reference_rows),
        "provenance_skipped": sum(row["status"] == "skipped" for row in preference_rows + reference_rows),
        "cleared_preference_copies": 0,
        "modified_preference_copies": 0,
        "cleared_reference_copies": 0,
        "modified_reference_copies": 0,
    }
    errors: list[str] = []
    for row in preference_rows:
        if row["status"] != "copied":
            continue
        if row["preference_id"] is None:
            result["cleared_preference_copies"] += 1
        elif _fingerprint(_current_preference_payload(row)) != row["payload_fingerprint"]:
            result["modified_preference_copies"] += 1
    for row in reference_rows:
        if row["status"] != "copied":
            continue
        if row["target_reference_id"] is None:
            result["cleared_reference_copies"] += 1
        elif _fingerprint(_current_reference_payload(row)) != row["payload_fingerprint"]:
            result["modified_reference_copies"] += 1
    unmapped_availability = _scalar(
        bind,
        f"""
        SELECT count(*)
        FROM lecturer_availability s
        LEFT JOIN {_AVAILABILITY_MAP} m
          ON m.availability_id = s.availability_id
         AND m.academic_period_id = :period_id
        WHERE m.availability_id IS NULL
        """,
        period_id=period_id,
    )
    unmapped_references = _scalar(
        bind,
        f"""
        SELECT count(*)
        FROM course_instructor_references s
        LEFT JOIN {_REFERENCE_MAP} m
          ON m.instructor_reference_id = s.instructor_reference_id
         AND m.academic_period_id = :period_id
        WHERE s.academic_period_id IS NULL AND m.instructor_reference_id IS NULL
        """,
        period_id=period_id,
    )
    if unmapped_availability:
        errors.append(f"unmapped_availability_sources={unmapped_availability}")
    if unmapped_references:
        errors.append(f"unmapped_reference_sources={unmapped_references}")
    result["integrity_errors"] = tuple(errors)
    return result


def upgrade_legacy_scheduling(bind: Connection) -> LegacyMigrationResult:
    """Copy once into the recorded period; conflicts are resolved before any copy."""
    _lock_migration(bind)
    period_id = _target_period(bind)
    if period_id is None:
        return LegacyMigrationResult(
            status="no_active_period",
            academic_period_id=None,
            availability_sources=_scalar(bind, "SELECT count(*) FROM lecturer_availability"),
            reference_sources=_scalar(
                bind,
                "SELECT count(*) FROM course_instructor_references WHERE academic_period_id IS NULL",
            ),
        )
    availability_plans, availability_sources = _availability_plans(bind, period_id)
    reference_plans, reference_sources = _reference_plans(bind, period_id)
    if _state(bind) is None:
        bind.execute(
            text(
                f"""
                INSERT INTO {_STATE_TABLE} (
                    singleton, target_academic_period_id, migration_revision, completed_at
                ) VALUES (
                    TRUE, :period_id, :migration_revision, NOW()
                )
                ON CONFLICT (singleton) DO NOTHING
                """
            ),
            {"period_id": period_id, "migration_revision": MIGRATION_REVISION},
        )
    counts = {
        "availability_inserted": 0,
        "availability_skipped_existing": 0,
        "availability_conflicts": 0,
        "availability_rerun": 0,
        "references_inserted": 0,
        "references_skipped_existing": 0,
        "references_conflicts": 0,
        "references_rerun": 0,
    }
    for plan in availability_plans:
        if plan.action == "copy":
            _insert_availability(bind, period_id, plan)
            counts["availability_inserted"] += 1
        elif plan.action == "skip_existing":
            _record_availability_skip(bind, period_id, plan)
            counts["availability_skipped_existing"] += 1
        else:
            counts["availability_rerun"] += 1
    for plan in reference_plans:
        if plan.action == "copy":
            _insert_reference(bind, period_id, plan)
            counts["references_inserted"] += 1
        elif plan.action == "skip_existing":
            _record_reference_skip(bind, period_id, plan)
            counts["references_skipped_existing"] += 1
        elif plan.action == "skip_conflict":
            _record_reference_skip(bind, period_id, plan)
            counts["references_conflicts"] += 1
        else:
            counts["references_rerun"] += 1
    inspection = _inspect_provenance(bind, period_id)
    return LegacyMigrationResult(
        status="completed",
        academic_period_id=period_id,
        availability_sources=availability_sources,
        reference_sources=reference_sources,
        **counts,
        **inspection,
    )


def rollback_legacy_scheduling(bind: Connection) -> LegacyRollbackResult:
    """Delete only unchanged owned copies, preserving edits and all user-created rows."""
    _lock_migration(bind)
    state = _state(bind)
    if state is None:
        return LegacyRollbackResult(status="not_migrated")
    period_id = state["target_academic_period_id"]
    preference_rows = _rows(
        bind,
        f"""
        SELECT m.availability_id, m.preference_id, m.payload_fingerprint,
               t.user_id, t.academic_period_id, t.day_of_week,
               t.start_time, t.end_time, t.kind
        FROM {_AVAILABILITY_MAP} m
        LEFT JOIN lecturer_schedule_preferences t
          ON t.preference_id = m.preference_id
        WHERE m.academic_period_id = :period_id AND m.status = 'copied'
        """,
        period_id=period_id,
    )
    reference_rows = _rows(
        bind,
        f"""
        SELECT m.instructor_reference_id, m.target_reference_id, m.payload_fingerprint,
               t.curriculum_course_id, t.academic_period_id, t.source_document_id,
               t.instructor_name, t.instructor_role, t.user_id
        FROM {_REFERENCE_MAP} m
        LEFT JOIN course_instructor_references t
          ON t.instructor_reference_id = m.target_reference_id
        WHERE m.academic_period_id = :period_id AND m.status = 'copied'
        """,
        period_id=period_id,
    )
    result = LegacyRollbackResult(status="rolled_back")
    deleted_preferences = 0
    preserved_preferences = 0
    deleted_references = 0
    preserved_references = 0
    already_deleted_preferences = 0
    already_deleted_references = 0
    provenance_deleted = 0
    for row in preference_rows:
        if row["preference_id"] is None:
            bind.execute(
                text(
                    f"""
                    DELETE FROM {_AVAILABILITY_MAP}
                    WHERE availability_id = :source_id AND academic_period_id = :period_id
                    """
                ),
                {"source_id": row["availability_id"], "period_id": period_id},
            )
            already_deleted_preferences += 1
            provenance_deleted += 1
        elif _fingerprint(_current_preference_payload(row)) != row["payload_fingerprint"]:
            preserved_preferences += 1
        else:
            with bind.begin_nested():
                bind.execute(
                    text("DELETE FROM lecturer_schedule_preferences WHERE preference_id = :target_id"),
                    {"target_id": row["preference_id"]},
                )
                bind.execute(
                    text(
                        f"""
                        DELETE FROM {_AVAILABILITY_MAP}
                        WHERE availability_id = :source_id AND academic_period_id = :period_id
                        """
                    ),
                    {"source_id": row["availability_id"], "period_id": period_id},
                )
            deleted_preferences += 1
            provenance_deleted += 1
    for row in reference_rows:
        if row["target_reference_id"] is None:
            bind.execute(
                text(
                    f"""
                    DELETE FROM {_REFERENCE_MAP}
                    WHERE instructor_reference_id = :source_id AND academic_period_id = :period_id
                    """
                ),
                {"source_id": row["instructor_reference_id"], "period_id": period_id},
            )
            already_deleted_references += 1
            provenance_deleted += 1
        elif _fingerprint(_current_reference_payload(row)) != row["payload_fingerprint"]:
            preserved_references += 1
        else:
            with bind.begin_nested():
                bind.execute(
                    text(
                        """
                        DELETE FROM course_instructor_references
                        WHERE instructor_reference_id = :target_id
                        """
                    ),
                    {"target_id": row["target_reference_id"]},
                )
                bind.execute(
                    text(
                        f"""
                        DELETE FROM {_REFERENCE_MAP}
                        WHERE instructor_reference_id = :source_id AND academic_period_id = :period_id
                        """
                    ),
                    {"source_id": row["instructor_reference_id"], "period_id": period_id},
                )
            deleted_references += 1
            provenance_deleted += 1
    for table in (_AVAILABILITY_MAP, _REFERENCE_MAP):
        deleted = bind.execute(
            text(f"DELETE FROM {table} WHERE academic_period_id = :period_id AND status = 'skipped'"),
            {"period_id": period_id},
        ).rowcount
        provenance_deleted += deleted
    return LegacyRollbackResult(
        status=result.status,
        preferences_deleted=deleted_preferences,
        preferences_preserved_modified=preserved_preferences,
        preferences_already_deleted=already_deleted_preferences,
        references_deleted=deleted_references,
        references_preserved_modified=preserved_references,
        references_already_deleted=already_deleted_references,
        provenance_deleted=provenance_deleted,
    )
