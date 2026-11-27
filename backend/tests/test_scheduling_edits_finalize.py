"""Regresi HTTP: edit jadwal, bentrok, finalisasi per prodi, dan unlock."""

import uuid
from datetime import datetime, time, timezone

import pytest
from sqlalchemy import delete, select, update

from models import (
    AcademicPeriod,
    ClassInstructorAssignment,
    ClassSchedule,
    ClassSection,
    Course,
    CourseInstructorReference,
    CourseOffering,
    CourseOfferingEligibility,
    Curriculum,
    CurriculumCourse,
    LecturerProfile,
    OfferingComponent,
    Room,
    ScheduleEditLog,
    SchedulePeriodLock,
    ScheduleProgramStatus,
    ScheduleRun,
    StudyProgram,
    Timetable,
    TimetableItem,
    User,
)
from rate_limit import limiter

V1 = "/api/v1"
BASE = f"{V1}/scheduling"
PJ_PASSWORD = "PjProdi2026!"
OTHER_PRODI_PJ = ("asif.ali@ftmm.unair.ac.id", PJ_PASSWORD)


def _headers(client, identifier: str, password: str) -> dict[str, str]:
    limiter.reset()
    response = client.post(
        f"{V1}/auth/login",
        json={"identifier": identifier, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def other_pj_headers(client) -> dict[str, str]:
    return _headers(client, *OTHER_PRODI_PJ)


@pytest.fixture
def scheduling_data(client, db_session):
    """Tiga kelas uji (dua TSD, satu TRKB) pada periode aktif."""
    suffix = uuid.uuid4().hex[:10].upper()

    async def setup():
        period = (
            await db_session.execute(
                select(AcademicPeriod)
                .where(AcademicPeriod.is_active.is_(True))
                .order_by(AcademicPeriod.academic_year_start.desc())
            )
        ).scalars().first()
        assert period is not None

        seeded_offerings = select(CourseOffering.course_offering_id).where(
            CourseOffering.academic_period_id == period.academic_period_id
        )
        seeded_components = select(OfferingComponent.offering_component_id).where(
            OfferingComponent.course_offering_id.in_(seeded_offerings)
        )
        seeded_sections = select(ClassSection.class_section_id).where(
            ClassSection.offering_component_id.in_(seeded_components)
        )
        await db_session.execute(
            update(Timetable)
            .where(Timetable.academic_period_id == period.academic_period_id)
            .values(is_active=False)
        )
        await db_session.execute(
            delete(TimetableItem).where(
                TimetableItem.class_section_id.in_(seeded_sections)
            )
        )
        await db_session.execute(
            delete(ClassSchedule).where(
                ClassSchedule.class_section_id.in_(seeded_sections)
            )
        )
        await db_session.execute(
            delete(ClassSection).where(
                ClassSection.class_section_id.in_(seeded_sections)
            )
        )
        await db_session.execute(
            delete(OfferingComponent).where(
                OfferingComponent.offering_component_id.in_(seeded_components)
            )
        )
        await db_session.execute(
            delete(CourseOfferingEligibility).where(
                CourseOfferingEligibility.course_offering_id.in_(seeded_offerings)
            )
        )
        await db_session.execute(
            delete(CourseOffering).where(
                CourseOffering.course_offering_id.in_(seeded_offerings)
            )
        )
        await db_session.execute(
            delete(ScheduleProgramStatus).where(
                ScheduleProgramStatus.academic_period_id == period.academic_period_id
            )
        )
        await db_session.execute(
            delete(SchedulePeriodLock).where(
                SchedulePeriodLock.academic_period_id == period.academic_period_id
            )
        )

        programs = {
            row.program_code: row
            for row in (
                await db_session.execute(
                    select(StudyProgram).where(
                        StudyProgram.program_code.in_(("TSD", "TRKB", "RN", "TI", "TE"))
                    )
                )
            ).scalars().all()
        }

        rooms = {}
        for label, owner_code, capacity in (
            ("A", "TSD", 60),
            ("B", "TSD", 60),
            ("TRKB", "TRKB", 60),
            ("SMALL", "TSD", 5),
        ):
            room = Room(
                room_code=f"UJI-{label}-{suffix}",
                capacity=capacity,
                owner_study_program_id=programs[owner_code].study_program_id,
                is_active=True,
            )
            db_session.add(room)
            rooms[label] = room
        await db_session.flush()

        curricula = {}
        for code in ("TSD", "TRKB"):
            curriculum = Curriculum(
                study_program_id=programs[code].study_program_id,
                curriculum_name=f"Kurikulum Uji {code} {suffix}",
                curriculum_year=2099,
                is_active=True,
            )
            db_session.add(curriculum)
            curricula[code] = curriculum
        await db_session.flush()

        def new_course(code: str, label: str):
            course = Course(
                course_code=code,
                course_name=f"MK Uji {label} {suffix}",
                is_active=True,
            )
            db_session.add(course)
            return course

        course_tsd = new_course(f"UJ{uuid.uuid4().int % 10000:04d}", "TSD")
        course_trkb = new_course(f"UK{uuid.uuid4().int % 10000:04d}", "TRKB")
        await db_session.flush()

        credits = {}
        for code, course in (("TSD", course_tsd), ("TRKB", course_trkb)):
            curriculum_course = CurriculumCourse(
                curriculum_id=curricula[code].curriculum_id,
                course_id=course.course_id,
                credits_total=2,
                recommended_semester=3,
                term="ganjil",
                course_type="wajib",
            )
            db_session.add(curriculum_course)
            credits[code] = curriculum_course
        await db_session.flush()

        def new_offering(course, label):
            offering = CourseOffering(
                academic_period_id=period.academic_period_id,
                course_id=course.course_id,
                offering_code=f"{label}-{suffix}",
            )
            db_session.add(offering)
            return offering

        offering_tsd = new_offering(course_tsd, "UJITSD")
        offering_trkb = new_offering(course_trkb, "UJIRKB")
        await db_session.flush()
        for offering, credit_row in (
            (offering_tsd, credits["TSD"]),
            (offering_trkb, credits["TRKB"]),
        ):
            db_session.add(
                CourseOfferingEligibility(
                    course_offering_id=offering.course_offering_id,
                    curriculum_course_id=credit_row.curriculum_course_id,
                )
            )
        await db_session.flush()

        component_tsd = OfferingComponent(
            course_offering_id=offering_tsd.course_offering_id,
            component_code="KULIAH",
            component_type="lecture",
        )
        component_trkb = OfferingComponent(
            course_offering_id=offering_trkb.course_offering_id,
            component_code="KULIAH",
            component_type="lecture",
        )
        db_session.add_all([component_tsd, component_trkb])
        await db_session.flush()

        section_a = ClassSection(
            offering_component_id=component_tsd.offering_component_id,
            section_code="A",
            capacity=40,
        )
        section_b = ClassSection(
            offering_component_id=component_tsd.offering_component_id,
            section_code="B",
            capacity=40,
        )
        section_c = ClassSection(
            offering_component_id=component_trkb.offering_component_id,
            section_code="A",
            capacity=40,
        )
        db_session.add_all([section_a, section_b, section_c])
        await db_session.flush()

        db_session.add_all(
            [
                ClassSchedule(
                    class_section_id=section_a.class_section_id,
                    day_of_week=1,
                    start_time=time(8, 0),
                    end_time=time(10, 0),
                    room_id=rooms["A"].room_id,
                    room_name=rooms["A"].room_code,
                ),
                ClassSchedule(
                    class_section_id=section_b.class_section_id,
                    day_of_week=2,
                    start_time=time(8, 0),
                    end_time=time(10, 0),
                    room_id=rooms["B"].room_id,
                    room_name=rooms["B"].room_code,
                ),
                ClassSchedule(
                    class_section_id=section_c.class_section_id,
                    day_of_week=3,
                    start_time=time(8, 0),
                    end_time=time(10, 0),
                    room_id=rooms["TRKB"].room_id,
                    room_name=rooms["TRKB"].room_code,
                ),
            ]
        )
        for code in ("TSD", "TRKB"):
            db_session.add(
                ScheduleProgramStatus(
                    academic_period_id=period.academic_period_id,
                    study_program_id=programs[code].study_program_id,
                    state="draft",
                )
            )
        for code in ("RN", "TI", "TE"):
            db_session.add(
                ScheduleProgramStatus(
                    academic_period_id=period.academic_period_id,
                    study_program_id=programs[code].study_program_id,
                    state="final",
                )
            )
        lecturer_rows = (
            await db_session.execute(
                select(User, LecturerProfile)
                .join(
                    LecturerProfile,
                    LecturerProfile.user_id == User.user_id,
                )
                .where(
                    LecturerProfile.study_program_id.in_(
                        [programs["TSD"].study_program_id, programs["TRKB"].study_program_id]
                    ),
                    User.role == "lecturer",
                    User.is_active.is_(True),
                )
                .order_by(User.user_id)
            )
        ).all()
        lecturer_by_program = {
            row.LecturerProfile.study_program_id: row.User
            for row in lecturer_rows
        }
        for code in ("TSD", "TRKB"):
            lecturer = lecturer_by_program[programs[code].study_program_id]
            db_session.add(
                CourseInstructorReference(
                    curriculum_course_id=credits[code].curriculum_course_id,
                    academic_period_id=period.academic_period_id,
                    instructor_name=lecturer.full_name,
                    instructor_role="pjmk",
                    user_id=lecturer.user_id,
                    position=1,
                )
            )
        for section, code in (
            (section_a, "TSD"),
            (section_b, "TSD"),
            (section_c, "TRKB"),
        ):
            db_session.add(
                ClassInstructorAssignment(
                    class_section_id=section.class_section_id,
                    academic_period_id=period.academic_period_id,
                    user_id=lecturer_by_program[
                        programs[code].study_program_id
                    ].user_id,
                    source="manual",
                    is_pinned=True,
                    is_active=True,
                    assigned_by=lecturer_by_program[
                        programs[code].study_program_id
                    ].user_id,
                )
            )
        now = datetime.now(timezone.utc)
        db_session.add(
            ScheduleRun(
                academic_period_id=period.academic_period_id,
                mode="fill_empty",
                input_revision=0,
                status="completed",
                stats={},
                started_at=now,
                ended_at=now,
            )
        )
        await db_session.flush()

        return {
            "period_id": str(period.academic_period_id),
            "section_a": str(section_a.class_section_id),
            "section_b": str(section_b.class_section_id),
            "section_c": str(section_c.class_section_id),
            "room_a": str(rooms["A"].room_id),
            "room_b": str(rooms["B"].room_id),
            "room_trkb": str(rooms["TRKB"].room_id),
            "room_small": str(rooms["SMALL"].room_id),
            "program_tsd": str(programs["TSD"].study_program_id),
            "program_trkb": str(programs["TRKB"].study_program_id),
        }

    return client.portal.call(setup)


def _move_payload(data, *, room_id=None, day=1, start=8, reason="Perbaikan jadwal"):
    return {
        "day_of_week": day,
        "start_hour": start,
        "room_id": room_id or data["room_a"],
        "reason": reason,
    }


def test_move_denied_for_pj_of_other_prodi(client, other_pj_headers, scheduling_data):
    response = client.patch(
        f"{BASE}/classes/{scheduling_data['section_a']}",
        json=_move_payload(scheduling_data),
        headers=other_pj_headers,
    )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "akses_prodi_ditolak"


def test_conflicting_move_is_saved_reported_and_audited(
    client, pj_headers, db_session, scheduling_data
):
    data = scheduling_data
    response = client.patch(
        f"{BASE}/classes/{data['section_a']}",
        json=_move_payload(data, room_id=data["room_b"], day=2, start=9),
        headers=pj_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["class"]["class_section_id"] == data["section_a"]
    assert body["class"]["day_of_week"] == 2
    assert body["class"]["start_hour"] == 9
    assert body["class"]["end_hour"] == 11
    conflict_sections = {
        item["class_section_a_id"] for item in body["conflicts"]
    } | {item["class_section_b_id"] for item in body["conflicts"]}
    assert conflict_sections == {data["section_a"], data["section_b"]}
    assert any(item["kind"] == "room" for item in body["conflicts"])
    assert body["class"]["assigned_lecturer_id"]
    assert body["class"]["assigned_lecturer_name"] in body["class"]["lecturers"]
    assert body["class"]["can_edit"] is True
    assert body["class"]["read_only"] is False

    async def inspect():
        schedule = (
            await db_session.execute(
                select(ClassSchedule).where(
                    ClassSchedule.class_section_id == uuid.UUID(data["section_a"])
                )
            )
        ).scalars().first()
        assert schedule.day_of_week == 2
        assert schedule.start_time == time(9, 0)
        assert str(schedule.room_id) == data["room_b"]
        log = (
            await db_session.execute(
                select(ScheduleEditLog).where(
                    ScheduleEditLog.class_section_id == uuid.UUID(data["section_a"])
                )
            )
        ).scalars().first()
        assert log is not None
        assert log.reason == "Perbaikan jadwal"
        assert log.changed_by is not None
        assert log.before_state["start_hour"] == 8
        assert log.after_state["start_hour"] == 9
        assert log.after_state["room_id"] == data["room_b"]

    client.portal.call(inspect)


def test_move_denied_for_room_of_other_prodi(client, pj_headers, scheduling_data):
    data = scheduling_data
    response = client.patch(
        f"{BASE}/classes/{data['section_a']}",
        json=_move_payload(data, room_id=data["room_trkb"]),
        headers=pj_headers,
    )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "invalid_room_owner"


@pytest.mark.parametrize(
    ("field", "override", "expected_detail"),
    [
        ("room_id", {"room_id": "SMALL"}, "insufficient_capacity"),
        ("start_hour", {"start": 16}, "invalid_time_block"),
        ("reason", {"reason": "   "}, "required"),
    ],
)
def test_move_validates_capacity_block_and_reason(
    client, pj_headers, scheduling_data, field, override, expected_detail
):
    data = scheduling_data
    payload = _move_payload(data, **override)
    if override.get("room_id") == "SMALL":
        payload["room_id"] = data[f"room_{override['room_id'].lower()}"]
    response = client.patch(
        f"{BASE}/classes/{data['section_a']}",
        json=payload,
        headers=pj_headers,
    )
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["details"][0]["field"] == field
    assert body["error"]["details"][0]["code"] == expected_detail


def test_finalize_blocked_by_conflict_and_scoped_to_own_prodi(
    client, pj_headers, other_pj_headers, db_session, scheduling_data
):
    data = scheduling_data

    async def make_conflict():
        schedule = (
            await db_session.execute(
                select(ClassSchedule).where(
                    ClassSchedule.class_section_id == uuid.UUID(data["section_b"])
                )
            )
        ).scalars().first()
        schedule.day_of_week = 1
        schedule.start_time = time(9, 0)
        schedule.end_time = time(11, 0)
        schedule.room_id = uuid.UUID(data["room_a"])
        await db_session.flush()

    client.portal.call(make_conflict)

    blocked = client.post(
        f"{BASE}/periods/{data['period_id']}/finalize", headers=pj_headers
    )
    assert blocked.status_code == 422, blocked.text
    assert blocked.json()["error"]["code"] == "conflicts_exist"

    allowed = client.post(
        f"{BASE}/periods/{data['period_id']}/finalize", headers=other_pj_headers
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["study_program_id"] == data["program_trkb"]
    assert allowed.json()["all_final"] is False


def test_finalize_per_program_all_final_and_krs_lock(
    client, pj_headers, other_pj_headers, scheduling_data
):
    data = scheduling_data
    first = client.post(
        f"{BASE}/periods/{data['period_id']}/finalize", headers=pj_headers
    )
    assert first.status_code == 200, first.text
    assert first.json()["study_program_id"] == data["program_tsd"]
    assert first.json()["all_final"] is False

    locked_by_status = client.patch(
        f"{BASE}/classes/{data['section_a']}",
        json=_move_payload(data),
        headers=pj_headers,
    )
    assert locked_by_status.status_code == 409, locked_by_status.text
    assert locked_by_status.json()["error"]["code"] == "schedule_final"

    second = client.post(
        f"{BASE}/periods/{data['period_id']}/finalize", headers=other_pj_headers
    )
    assert second.status_code == 200, second.text
    assert second.json()["all_final"] is True

    locked_by_krs = client.patch(
        f"{BASE}/classes/{data['section_c']}",
        json=_move_payload(data, room_id=data["room_trkb"], day=4),
        headers=other_pj_headers,
    )
    assert locked_by_krs.status_code == 409, locked_by_krs.text
    assert locked_by_krs.json()["error"]["code"] == "krs_open"


def test_unlock_requires_reason_and_resets_final_statuses(
    client, admin_headers, pj_headers, other_pj_headers, db_session, scheduling_data
):
    data = scheduling_data
    for headers in (pj_headers, other_pj_headers):
        response = client.post(
            f"{BASE}/periods/{data['period_id']}/finalize", headers=headers
        )
        assert response.status_code == 200, response.text
        assert response.json()["all_final"] is (headers is other_pj_headers)

    blank = client.post(
        f"{BASE}/periods/{data['period_id']}/unlock",
        json={"reason": "   ", "confirm": True},
        headers=admin_headers,
    )
    assert blank.status_code == 422, blank.text
    assert blank.json()["error"]["details"][0]["field"] == "reason"

    forbidden = client.post(
        f"{BASE}/periods/{data['period_id']}/unlock",
        json={"reason": "Perbaikan jadwal"},
        headers=pj_headers,
    )
    assert forbidden.status_code == 403, forbidden.text

    unlocked = client.post(
        f"{BASE}/periods/{data['period_id']}/unlock",
        json={"reason": "Perbaikan jadwal", "confirm": True},
        headers=admin_headers,
    )
    assert unlocked.status_code == 200, unlocked.text

    async def inspect():
        lock = await db_session.get(
            SchedulePeriodLock, uuid.UUID(data["period_id"])
        )
        assert lock is not None and lock.krs_open is False
        statuses = (
            await db_session.execute(
                select(ScheduleProgramStatus).where(
                    ScheduleProgramStatus.academic_period_id
                    == uuid.UUID(data["period_id"])
                )
            )
        ).scalars().all()
        assert {row.state for row in statuses} == {"in_progress"}
        logs = (
            await db_session.execute(
                select(ScheduleEditLog).where(
                    ScheduleEditLog.class_section_id.in_(
                        {
                            uuid.UUID(data["section_a"]),
                            uuid.UUID(data["section_b"]),
                            uuid.UUID(data["section_c"]),
                        }
                    ),
                    ScheduleEditLog.reason == "Perbaikan jadwal",
                )
            )
        ).scalars().all()
        assert all(log.reason == "Perbaikan jadwal" for log in logs)
        assert len(logs) >= 3

    client.portal.call(inspect)

    editable = client.patch(
        f"{BASE}/classes/{data['section_a']}",
        json=_move_payload(data),
        headers=pj_headers,
    )
    assert editable.status_code == 200, editable.text


def test_admin_can_move_class_without_pj_profile(client, admin_headers, scheduling_data):
    response = client.patch(
        f"{BASE}/classes/{scheduling_data['section_a']}",
        json=_move_payload(scheduling_data, day=4),
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["class"]["day_of_week"] == 4


def test_student_cannot_move_class(client, student_headers, scheduling_data):
    response = client.patch(
        f"{BASE}/classes/{scheduling_data['section_a']}",
        json=_move_payload(scheduling_data),
        headers=student_headers,
    )
    assert response.status_code == 403, response.text


def test_edit_log_scoped_by_role_and_program(
    client, admin_headers, pj_headers, other_pj_headers, student_headers, scheduling_data
):
    data = scheduling_data
    moved_own = client.patch(
        f"{BASE}/classes/{data['section_a']}",
        json=_move_payload(data, room_id=data["room_a"], day=4, start=8),
        headers=pj_headers,
    )
    assert moved_own.status_code == 200, moved_own.text
    moved_other = client.patch(
        f"{BASE}/classes/{data['section_c']}",
        json=_move_payload(data, room_id=data["room_trkb"], day=5, start=9),
        headers=other_pj_headers,
    )
    assert moved_other.status_code == 200, moved_other.text

    params = {"period_id": data["period_id"]}
    admin = client.get(f"{BASE}/edit-log", params=params, headers=admin_headers)
    assert admin.status_code == 200, admin.text
    admin_body = admin.json()
    assert admin_body["meta"]["total"] == len(admin_body["data"])
    admin_sections = {row["class_section_id"] for row in admin_body["data"]}
    assert {data["section_a"], data["section_c"]} <= admin_sections

    sample = next(
        row for row in admin_body["data"]
        if row["class_section_id"] == data["section_a"]
    )
    assert sample["reason"] == "Perbaikan jadwal"
    assert uuid.UUID(sample["changed_by"])
    assert sample["changed_by_name"]
    assert sample["before_state"]["start_hour"] == 8
    assert sample["after_state"]["day_of_week"] == 4
    assert sample["created_at"]

    tsd = client.get(f"{BASE}/edit-log", params=params, headers=pj_headers)
    assert tsd.status_code == 200, tsd.text
    tsd_sections = {row["class_section_id"] for row in tsd.json()["data"]}
    assert data["section_a"] in tsd_sections
    assert data["section_c"] not in tsd_sections

    trkb = client.get(f"{BASE}/edit-log", params=params, headers=other_pj_headers)
    assert trkb.status_code == 200, trkb.text
    trkb_sections = {row["class_section_id"] for row in trkb.json()["data"]}
    assert data["section_c"] in trkb_sections
    assert data["section_a"] not in trkb_sections

    denied = client.get(f"{BASE}/edit-log", params=params, headers=student_headers)
    assert denied.status_code == 403, denied.text

    filtered = client.get(
        f"{BASE}/edit-log",
        params={"class_section_id": data["section_c"]},
        headers=admin_headers,
    )
    assert filtered.status_code == 200, filtered.text
    assert {row["class_section_id"] for row in filtered.json()["data"]} == {
        data["section_c"]
    }


def test_edit_log_records_generate_and_full_reset(
    client, admin_headers, scheduling_data
):
    data = scheduling_data
    unlocked = client.post(
        f"{BASE}/periods/{data['period_id']}/unlock",
        json={"reason": "Uji full reset", "confirm": True},
        headers=admin_headers,
    )
    assert unlocked.status_code == 200, unlocked.text
    generated = client.post(
        f"{BASE}/generate",
        json={
            "academic_period_id": data["period_id"],
            "mode": "full_reset",
            "confirm_full_reset": True,
        },
        headers=admin_headers,
    )
    assert generated.status_code == 200, generated.text

    logs = client.get(
        f"{BASE}/edit-log",
        params={"period_id": data["period_id"]},
        headers=admin_headers,
    )
    assert logs.status_code == 200, logs.text
    body = logs.json()
    reasons = {row["reason"] for row in body["data"]}
    assert {"full_reset", "generate"} <= reasons

    deletion = next(
        row for row in body["data"]
        if row["reason"] == "full_reset"
        and row["class_section_id"] == data["section_a"]
    )
    assert deletion["before_state"]["day_of_week"] == 1
    assert deletion["before_state"]["start_hour"] == 8
    assert deletion["after_state"] is None
    assert uuid.UUID(deletion["changed_by"])
    assert deletion["changed_by_name"]

    creation = next(row for row in body["data"] if row["reason"] == "generate")
    assert creation["before_state"] is None
    assert creation["after_state"]["day_of_week"] in range(1, 6)
    assert creation["after_state"]["start_hour"] >= 7
    assert creation["after_state"]["end_hour"] > creation["after_state"]["start_hour"]
    assert creation["after_state"]["room_id"]


def test_edit_log_records_block_normalization(
    client, admin_headers, db_session, scheduling_data
):
    data = scheduling_data

    async def make_partial_hour():
        schedule = (
            await db_session.execute(
                select(ClassSchedule).where(
                    ClassSchedule.class_section_id == uuid.UUID(data["section_a"])
                )
            )
        ).scalars().first()
        assert schedule is not None
        schedule.end_time = time(10, 40)
        await db_session.flush()

    client.portal.call(make_partial_hour)

    generated = client.post(
        f"{BASE}/generate",
        json={
            "academic_period_id": data["period_id"],
            "mode": "fill_empty",
        },
        headers=admin_headers,
    )
    assert generated.status_code == 200, generated.text

    logs = client.get(
        f"{BASE}/edit-log",
        params={"class_section_id": data["section_a"]},
        headers=admin_headers,
    )
    assert logs.status_code == 200, logs.text
    normalized = [
        row for row in logs.json()["data"] if row["reason"] == "normalisasi blok"
    ]
    assert normalized
    assert normalized[0]["before_state"]["end_time"] == "10:40"
    assert normalized[0]["after_state"]["end_time"] == "10:00"
    assert normalized[0]["changed_by_name"]

