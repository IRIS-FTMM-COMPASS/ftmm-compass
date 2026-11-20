"""Kontrak HTTP untuk ketersediaan dosen, Papan Jadwal Bersama, dan status dashboard."""

import uuid
from datetime import time

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from auth import get_password_hash
from models import (
    ClassSchedule,
    ClassSection,
    CourseOffering,
    LecturerAvailability,
    LecturerProfile,
    OfferingComponent,
    ScheduleProgramStatus,
    StudyProgram,
    User,
)
from scheduling_common import all_study_program_ids, current_period_id, status_label
from tests.conftest import SEEDED_LECTURER, SEEDED_STUDENT

V1 = "/api/v1"
PASSWORD = "JadwalUji2026!"
SLOTS = [
    {"day_of_week": 1, "start_hour": 8, "end_hour": 10},
    {"day_of_week": 2, "start_hour": 13, "end_hour": 15},
]


def test_availability_requires_authentication(client):
    assert client.put(f"{V1}/scheduling/availability/me", json=SLOTS).status_code == 401
    assert client.get(f"{V1}/scheduling/availability/me").status_code == 401
    assert client.get(f"{V1}/scheduling/board").status_code == 401
    assert client.get(f"{V1}/scheduling/conflicts").status_code == 401


def test_availability_put_replaces_slots_and_ignores_foreign_user_id(
    client, db_session, lecturer_headers
):
    lecturer_id = client.portal.call(_user_id, db_session, SEEDED_LECTURER[0])
    foreign_id = client.portal.call(
        _user_id, db_session, "mahasiswa.testing@ftmm.unair.ac.id"
    )

    payload = [{**slot, "user_id": str(foreign_id)} for slot in SLOTS]
    response = client.put(
        f"{V1}/scheduling/availability/me",
        json={"slots": payload},
        headers=lecturer_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["data"]) == 2
    assert {slot["user_id"] for slot in body["data"]} == {str(lecturer_id)}
    assert body["data"][0]["day_name"] == "Senin"
    assert body["meta"]["count"] == 2

    replacement = client.put(
        f"{V1}/scheduling/availability/me", json=[SLOTS[0]], headers=lecturer_headers
    )
    assert replacement.status_code == 200, replacement.text
    assert [slot["start_hour"] for slot in replacement.json()["data"]] == [8]

    current = client.get(f"{V1}/scheduling/availability/me", headers=lecturer_headers)
    assert current.status_code == 200
    assert len(current.json()["data"]) == 1


def test_availability_rejects_invalid_ranges_and_overlaps(client, lecturer_headers):
    invalid_cases = (
        [{"day_of_week": 6, "start_hour": 8, "end_hour": 10}],
        [{"day_of_week": 1, "start_hour": 8, "end_hour": 8}],
        [{"day_of_week": 1, "start_hour": 6, "end_hour": 9}],
        [{"day_of_week": 1, "start_hour": 9, "end_hour": 18}],
    )
    for slots in invalid_cases:
        response = client.put(
            f"{V1}/scheduling/availability/me", json=slots, headers=lecturer_headers
        )
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "validation_error"

    overlap = client.put(
        f"{V1}/scheduling/availability/me",
        json=[
            {"day_of_week": 1, "start_hour": 8, "end_hour": 11},
            {"day_of_week": 1, "start_hour": 9, "end_hour": 10},
            {"day_of_week": 2, "start_hour": 8, "end_hour": 10},
        ],
        headers=lecturer_headers,
    )
    assert overlap.status_code == 422, overlap.text
    assert overlap.json()["error"]["code"] == "overlapping_availability"


def test_availability_read_is_scoped_to_admin_or_owning_pj(
    client, db_session, admin_headers, pj_headers, student_headers
):
    target_id, outsider_id = client.portal.call(_create_availability_targets, db_session)

    readable = client.get(f"{V1}/scheduling/availability/{target_id}", headers=pj_headers)
    assert readable.status_code == 200, readable.text
    assert len(readable.json()["data"]) == 1

    outsider = client.get(
        f"{V1}/scheduling/availability/{outsider_id}", headers=pj_headers
    )
    assert outsider.status_code == 403
    assert outsider.json()["error"]["code"] == "forbidden"

    as_admin = client.get(
        f"{V1}/scheduling/availability/{outsider_id}", headers=admin_headers
    )
    assert as_admin.status_code == 200
    assert as_admin.json()["data"]

    as_student = client.get(
        f"{V1}/scheduling/availability/{target_id}", headers=student_headers
    )
    assert as_student.status_code == 403


