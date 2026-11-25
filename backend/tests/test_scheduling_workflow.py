"""End-to-end HTTP workflow for period-scoped lecturer scheduling."""

import json
import uuid
from datetime import time
from typing import Any

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import selectinload
from auth import get_password_hash
from models import (
    AcademicPeriod,
    ClassInstructorAssignment,
    ClassSchedule,
    ClassSection,
    Course,
    CourseOffering,
    CourseOfferingEligibility,
    Curriculum,
    CurriculumCourse,
    LecturerProfile,
    OfferingComponent,
    Room,
    ScheduleEditLog,
    SchedulePeriodLock,
    SchedulePeriodSettings,
    ScheduleProgramStatus,
    ScheduleRun,
    StudyProgram,
    User,
)
from tests.conftest import SEEDED_PJ
from tests.test_scheduling_assignments import _login, _own_group, _preview, _save

V1 = "/api/v1"
LEGACY = "/api"
BASE = f"{V1}/scheduling"


@pytest.fixture
def workflow_case(client, db_session) -> dict[str, Any]:
    async def setup():
        label = uuid.uuid4().hex[:8]
        max_year = (
            await db_session.execute(select(func.max(AcademicPeriod.academic_year_start)))
        ).scalar()
        year = int(max_year or 2026) + 50

        # Dashboard reads only the active period; isolated_db rolls this switch back.
        await db_session.execute(
            update(AcademicPeriod)
            .where(AcademicPeriod.is_active.is_(True))
            .values(is_active=False)
        )
        period = AcademicPeriod(
            academic_year_start=year,
            semester_number=1,
            term="ganjil",
            is_active=True,
        )
        db_session.add(period)
        await db_session.flush()

        pj = (
            await db_session.execute(
                select(User)
                .options(selectinload(User.lecturer_profile))
                .where(User.email == SEEDED_PJ[0])
            )
        ).scalars().one()
        assert pj.lecturer_profile is not None
        program_id = pj.lecturer_profile.study_program_id
        program_code = (
            await db_session.execute(
                select(StudyProgram.program_code).where(
                    StudyProgram.study_program_id == program_id
                )
            )
        ).scalar_one()
        other_program_id = (
            await db_session.execute(
                select(StudyProgram.study_program_id)
                .where(StudyProgram.program_code == "TRKB")
                .limit(1)
            )
        ).scalar_one()
        assert other_program_id != program_id

        ordinary = User(
            email=f"workflow.ordinary.{label}@ftmm.unair.ac.id",
            full_name=f"Dosen Biasa Workflow {label}",
            role="lecturer",
            is_active=True,
            password_hash=get_password_hash(SEEDED_PJ[1]),
        )
        db_session.add(ordinary)
        await db_session.flush()
        db_session.add(
            LecturerProfile(
                user_id=ordinary.user_id,
                study_program_id=program_id,
                is_program_coordinator=False,
            )
        )

        async def course(owner_id: uuid.UUID, prefix: str):
            curriculum = Curriculum(
                study_program_id=owner_id,
                curriculum_name=f"Kurikulum Workflow {prefix} {label}",
                curriculum_year=year,
                is_active=True,
            )
            db_session.add(curriculum)
            await db_session.flush()
            number = uuid.uuid4().int % 10_000
            code = f"{prefix}{number:04d}"
            while (
                await db_session.execute(
                    select(Course.course_id).where(Course.course_code == code)
                )
            ).first() is not None:
                number = (number + 1) % 10_000
                code = f"{prefix}{number:04d}"
            course_row = Course(
                course_code=code,
                course_name=f"Mata Kuliah Workflow {prefix}",
                is_active=True,
            )
            db_session.add(course_row)
            await db_session.flush()
            curriculum_course = CurriculumCourse(
                curriculum_id=curriculum.curriculum_id,
                course_id=course_row.course_id,
                credits_total=3,
                recommended_semester=1,
                term="ganjil",
                course_type="wajib",
                course_scope="program_studi",
                is_active=True,
            )
            offering = CourseOffering(
                academic_period_id=period.academic_period_id,
                course_id=course_row.course_id,
                offering_code=f"{prefix}-{label}",
            )
            db_session.add_all([curriculum_course, offering])
            await db_session.flush()
            db_session.add(
                CourseOfferingEligibility(
                    course_offering_id=offering.course_offering_id,
                    curriculum_course_id=curriculum_course.curriculum_course_id,
                )
            )
            component = OfferingComponent(
                course_offering_id=offering.course_offering_id,
                component_code="KULIAH",
                component_type="lecture",
            )
            db_session.add(component)
            await db_session.flush()
            return curriculum_course, component, code

        curriculum_course, component, course_code = await course(program_id, "WF")
        _, other_component, _ = await course(other_program_id, "WL")
        sections = []
        for section_code in ("A", "B"):
            section = ClassSection(
                offering_component_id=component.offering_component_id,
                section_code=section_code,
                capacity=40,
                enrollment_status="open",
            )
            db_session.add(section)
            await db_session.flush()
            sections.append(section)
        other_section = ClassSection(
            offering_component_id=other_component.offering_component_id,
            section_code="X",
            capacity=40,
            enrollment_status="open",
        )
        db_session.add(other_section)
        await db_session.flush()

        room = Room(
            room_code=f"000-WF-{label}",
            capacity=80,
            owner_study_program_id=program_id,
            is_active=True,
        )
        other_room = Room(
            room_code=f"ZZZ-WF-{label}",
            capacity=80,
            owner_study_program_id=other_program_id,
            is_active=True,
        )
        db_session.add_all([room, other_room])
        await db_session.flush()
        other_schedule = ClassSchedule(
            class_section_id=other_section.class_section_id,
            day_of_week=1,
            start_time=time(7),
            end_time=time(10),
            room_id=other_room.room_id,
            room_name=other_room.room_code,
        )
        db_session.add(other_schedule)
        db_session.add_all(
            [
                SchedulePeriodSettings(
                    academic_period_id=period.academic_period_id,
                    study_program_id=None,
                    input_revision=0,
                ),
                SchedulePeriodSettings(
                    academic_period_id=period.academic_period_id,
                    study_program_id=program_id,
                    input_revision=0,
                ),
            ]
        )
        await db_session.commit()
        return {
            "period_id": period.academic_period_id,
            "program_id": program_id,
            "program_code": program_code,
            "curriculum_course_id": curriculum_course.curriculum_course_id,
            "course_code": course_code,
            "section_ids": [section.class_section_id for section in sections],
            "other_section_id": other_section.class_section_id,
            "room_id": room.room_id,
            "room_code": room.room_code,
            "other_schedule_id": other_schedule.class_schedule_id,
            "pj_id": pj.user_id,
            "pj_name": pj.full_name,
            "ordinary_email": ordinary.email,
        }

    return client.portal.call(setup)


