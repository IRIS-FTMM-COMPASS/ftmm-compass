"""Integrasi lifecycle T11/T12: revisi, regenerate, stale, finalisasi, unlock."""

import uuid
from datetime import time

from sqlalchemy import delete, select, update

from models import (
    ClassInstructorAssignment,
    ClassSchedule,
    CourseInstructorReference,
    LecturerSchedulePreference,
    ScheduleEditLog,
    SchedulePeriodSettings,
    ScheduleProgramStatus,
    ScheduleRun,
)
from tests.test_scheduling_edits_finalize import _move_payload, scheduling_data  # noqa: F401
from tests.test_scheduling_generate import _make_case, _schedules

V1 = "/api/v1"
BASE = f"{V1}/scheduling"


def _revision_state(client, db_session, period_id, program_ids):
    async def read():
        rows = (
            await db_session.execute(
                select(SchedulePeriodSettings).where(
                    SchedulePeriodSettings.academic_period_id == period_id,
                )
            )
        ).scalars().all()
        return {
            str(row.study_program_id): row.input_revision
            for row in rows
        }

    state = client.portal.call(read)
    return state, [state.get(str(program_id)) for program_id in program_ids]


def _schedule_map(client, db_session, section_ids):
    return {
        row["section_id"]: row
        for row in _schedules(client, db_session, section_ids)
    }


def test_generation_persists_revision_and_room_change_stales_board(
    client, db_session, admin_headers
):
    case = _make_case(client, db_session)
    generated = client.post(
        f"{BASE}/generate",
        json={"academic_period_id": case["period_id"], "mode": "regenerate"},
        headers=admin_headers,
    )
    assert generated.status_code == 200, generated.text
    assert generated.json()["input_revision"] == 0
    assert generated.json()["study_program_id"] is None

    async def persisted_revision():
        run = await db_session.get(ScheduleRun, uuid.UUID(generated.json()["run_id"]))
        assert run is not None
        return run.input_revision

    assert client.portal.call(persisted_revision) == 0
    board = client.get(f"{BASE}/board", headers=admin_headers).json()
    item = next(
        row
        for row in board["data"]["classes"]
        if row["class_section_id"] == case["section_id"]
    )
    assert item["is_stale"] is False
    assert item["run_id"] == generated.json()["run_id"]

    room = client.patch(
        f"{BASE}/rooms/{case['room_ids'][0]}",
        json={"capacity": 81},
        headers=admin_headers,
    )
    assert room.status_code == 200, room.text
    stale = client.get(f"{BASE}/board", headers=admin_headers).json()
    stale_item = next(
        row
        for row in stale["data"]["classes"]
        if row["class_section_id"] == case["section_id"]
    )
    assert stale_item["is_stale"] is True
    assert stale_item["input_revision"] == 1
    assert stale["meta"]["stale_count"] >= 1

    legacy = client.get("/api/scheduling/board", headers=admin_headers)
    assert legacy.status_code == 200, legacy.text
    legacy_item = next(
        row
        for row in legacy.json()["data"]["classes"]
        if row["class_section_id"] == case["section_id"]
    )
    assert legacy_item["is_stale"] is True
    assert legacy_item["input_revision"] == stale_item["input_revision"]


def test_preference_class_count_and_legacy_assignment_changes_bump_revisions(
    client, db_session, admin_headers, pj_headers
):
    case = _make_case(client, db_session, with_assignment=False)
    period_id = uuid.UUID(case["period_id"])
    program_id = uuid.UUID(case["program_id"])
    preference = {
        "academic_period_id": case["period_id"],
        "slots": [
            {
                "day_of_week": 1,
                "start_time": "08:00:00",
                "end_time": "10:00:00",
                "kind": "preferred",
            }
        ],
    }
    changed = client.put(
        f"{BASE}/preferences/me",
        params={"academic_period_id": case["period_id"]},
        json=preference,
        headers=pj_headers,
    )
    assert changed.status_code == 200, changed.text
    state, _ = _revision_state(client, db_session, period_id, [program_id])
    assert state.get("None", 0) == 0
    assert [value for key, value in state.items() if key != "None"] == [1]

    repeated = client.put(
        f"{BASE}/preferences/me",
        params={"academic_period_id": case["period_id"]},
        json=preference,
        headers=pj_headers,
    )
    assert repeated.status_code == 200, repeated.text
    state, _ = _revision_state(client, db_session, period_id, [program_id])
    assert state.get("None", 0) == 0
    assert [value for key, value in state.items() if key != "None"] == [1]

    override = client.post(
        f"{BASE}/class-count-overrides",
        json={
            "academic_period_id": case["period_id"],
            "course_id": case["course_id"],
            "study_program_id": case["program_id"],
            "class_count": 2,
        },
        headers=admin_headers,
    )
    assert override.status_code == 200, override.text
    state, _ = _revision_state(client, db_session, period_id, [program_id])
    assert state.get("None", 0) == 0
    assert state[case["program_id"]] == 1

    assignment = client.put(
        f"{BASE}/classes/{case['section_id']}/assignment",
        json={
            "academic_period_id": case["period_id"],
            "user_id": case["lecturer_id"],
            "source": "manual",
            "is_pinned": True,
        },
        headers=admin_headers,
    )
    assert assignment.status_code == 200, assignment.text
    state, _ = _revision_state(client, db_session, period_id, [program_id])
    assert state.get("None", 0) == 0
    assert state[case["program_id"]] == 2