def test_board_contains_classes_programs_unassigned_and_conflicts(
    client, db_session, admin_headers
):
    section_a, section_b = client.portal.call(_create_overlapping_sections, db_session)

    response = client.get(f"{V1}/scheduling/board", headers=admin_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    data = body["data"]
    assert data["academic_period_id"]
    assert data["period_label"]
    assert len(data["programs"]) == 5
    assert len(body["meta"]) >= 3

    classes = data["classes"]
    assert classes
    assert all(
        {
            "class_section_id",
            "course_code",
            "day_of_week",
            "start_hour",
            "end_hour",
            "state",
        }
        <= set(item)
        for item in classes
    )
    assert {item["study_program_code"] for item in classes} <= {
        item["study_program_code"] for item in data["programs"]
    } | {""}
    assert isinstance(data["unassigned"], list)

    ids = {section_a, section_b}
    room_conflicts = [
        item
        for item in data["conflicts"]
        if item["class_section_a_id"] in ids and item["kind"] == "room"
    ]
    assert room_conflicts
    assert room_conflicts[0]["day_of_week"] == 1
    assert room_conflicts[0]["start_hour"] == 9
    assert room_conflicts[0]["end_hour"] == 10

    conflicts = client.get(f"{V1}/scheduling/conflicts", headers=admin_headers)
    assert conflicts.status_code == 200, conflicts.text
    assert conflicts.json()["data"] == data["conflicts"]

    statuses = client.portal.call(_status_rows, db_session)
    assert len(statuses) >= 5
    assert all(state == "draft" for state in statuses.values())


def test_board_rejects_unknown_period(client, admin_headers):
    response = client.get(
        f"{V1}/scheduling/board",
        params={"period_id": str(uuid.uuid4())},
        headers=admin_headers,
    )
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "period_not_found"

    conflicts = client.get(
        f"{V1}/scheduling/conflicts",
        params={"period_id": "bukan-uuid"},
        headers=admin_headers,
    )
    assert conflicts.status_code == 404
    assert conflicts.json()["error"]["code"] == "period_not_found"


def test_dashboard_exposes_schedule_status(
    client, student_headers, lecturer_headers, db_session
):
    for headers in (student_headers, lecturer_headers):
        response = client.get(f"{V1}/dashboard/me", headers=headers)
        assert response.status_code == 200, response.text
        status = response.json().get("schedule_status")
        assert isinstance(status, str)
        assert status == status_label("draft")

    client.portal.call(_finalize_student_program, db_session)
    partial = client.get(f"{V1}/dashboard/me", headers=student_headers)
    assert partial.status_code == 200
    assert partial.json()["schedule_status"] == status_label("draft")

    client.portal.call(_finalize_all_programs, db_session)
    finalized = client.get(f"{V1}/dashboard/me", headers=student_headers)
    assert finalized.status_code == 200
    assert finalized.json()["schedule_status"] == status_label("final")


async def _user_id(db_session, email):
    return (
        await db_session.execute(select(User.user_id).where(User.email == email))
    ).scalar_one()


async def _create_availability_targets(db_session):
    programs = (
        await db_session.execute(
            select(StudyProgram).order_by(StudyProgram.program_code)
        )
    ).scalars().all()
    pj = (
        await db_session.execute(
            select(LecturerProfile).where(
                LecturerProfile.user_id.in_(
                    select(User.user_id).where(User.email == SEEDED_LECTURER[0])
                )
            )
        )
    ).scalars().one()
    own_program = pj.study_program_id
    other_program = next(
        program.study_program_id
        for program in programs
        if program.study_program_id != own_program
    )

    created = []
    for program_id in (own_program, other_program):
        user = User(
            email=f"availability.{uuid.uuid4().hex[:10]}@ftmm.unair.ac.id",
            full_name="Dosen Uji Ketersediaan",
            password_hash=get_password_hash(PASSWORD),
            role="lecturer",
        )
        db_session.add(user)
        await db_session.flush()
        db_session.add(
            LecturerProfile(
                user_id=user.user_id,
                study_program_id=program_id,
                is_program_coordinator=False,
            )
        )
        db_session.add(
            LecturerAvailability(
                user_id=user.user_id,
                day_of_week=3,
                start_hour=10,
                end_hour=12,
            )
        )
        created.append(str(user.user_id))
    await db_session.commit()
    return created[0], created[1]


async def _create_overlapping_sections(db_session):
    period_id = await current_period_id(db_session)
    source = (
        await db_session.execute(
            select(
                ClassSection.offering_component_id, CourseOffering.course_offering_id
            )
            .join(
                OfferingComponent,
                OfferingComponent.offering_component_id
                == ClassSection.offering_component_id,
            )
            .join(
                CourseOffering,
                CourseOffering.course_offering_id
                == OfferingComponent.course_offering_id,
            )
            .where(CourseOffering.academic_period_id == period_id)
            .limit(1)
        )
    ).first()
    assert source is not None, "seed harus memuat kelas pada periode aktif"

    suffix = uuid.uuid4().hex[:6]
    sections = [
        ClassSection(
            offering_component_id=source.offering_component_id,
            section_code=f"KONFLIK-{label}-{suffix}",
            capacity=20,
        )
        for label in ("A", "B")
    ]
    db_session.add_all(sections)
    await db_session.flush()
    room_name = f"Ruang Uji Konflik {suffix}"
    db_session.add_all(
        [
            ClassSchedule(
                class_section_id=sections[0].class_section_id,
                day_of_week=1,
                start_time=time(8, 0),
                end_time=time(10, 0),
                room_name=room_name,
            ),
            ClassSchedule(
                class_section_id=sections[1].class_section_id,
                day_of_week=1,
                start_time=time(9, 0),
                end_time=time(11, 0),
                room_name=room_name,
            ),
        ]
    )
    await db_session.commit()
    return str(sections[0].class_section_id), str(sections[1].class_section_id)


async def _status_rows(db_session):
    period_id = await current_period_id(db_session)
    rows = (
        await db_session.execute(
            select(ScheduleProgramStatus.study_program_id, ScheduleProgramStatus.state)
            .where(ScheduleProgramStatus.academic_period_id == period_id)
        )
    ).all()
    return {str(row.study_program_id): row.state for row in rows}


async def _finalize_student_program(db_session):
    period_id = await current_period_id(db_session)
    user = (
        await db_session.execute(
            select(User)
            .options(selectinload(User.student_profile))
            .where(User.email == SEEDED_STUDENT[0])
        )
    ).scalars().one()
    program_id = user.student_profile.study_program_id
    row = (
        await db_session.execute(
            select(ScheduleProgramStatus).where(
                ScheduleProgramStatus.academic_period_id == period_id,
                ScheduleProgramStatus.study_program_id == program_id,
            )
        )
    ).scalars().first()
    if row is None:
        db_session.add(
            ScheduleProgramStatus(
                academic_period_id=period_id,
                study_program_id=program_id,
                state="final",
            )
        )
    else:
        row.state = "final"
    await db_session.commit()


async def _finalize_all_programs(db_session):
    period_id = await current_period_id(db_session)
    for program_id in await all_study_program_ids(db_session):
        row = (
            await db_session.execute(
                select(ScheduleProgramStatus).where(
                    ScheduleProgramStatus.academic_period_id == period_id,
                    ScheduleProgramStatus.study_program_id == program_id,
                )
            )
        ).scalars().first()
        if row is None:
            db_session.add(
                ScheduleProgramStatus(
                    academic_period_id=period_id,
                    study_program_id=program_id,
                    state="final",
                )
            )
        else:
            row.state = "final"
    await db_session.commit()