async def _workflow_state(db_session, case: dict[str, Any], run_id=None):
    section_ids = [*case["section_ids"], case["other_section_id"]]
    assignments = (
        await db_session.execute(
            select(ClassInstructorAssignment)
            .where(ClassInstructorAssignment.class_section_id.in_(case["section_ids"]))
            .order_by(ClassInstructorAssignment.class_section_id)
        )
    ).scalars().all()
    other_schedule = await db_session.get(ClassSchedule, case["other_schedule_id"])
    run = (
        await db_session.get(ScheduleRun, uuid.UUID(str(run_id)))
        if run_id is not None
        else None
    )
    logs = (
        await db_session.execute(
            select(ScheduleEditLog)
            .where(ScheduleEditLog.class_section_id.in_(section_ids))
            .order_by(ScheduleEditLog.created_at, ScheduleEditLog.id)
        )
    ).scalars().all()
    status = await db_session.get(
        ScheduleProgramStatus, (case["period_id"], case["program_id"])
    )
    lock = await db_session.get(SchedulePeriodLock, case["period_id"])
    return {
        "assignments": [
            {
                "class_section_id": row.class_section_id,
                "user_id": row.user_id,
                "curriculum_course_id": row.curriculum_course_id,
                "source": row.source,
                "is_pinned": row.is_pinned,
                "is_active": row.is_active,
                "assigned_by": row.assigned_by,
            }
            for row in assignments
        ],
        "other_schedule": (
            other_schedule.day_of_week,
            other_schedule.start_time,
            other_schedule.end_time,
            other_schedule.room_id,
            other_schedule.room_name,
        ),
        "run": (
            {
                "study_program_id": run.study_program_id,
                "mode": run.mode,
                "input_revision": run.input_revision,
                "status": run.status,
                "triggered_by": run.triggered_by,
            }
            if run is not None
            else None
        ),
        "logs": [
            {
                "class_section_id": row.class_section_id,
                "changed_by": row.changed_by,
                "reason": row.reason,
                "before_state": row.before_state,
                "after_state": row.after_state,
            }
            for row in logs
        ],
        "status": (
            {
                "state": status.state,
                "finalized_by": status.finalized_by,
                "finalized_at": status.finalized_at,
            }
            if status is not None
            else None
        ),
        "lock": (
            {"krs_open": lock.krs_open, "locked_by": lock.locked_by}
            if lock is not None
            else None
        ),
    }