def test_scoped_regenerate_preserves_manual_final_and_other_program(
    client, db_session, pj_headers, scheduling_data
):
    data = scheduling_data
    before = _schedule_map(
        client,
        db_session,
        [data["section_a"], data["section_b"], data["section_c"]],
    )

    async def finalize_other_and_move_draft():
        await db_session.execute(
            update(ScheduleProgramStatus)
            .where(
                ScheduleProgramStatus.academic_period_id
                == uuid.UUID(data["period_id"]),
                ScheduleProgramStatus.study_program_id
                == uuid.UUID(data["program_trkb"]),
            )
            .values(state="final")
        )
        schedule = await db_session.get(
            ClassSchedule, uuid.UUID(before[data["section_b"]]["id"])
        )
        schedule.day_of_week = 5
        schedule.start_time = time(15)
        schedule.end_time = time(17)
        await db_session.commit()

    client.portal.call(finalize_other_and_move_draft)
    moved = client.patch(
        f"{BASE}/classes/{data['section_a']}",
        json=_move_payload(data, day=4, start=9),
        headers=pj_headers,
    )
    assert moved.status_code == 200, moved.text

    regenerated = client.post(
        f"{BASE}/generate",
        json={
            "academic_period_id": data["period_id"],
            "mode": "regenerate",
            "study_program_id": data["program_tsd"],
        },
        headers=pj_headers,
    )
    assert regenerated.status_code == 200, regenerated.text
    body = regenerated.json()
    assert body["study_program_id"] == data["program_tsd"]
    assert body["regenerated_count"] == 1
    assert body["preserved_manual_count"] == 1
    assert body["preserved_final_count"] == 1

    after = _schedule_map(
        client,
        db_session,
        [data["section_a"], data["section_b"], data["section_c"]],
    )
    assert after[data["section_a"]]["id"] == before[data["section_a"]]["id"]
    assert after[data["section_a"]]["day"] == 4
    assert after[data["section_a"]]["start"] == 9
    assert after[data["section_a"]]["end"] == 11
    assert after[data["section_c"]] == before[data["section_c"]]
    assert after[data["section_b"]]["id"] != before[data["section_b"]]["id"]
    assert after[data["section_b"]]["day"] != 5

    board = client.get(f"{BASE}/board", headers=pj_headers).json()
    manual = next(
        row
        for row in board["data"]["classes"]
        if row["class_section_id"] == data["section_a"]
    )
    final = next(
        row
        for row in board["data"]["classes"]
        if row["class_section_id"] == data["section_c"]
    )
    assert manual["is_manually_edited"] is True
    assert final["state"] == "final"
    assert final["is_stale"] is False


def test_finalize_rejects_stale_and_unassigned_classes(
    client, db_session, pj_headers, scheduling_data
):
    data = scheduling_data
    period_id = uuid.UUID(data["period_id"])

    async def make_stale():
        settings = (
            await db_session.execute(
                select(SchedulePeriodSettings).where(
                    SchedulePeriodSettings.academic_period_id == period_id,
                    SchedulePeriodSettings.study_program_id.is_(None),
                )
            )
        ).scalars().first()
        if settings is None:
            db_session.add(
                SchedulePeriodSettings(
                    academic_period_id=period_id,
                    study_program_id=None,
                    input_revision=1,
                )
            )
        else:
            settings.input_revision = 1
        await db_session.commit()

    client.portal.call(make_stale)
    stale = client.post(
        f"{BASE}/periods/{data['period_id']}/finalize", headers=pj_headers
    )
    assert stale.status_code == 409, stale.text
    assert stale.json()["error"]["code"] == "schedule_stale"

    async def refresh_run_and_remove_assignment():
        await db_session.execute(
            update(ScheduleRun)
            .where(ScheduleRun.academic_period_id == period_id)
            .values(input_revision=1)
        )
        await db_session.execute(
            update(ClassInstructorAssignment)
            .where(
                ClassInstructorAssignment.class_section_id
                == uuid.UUID(data["section_b"])
            )
            .values(is_active=False)
        )
        await db_session.commit()

    client.portal.call(refresh_run_and_remove_assignment)
    unassigned = client.post(
        f"{BASE}/periods/{data['period_id']}/finalize", headers=pj_headers
    )
    assert unassigned.status_code == 422, unassigned.text
    assert unassigned.json()["error"]["code"] == "unassigned_classes"
    assert any(
        item["class_section_id"] == data["section_b"]
        and "missing_assignment" in item["reasons"]
        for item in unassigned.json()["error"]["details"]
    )