async def _authority_audit(db_session, actor_id, field_name, action_prefix):
    rows = (
        await db_session.execute(
            text(
                "SELECT action, actor_user_id, field_name, old_value, new_value "
                "FROM admin_authority_traces "
                "WHERE actor_user_id = CAST(:actor_id AS uuid) "
                "AND field_name = :field_name AND action LIKE :action_prefix "
                "ORDER BY created_at, action"
            ),
            {
                "actor_id": str(actor_id),
                "field_name": field_name,
                "action_prefix": action_prefix,
            },
        )
    ).mappings().all()
    return [dict(row) for row in rows]


def test_scheduling_workflow_from_preferences_to_admin_unlock(
    client, db_session, admin_headers, pj_headers, workflow_case
):
    case = workflow_case
    period_id = str(case["period_id"])
    curriculum_course_id = str(case["curriculum_course_id"])
    section_ids = {str(section_id) for section_id in case["section_ids"]}

    pj_me = client.get(f"{V1}/auth/me", headers=pj_headers)
    assert pj_me.status_code == 200, pj_me.text
    assert pj_me.json()["user_id"] == str(case["pj_id"])
    assert pj_me.json()["email"] == SEEDED_PJ[0]
    assert pj_me.json()["is_program_coordinator"] is True
    admin_me = client.get(f"{V1}/auth/me", headers=admin_headers)
    assert admin_me.status_code == 200, admin_me.text
    admin_id = admin_me.json()["user_id"]

    periods = client.get(f"{BASE}/preferences/periods", headers=pj_headers)
    assert periods.status_code == 200, periods.text
    assert periods.json()["meta"]["current_academic_period_id"] == period_id
    assert periods.json()["data"][0]["academic_period_id"] == period_id

    preference_payload = [
        {
            "day_of_week": 1,
            "start_time": "08:00:00",
            "end_time": "10:00:00",
            "kind": "preferred",
        }
    ]
    preference = client.put(
        f"{BASE}/preferences/me",
        params={"academic_period_id": period_id},
        json=preference_payload,
        headers=pj_headers,
    )
    assert preference.status_code == 200, preference.text
    preference_body = preference.json()
    assert preference_body["academic_period_id"] == period_id
    assert preference_body["user_id"] == str(case["pj_id"])
    assert preference_body["data"] == [
        {
            "day_of_week": 1,
            "day_name": "Senin",
            "start_time": "08:00:00",
            "end_time": "10:00:00",
            "kind": "preferred",
        }
    ]
    assert preference_body["meta"]["status"] == "filled"
    assert preference_body["meta"]["preferred_count"] == 1
    assert preference_body["meta"]["unavailable_count"] == 0
    assert preference_body["meta"]["warnings"] == []
    preference_read = client.get(
        f"{BASE}/preferences/me",
        params={"academic_period_id": period_id},
        headers=pj_headers,
    )
    assert preference_read.status_code == 200, preference_read.text
    assert preference_read.json() == preference_body

    mapping = client.post(
        f"{BASE}/instructor-references",
        json={
            "curriculum_course_id": curriculum_course_id,
            "academic_period_id": period_id,
            "instructor_name": case["pj_name"],
            "instructor_role": "pjmk",
            "user_id": str(case["pj_id"]),
        },
        headers=pj_headers,
    )
    assert mapping.status_code == 201, mapping.text
    mapping_body = mapping.json()
    assert mapping_body["curriculum_course_id"] == curriculum_course_id
    assert mapping_body["academic_period_id"] == period_id
    assert mapping_body["user_id"] == str(case["pj_id"])
    assert mapping_body["is_mapped"] is True
    assert mapping_body["eligibility_reason"] == "eligible"
    assert mapping_body["position"] == 1
    listed = client.get(
        f"{BASE}/instructor-references",
        params={"academic_period_id": period_id},
        headers=pj_headers,
    )
    listed_legacy = client.get(
        f"{LEGACY}/scheduling/instructor-references",
        params={"academic_period_id": period_id},
        headers=pj_headers,
    )
    assert listed.status_code == listed_legacy.status_code == 200
    assert listed.json() == listed_legacy.json()
    assert [item["reference_id"] for item in listed.json()["data"]] == [
        mapping_body["reference_id"]
    ]
    mapping_audit = client.portal.call(
        _authority_audit,
        db_session,
        case["pj_id"],
        mapping_body["reference_id"],
        "instructor_reference_%",
    )
    assert [row["action"] for row in mapping_audit] == ["instructor_reference_create"]
    assert json.loads(mapping_audit[0]["new_value"])["user_id"] == str(case["pj_id"])

    preview = _preview(client, pj_headers, case)
    assert preview == _preview(client, pj_headers, case)
    legacy_preview = _preview(client, pj_headers, case, LEGACY)
    assert preview == legacy_preview
    group = _own_group(preview, case)
    assert group["can_edit"] is True
    assert group["course_code"] == case["course_code"]
    assert [item["user_id"] for item in group["pool"]] == [str(case["pj_id"])]
    assert [item["section_code"] for item in group["classes"]] == ["A", "B"]
    assert all(item["existing_assignment"] is None for item in group["classes"])
    assert client.portal.call(_workflow_state, db_session, case)["assignments"] == []

    ordinary_headers = _login(client, case["ordinary_email"], SEEDED_PJ[1])
    denied_mutations = (
        client.get(f"{BASE}/assignments/preview", headers=ordinary_headers),
        client.put(
            f"{BASE}/assignments",
            json={
                "decisions": [
                    {
                        "class_section_id": str(case["section_ids"][0]),
                        "curriculum_course_id": curriculum_course_id,
                        "user_id": str(case["pj_id"]),
                        "source": "manual",
                        "is_pinned": True,
                    }
                ]
            },
            headers=ordinary_headers,
        ),
        client.post(
            f"{BASE}/instructor-references",
            json={
                "curriculum_course_id": curriculum_course_id,
                "academic_period_id": period_id,
                "instructor_name": case["pj_name"],
                "instructor_role": "teaching_team",
                "user_id": str(case["pj_id"]),
            },
            headers=ordinary_headers,
        ),
        client.post(
            f"{BASE}/generate",
            json={
                "academic_period_id": period_id,
                "mode": "regenerate",
                "study_program_id": str(case["program_id"]),
            },
            headers=ordinary_headers,
        ),
        client.patch(
            f"{BASE}/classes/{case['section_ids'][0]}",
            json={
                "day_of_week": 2,
                "start_hour": 8,
                "room_id": str(case["room_id"]),
                "reason": "Uji peran dosen biasa",
            },
            headers=ordinary_headers,
        ),
        client.post(f"{BASE}/periods/{period_id}/finalize", headers=ordinary_headers),
    )
    assert all(response.status_code == 403 for response in denied_mutations)

    decisions = [
        {
            "class_section_id": str(case["section_ids"][0]),
            "curriculum_course_id": curriculum_course_id,
            "user_id": str(case["pj_id"]),
            "source": "manual",
            "is_pinned": True,
        },
        {
            "class_section_id": str(case["section_ids"][1]),
            "curriculum_course_id": curriculum_course_id,
            "user_id": str(case["pj_id"]),
            "source": "auto",
            "is_pinned": False,
        },
    ]
    saved = _save(client, pj_headers, decisions)
    assert saved.status_code == 200, saved.text
    saved_body = saved.json()
    assert len(saved_body["data"]) == 2
    assert {item["class_section_id"] for item in saved_body["data"]} == section_ids
    assert {item["assigned_by"] for item in saved_body["data"]} == {str(case["pj_id"])}
    assert {item["curriculum_course_id"] for item in saved_body["data"]} == {
        curriculum_course_id
    }
    saved_by_section = {item["class_section_id"]: item for item in saved_body["data"]}
    assert saved_by_section[str(case["section_ids"][0])]["source"] == "manual"
    assert saved_by_section[str(case["section_ids"][0])]["is_pinned"] is True
    assert saved_by_section[str(case["section_ids"][1])]["source"] == "auto"
    assert saved_by_section[str(case["section_ids"][1])]["is_pinned"] is False

    state_before_generate = client.portal.call(_workflow_state, db_session, case)
    assert len(state_before_generate["assignments"]) == 2
    assert all(row["is_active"] for row in state_before_generate["assignments"])
    assert all(
        row["user_id"] == case["pj_id"] for row in state_before_generate["assignments"]
    )
    assignment_audits = []
    for section_id in case["section_ids"]:
        assignment_audits.extend(
            client.portal.call(
                _authority_audit,
                db_session,
                case["pj_id"],
                str(section_id),
                "class_instructor_assignment_%",
            )
        )
    assert len(assignment_audits) == 2
    assert all(
        row["action"] == "class_instructor_assignment_upsert"
        for row in assignment_audits
    )
    assert all(row["old_value"] is None for row in assignment_audits)

    stale_board = client.get(
        f"{BASE}/board", params={"period_id": period_id}, headers=pj_headers
    )
    assert stale_board.status_code == 200, stale_board.text
    stale_classes = {
        item["class_section_id"]: item
        for item in stale_board.json()["data"]["classes"]
        if item["class_section_id"] in section_ids
    }
    assert set(stale_classes) == section_ids
    assert all(item["is_stale"] is True for item in stale_classes.values())
    assert all(item["run_id"] is None for item in stale_classes.values())
    assert all(
        item["assigned_lecturer_id"] == str(case["pj_id"])
        for item in stale_classes.values()
    )

    other_schedule_before = state_before_generate["other_schedule"]
    generated = client.post(
        f"{BASE}/generate",
        json={
            "academic_period_id": period_id,
            "mode": "regenerate",
            "study_program_id": str(case["program_id"]),
        },
        headers=pj_headers,
    )
    assert generated.status_code == 200, generated.text
    generated_body = generated.json()
    run_id = generated_body["run_id"]
    assert generated_body["mode"] == "regenerate"
    assert generated_body["study_program_id"] == str(case["program_id"])
    assert generated_body["assigned_count"] == 2
    assert generated_body["unassigned_count"] == 0
    assert generated_body["conflict_count"] == 0
    assert generated_body["regenerated_count"] == 2
    assert generated_body["preserved_manual_count"] == 0
    assert generated_body["preserved_final_count"] == 0

    state_after_generate = client.portal.call(_workflow_state, db_session, case, run_id)
    assert state_after_generate["other_schedule"] == other_schedule_before
    assert state_after_generate["run"] == {
        "study_program_id": case["program_id"],
        "mode": "regenerate",
        "input_revision": generated_body["input_revision"],
        "status": "completed",
        "triggered_by": case["pj_id"],
    }

    board = client.get(
        f"{BASE}/board", params={"period_id": period_id}, headers=pj_headers
    )
    legacy_board = client.get(
        f"{LEGACY}/scheduling/board", params={"period_id": period_id}, headers=pj_headers
    )
    assert board.status_code == legacy_board.status_code == 200
    assert board.json() == legacy_board.json()
    board_body = board.json()
    assert board_body["data"]["academic_period_id"] == period_id
    board_classes = {
        item["class_section_id"]: item
        for item in board_body["data"]["classes"]
        if item["class_section_id"] in section_ids
    }
    assert set(board_classes) == section_ids
    for item in board_classes.values():
        assert item["course_code"] == case["course_code"]
        assert item["study_program_id"] == str(case["program_id"])
        assert item["study_program_code"] == case["program_code"]
        assert item["assigned_lecturer_id"] == str(case["pj_id"])
        assert item["assigned_lecturer_name"] == case["pj_name"]
        assert item["lecturers"] == [case["pj_name"]]
        assert item["room_id"] == str(case["room_id"])
        assert item["room_code"] == case["room_code"]
        assert item["is_stale"] is False
        assert item["run_id"] == run_id
        assert item["can_edit"] is True
    program_status = next(
        item
        for item in board_body["data"]["programs"]
        if item["study_program_id"] == str(case["program_id"])
    )
    assert program_status["is_stale"] is False
    assert program_status["run_id"] == run_id

    dashboard = client.get(f"{V1}/dashboard/me", headers=pj_headers)
    assert dashboard.status_code == 200, dashboard.text
    dashboard_body = dashboard.json()
    assert dashboard_body["academic_period_id"] == period_id
    assert {item["class_section_id"] for item in dashboard_body["assigned_classes"]} == (
        section_ids
    )
    assert dashboard_body["unscheduled_classes"] == []
    assert dashboard_body["stats"] == {
        "type": "lecturer",
        "assigned_classes": 2,
        "scheduled_classes": 2,
        "unscheduled_classes": 0,
    }
    assert dashboard_body["preference"] == {
        "academic_period_id": period_id,
        "status": "filled",
        "preferred_count": 1,
        "unavailable_count": 0,
        "deadline": None,
        "deadline_scope": None,
    }
    dashboard_schedules = {
        item["class_section_id"]: item for item in dashboard_body["schedule"]
    }
    assert set(dashboard_schedules) == section_ids
    for section_id, item in dashboard_schedules.items():
        board_item = board_classes[section_id]
        assert item["course_code"] == case["course_code"]
        assert item["assignment_id"] == saved_by_section[section_id]["assignment_id"]
        assert item["day_of_week"] == board_item["day_of_week"]
        assert item["start_time"] == f"{board_item['start_hour']:02d}:00"
        assert item["end_time"] == f"{board_item['end_hour']:02d}:00"
        assert item["room"] == case["room_code"]
        assert item["schedule_state"] == "draft"

    finalized = client.post(f"{BASE}/periods/{period_id}/finalize", headers=pj_headers)
    assert finalized.status_code == 200, finalized.text
    finalized_body = finalized.json()
    assert finalized_body["study_program_id"] == str(case["program_id"])
    assert finalized_body["state"] == "final"
    assert finalized_body["all_final"] is False
    assert finalized_body["completeness"] == {
        "classes": {"total": 2, "scheduled": 2},
        "preferences": {
            "expected": 1,
            "submitted": 1,
            "complete": 1,
            "missing_user_ids": [],
        },
    }
    outside_warnings = [
        warning
        for warning in finalized_body["warnings"]
        if warning["code"] == "outside_preferred_window"
    ]
    assert {warning["class_section_id"] for warning in outside_warnings} == section_ids
    assert all(warning["user_id"] == str(case["pj_id"]) for warning in outside_warnings)

    state_final = client.portal.call(_workflow_state, db_session, case, run_id)
    assert state_final["status"]["state"] == "final"
    assert state_final["status"]["finalized_by"] == case["pj_id"]
    finalize_logs = [row for row in state_final["logs"] if row["reason"] == "finalize"]
    assert {row["class_section_id"] for row in finalize_logs} == {
        case["section_ids"][0],
        case["section_ids"][1],
    }
    assert all(row["changed_by"] == case["pj_id"] for row in finalize_logs)
    assert all(row["after_state"]["warnings"] for row in finalize_logs)
    assert all(
        row["after_state"]["completeness"] == finalized_body["completeness"]
        for row in finalize_logs
    )

    locked_preference = client.put(
        f"{BASE}/preferences/me",
        params={"academic_period_id": period_id},
        json=preference_payload,
        headers=pj_headers,
    )
    assert locked_preference.status_code == 409, locked_preference.text
    assert locked_preference.json()["error"]["code"] == "schedule_final"
    final_board = client.get(
        f"{BASE}/board", params={"period_id": period_id}, headers=pj_headers
    )
    assert final_board.status_code == 200, final_board.text
    assert all(
        item["state"] == "final"
        for item in final_board.json()["data"]["classes"]
        if item["class_section_id"] in section_ids
    )
    final_dashboard = client.get(f"{V1}/dashboard/me", headers=pj_headers)
    assert final_dashboard.status_code == 200, final_dashboard.text
    assert all(
        item["schedule_state"] == "final"
        for item in final_dashboard.json()["schedule"]
    )

    pj_unlock = client.post(
        f"{BASE}/periods/{period_id}/unlock",
        json={"reason": "Pembukaan oleh PJ", "confirm": True},
        headers=pj_headers,
    )
    assert pj_unlock.status_code == 403, pj_unlock.text
    blank_unlock = client.post(
        f"{BASE}/periods/{period_id}/unlock",
        json={"reason": "   ", "confirm": True},
        headers=admin_headers,
    )
    assert blank_unlock.status_code == 422, blank_unlock.text
    assert blank_unlock.json()["error"]["details"][0]["field"] == "reason"

    unlock_reason = "Pembukaan workflow terintegrasi"
    unlocked = client.post(
        f"{BASE}/periods/{period_id}/unlock",
        json={"reason": unlock_reason, "confirm": True},
        headers=admin_headers,
    )
    assert unlocked.status_code == 200, unlocked.text
    assert unlocked.json()["state"] == "in_progress"
    assert unlocked.json()["unlocked_count"] == 1
    assert unlocked.json()["audit_count"] == 3

    state_unlocked = client.portal.call(_workflow_state, db_session, case, run_id)
    assert state_unlocked["status"]["state"] == "in_progress"
    assert state_unlocked["status"]["finalized_by"] is None
    assert state_unlocked["status"]["finalized_at"] is None
    assert state_unlocked["lock"]["krs_open"] is False
    assert state_unlocked["lock"]["locked_by"] == uuid.UUID(admin_id)
    unlock_logs = [row for row in state_unlocked["logs"] if row["reason"] == unlock_reason]
    assert len(unlock_logs) == 3
    assert all(row["changed_by"] == uuid.UUID(admin_id) for row in unlock_logs)
    assert all(
        row["after_state"] == {"krs_open": False, "state": "in_progress"}
        for row in unlock_logs
    )

    reopened = client.put(
        f"{BASE}/preferences/me",
        params={"academic_period_id": period_id},
        json=preference_payload,
        headers=pj_headers,
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json() == preference_body