def test_finalize_warns_audits_and_locks_period_inputs(
    client, db_session, pj_headers, scheduling_data
):
    data = scheduling_data

    async def add_outside_preference():
        assignment = (
            await db_session.execute(
                select(ClassInstructorAssignment).where(
                    ClassInstructorAssignment.class_section_id
                    == uuid.UUID(data["section_a"])
                )
            )
        ).scalars().one()
        await db_session.execute(
            delete(LecturerSchedulePreference).where(
                LecturerSchedulePreference.user_id == assignment.user_id,
                LecturerSchedulePreference.academic_period_id
                == uuid.UUID(data["period_id"]),
            )
        )
        db_session.add(
            LecturerSchedulePreference(
                user_id=assignment.user_id,
                academic_period_id=uuid.UUID(data["period_id"]),
                day_of_week=5,
                start_time=time(16),
                end_time=time(17),
                kind="preferred",
            )
        )
        await db_session.commit()
        return str(assignment.user_id)

    lecturer_id = client.portal.call(add_outside_preference)
    finalized = client.post(
        f"{BASE}/periods/{data['period_id']}/finalize", headers=pj_headers
    )
    assert finalized.status_code == 200, finalized.text
    body = finalized.json()
    assert any(
        warning["code"] == "outside_preferred_window"
        for warning in body["warnings"]
    )
    assert body["completeness"]["classes"] == {"total": 2, "scheduled": 2}
    assert body["completeness"]["preferences"]["expected"] == 1
    assert body["completeness"]["preferences"]["complete"] == 1

    async def audit_warnings():
        rows = (
            await db_session.execute(
                select(ScheduleEditLog).where(
                    ScheduleEditLog.reason == "finalize",
                )
            )
        ).scalars().all()
        assert rows
        assert all(row.after_state["warnings"] for row in rows)
        assert all(row.after_state["completeness"] for row in rows)

    client.portal.call(audit_warnings)

    preference = client.put(
        f"{BASE}/preferences/me",
        params={"academic_period_id": data["period_id"]},
        json=[],
        headers=pj_headers,
    )
    assert preference.status_code == 409, preference.text
    assert preference.json()["error"]["code"] == "schedule_final"

    assignment = client.put(
        f"{BASE}/classes/{data['section_a']}/assignment",
        json={
            "academic_period_id": data["period_id"],
            "user_id": lecturer_id,
            "source": "manual",
            "is_pinned": True,
        },
        headers=pj_headers,
    )
    assert assignment.status_code == 409, assignment.text
    assert assignment.json()["error"]["code"] == "schedule_final"

    async def mapping_id():
        return str(
            (
                await db_session.execute(
                    select(CourseInstructorReference.instructor_reference_id)
                    .where(
                        CourseInstructorReference.academic_period_id
                        == uuid.UUID(data["period_id"]),
                        CourseInstructorReference.user_id == uuid.UUID(lecturer_id),
                    )
                    .order_by(CourseInstructorReference.position)
                    .limit(1)
                )
            ).scalars().one()
        )

    reference_id = client.portal.call(mapping_id)
    mapping = client.patch(
        f"{BASE}/instructor-references/{reference_id}",
        json={"academic_period_id": data["period_id"], "position": 1},
        headers=pj_headers,
    )
    assert mapping.status_code == 409, mapping.text
    assert mapping.json()["error"]["code"] == "schedule_final"

    room = client.patch(
        f"{BASE}/rooms/{data['room_a']}",
        json={"capacity": 61},
        headers=pj_headers,
    )
    assert room.status_code == 409, room.text
    assert room.json()["error"]["code"] == "schedule_final"


def test_unlock_edit_regenerate_finalize_cycle_repeats(
    client, admin_headers, pj_headers, scheduling_data
):
    data = scheduling_data
    for _ in range(2):
        finalized = client.post(
            f"{BASE}/periods/{data['period_id']}/finalize", headers=pj_headers
        )
        assert finalized.status_code == 200, finalized.text
        unlocked = client.post(
            f"{BASE}/periods/{data['period_id']}/unlock",
            json={"reason": "Siklus perbaikan jadwal", "confirm": True},
            headers=admin_headers,
        )
        assert unlocked.status_code == 200, unlocked.text
        assert unlocked.json()["audit_count"] == 3
        moved = client.patch(
            f"{BASE}/classes/{data['section_a']}",
            json=_move_payload(data, day=4, start=8),
            headers=pj_headers,
        )
        assert moved.status_code == 200, moved.text
        regenerated = client.post(
            f"{BASE}/generate",
            json={
                "academic_period_id": data["period_id"],
                "mode": "regenerate",
            },
            headers=pj_headers,
        )
        assert regenerated.status_code == 200, regenerated.text
        assert regenerated.json()["preserved_manual_count"] == 1


def test_regenerate_rejects_other_program_scope(
    client, pj_headers, scheduling_data
):
    data = scheduling_data
    denied = client.post(
        f"{BASE}/generate",
        json={
            "academic_period_id": data["period_id"],
            "mode": "regenerate",
            "study_program_id": data["program_trkb"],
        },
        headers=pj_headers,
    )
    assert denied.status_code == 403, denied.text
    assert denied.json()["error"]["code"] == "akses_prodi_ditolak"
