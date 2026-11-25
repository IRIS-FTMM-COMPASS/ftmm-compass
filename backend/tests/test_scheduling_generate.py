"""Uji HTTP untuk pembangkit jadwal, batas kelas, dan diagnosis."""

import uuid
from datetime import datetime, time, timezone
from typing import Any

import pytest
from sqlalchemy import delete, select, text

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
    ElectiveCourseVote,
    ElectivePollingPeriod,
    LecturerProfile,
    LecturerSchedulePreference,
    OfferingComponent,
    Room,
    SchedulePeriodLock,
    ScheduleProgramStatus,
    StudentProfile,
    StudyProgram,
    User,
)
from scheduling_common import all_study_program_ids, blocks_overlap

PATH = "/api/v1/scheduling"


def _make_case(
    client,
    db_session,
    *,
    course_term=None,
    course_type="wajib",
    course_active=True,
    demand_votes=0,
    capacity=50,
    room_capacity=80,
    room_owner=True,
    instructor=True,
    with_schedule=False,
    extra_section=False,
    shared_lecturer=False,
    credits=3,
    room_count=1,
    pool_size=1,
    pjmk=True,
    with_assignment=True,
    assignment_source="auto",
    is_pinned=False,
    assigned_pool_index=0,
    preferences=None,
    period_id=None,
    new_period=False,
):
    async def setup():
        suffix = uuid.uuid4().hex[:8]
        active_period = (
            await db_session.execute(
                select(AcademicPeriod).where(AcademicPeriod.is_active.is_(True)).limit(1)
            )
        ).scalars().first()
        assert active_period is not None
        if period_id is not None:
            period = await db_session.get(AcademicPeriod, uuid.UUID(str(period_id)))
        elif new_period:
            period = AcademicPeriod(
                academic_year_start=2099,
                semester_number=active_period.semester_number,
                term=active_period.term,
                start_date=active_period.start_date,
                end_date=active_period.end_date,
                is_active=False,
            )
            db_session.add(period)
            await db_session.flush()
        else:
            period = active_period
        assert period is not None

        program = StudyProgram(
            program_code=f"SCH{suffix}",
            program_name=f"Prodi Uji {suffix}",
            degree_level="sarjana",
            is_active=True,
        )
        other_program = StudyProgram(
            program_code=f"OTH{suffix}",
            program_name=f"Prodi Lain {suffix}",
            degree_level="sarjana",
            is_active=True,
        )
        db_session.add_all([program, other_program])
        await db_session.flush()

        curriculum = Curriculum(
            study_program_id=program.study_program_id,
            curriculum_name=f"Kurikulum Uji {suffix}",
            curriculum_year=2024,
            is_active=True,
        )
        db_session.add(curriculum)
        await db_session.flush()

        lecturer = None
        pool_lecturers = []
        if instructor:
            for index in range(pool_size):
                pool_lecturer = User(
                    email=f"pool-{suffix}-{index}@ftmm.unair.ac.id",
                    full_name=f"Dosen Pool {index} {suffix}",
                    role="lecturer",
                    is_active=True,
                )
                db_session.add(pool_lecturer)
                await db_session.flush()
                db_session.add(
                    LecturerProfile(
                        user_id=pool_lecturer.user_id,
                        study_program_id=program.study_program_id,
                    )
                )
                pool_lecturers.append(pool_lecturer)
            lecturer = pool_lecturers[0]

        code = f"SC{uuid.uuid4().int % 10000:04d}"
        course = Course(course_code=code, course_name="Mata Kuliah Uji", is_active=True)
        db_session.add(course)
        await db_session.flush()
        effective_term = (
            ("genap" if period.term == "ganjil" else "ganjil")
            if course_term == "opposite"
            else course_term or period.term
        )
        curriculum_course = CurriculumCourse(
            curriculum_id=curriculum.curriculum_id,
            course_id=course.course_id,
            credits_total=credits,
            recommended_semester=2 if effective_term == "genap" else 1,
            term=effective_term,
            course_type=course_type,
            course_scope="program_studi",
            is_active=course_active,
        )
        db_session.add(curriculum_course)
        await db_session.flush()

        if instructor:
            for index, pool_lecturer in enumerate(pool_lecturers):
                db_session.add(
                    CourseInstructorReference(
                        curriculum_course_id=curriculum_course.curriculum_course_id,
                        academic_period_id=period.academic_period_id,
                        instructor_name=pool_lecturer.full_name,
                        instructor_role=(
                            "pjmk" if pjmk and index == 0 else "teaching_team"
                        ),
                        user_id=pool_lecturer.user_id,
                        position=index + 1,
                    )
                )


        offering = CourseOffering(
            academic_period_id=period.academic_period_id,
            course_id=course.course_id,
            offering_code=f"{code}-SCH",
        )
        db_session.add(offering)
        await db_session.flush()
        if course_term == "opposite":
            await db_session.execute(
                text(
                    "UPDATE course_offerings "
                    "SET is_term_override = true, term_override_reason = 'Uji paritas' "
                    "WHERE course_offering_id = :offering_id"
                ),
                {"offering_id": offering.course_offering_id},
            )
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
        section = ClassSection(
            offering_component_id=component.offering_component_id,
            section_code="A",
            capacity=capacity,
            enrollment_status="open",
        )
        db_session.add(section)
        await db_session.flush()

        room_ids = []
        for index in range(room_count):
            room = Room(
                room_code=f"RUANG-{suffix}-{index}",
                capacity=room_capacity,
                owner_study_program_id=(
                    program.study_program_id if room_owner else other_program.study_program_id
                ),
                is_active=True,
            )
            db_session.add(room)
            await db_session.flush()
            room_ids.append(str(room.room_id))

        extra_section_id = None
        if extra_section:
            second_code = f"SX{uuid.uuid4().int % 10000:04d}"
            second_course = Course(
                course_code=second_code,
                course_name="Mata Kuliah Uji Kedua",
                is_active=True,
            )
            db_session.add(second_course)
            await db_session.flush()
            second_cc = CurriculumCourse(
                curriculum_id=curriculum.curriculum_id,
                course_id=second_course.course_id,
                credits_total=3,
                recommended_semester=2 if period.term == "genap" else 1,
                term=period.term,
                course_type="wajib",
                course_scope="program_studi",
                is_active=True,
            )
            db_session.add(second_cc)
            await db_session.flush()
            second_lecturer = lecturer
            if not shared_lecturer:
                second_lecturer = User(
                    email=f"extra-{suffix}@ftmm.unair.ac.id",
                    full_name=f"Dosen Tambahan {suffix}",
                    role="lecturer",
                    is_active=True,
                )
                db_session.add(second_lecturer)
                await db_session.flush()
                db_session.add(
                    LecturerProfile(
                        user_id=second_lecturer.user_id,
                        study_program_id=program.study_program_id,
                    )
                )
            db_session.add(
                CourseInstructorReference(
                    curriculum_course_id=second_cc.curriculum_course_id,
                    academic_period_id=period.academic_period_id,
                    instructor_name=second_lecturer.full_name,
                    instructor_role="pjmk",
                    user_id=second_lecturer.user_id,
                    position=1,
                )
            )
            second_offering = CourseOffering(
                academic_period_id=period.academic_period_id,
                course_id=second_course.course_id,
                offering_code=f"{second_code}-SCH",
            )
            db_session.add(second_offering)
            await db_session.flush()
            db_session.add(
                CourseOfferingEligibility(
                    course_offering_id=second_offering.course_offering_id,
                    curriculum_course_id=second_cc.curriculum_course_id,
                )
            )
            second_component = OfferingComponent(
                course_offering_id=second_offering.course_offering_id,
                component_code="KULIAH",
                component_type="lecture",
            )
            db_session.add(second_component)
            await db_session.flush()
            second_section = ClassSection(
                offering_component_id=second_component.offering_component_id,
                section_code="A",
                capacity=capacity,
                enrollment_status="open",
            )
            db_session.add(second_section)
            await db_session.flush()
            extra_section_id = str(second_section.class_section_id)

        admin = (
            await db_session.execute(
                select(User).where(User.email == "admin@ftmm.unair.ac.id").limit(1)
            )
        ).scalars().first()
        assert admin is not None
        assignment_id = None
        if instructor and with_assignment:
            assignment = ClassInstructorAssignment(
                class_section_id=section.class_section_id,
                academic_period_id=period.academic_period_id,
                user_id=pool_lecturers[assigned_pool_index].user_id,
                source=assignment_source,
                is_pinned=is_pinned,
                is_active=True,
                assigned_by=admin.user_id,
            )
            db_session.add(assignment)
            await db_session.flush()
            assignment_id = str(assignment.assignment_id)
        for preference in preferences or []:
            pool_lecturer = pool_lecturers[preference["pool_index"]]
            db_session.add(
                LecturerSchedulePreference(
                    user_id=pool_lecturer.user_id,
                    academic_period_id=period.academic_period_id,
                    day_of_week=preference["day"],
                    start_time=time(hour=preference["start"]),
                    end_time=time(hour=preference["end"]),
                    kind=preference["kind"],
                )
            )
        if extra_section:
            db_session.add(
                ClassInstructorAssignment(
                    class_section_id=second_section.class_section_id,
                    academic_period_id=period.academic_period_id,
                    user_id=second_lecturer.user_id,
                    source="auto",
                    is_pinned=False,
                    is_active=True,
                    assigned_by=admin.user_id,
                )
            )

        if demand_votes:
            polling_period = (
                await db_session.execute(
                    select(ElectivePollingPeriod)
                    .where(ElectivePollingPeriod.status == "open")
                    .order_by(ElectivePollingPeriod.created_at.desc())
                    .limit(1)
                )
            ).scalars().first()
            if polling_period is None:
                polling_period = ElectivePollingPeriod(
                    title=f"Polling Uji {suffix}",
                    academic_year=str(period.academic_year_start),
                    target_term=period.term,
                    target_semester=1,
                    start_date=period.start_date or datetime.now(timezone.utc),
                    end_date=period.end_date or datetime.now(timezone.utc),
                    status="open",
                )
                db_session.add(polling_period)
                await db_session.flush()
            for index in range(demand_votes):
                voter = User(
                    email=f"vote-{suffix}-{index}@ftmm.unair.ac.id",
                    full_name=f"Pemilih Uji {index}",
                    role="student",
                    is_active=True,
                )
                db_session.add(voter)
                await db_session.flush()
                db_session.add(
                    ElectiveCourseVote(
                        polling_period_id=polling_period.polling_period_id,
                        user_id=voter.user_id,
                        course_id=str(course.course_id),
                        course_code=code,
                        course_name=course.course_name,
                        credits=3,
                        priority=index % 3 + 1,
                    )
                )

        schedule_id = None

        if with_schedule:
            schedule = ClassSchedule(
                class_section_id=section.class_section_id,
                day_of_week=2,
                start_time=time(hour=9),
                end_time=time(hour=11, minute=30),
                room_name="Ruang Lama",
            )
            db_session.add(schedule)
            await db_session.flush()
            schedule_id = str(schedule.class_schedule_id)

        await db_session.commit()

        return {
            "period_id": str(period.academic_period_id),
            "program_id": str(program.study_program_id),
            "course_id": str(course.course_id),
            "section_id": str(section.class_section_id),
            "extra_section_id": extra_section_id,
            "room_ids": room_ids,
            "schedule_id": schedule_id,
            "assignment_id": assignment_id,
            "lecturer_id": str(lecturer.user_id) if lecturer else None,
            "pool_user_ids": [str(user.user_id) for user in pool_lecturers],
            "pool_names": [user.full_name for user in pool_lecturers],
            "curriculum_course_id": str(curriculum_course.curriculum_course_id),
            "component_id": str(component.offering_component_id),
        }

    return client.portal.call(setup)


def _schedules(client, db_session, section_ids):
    async def read():
        rows = (
            await db_session.execute(
                select(ClassSchedule).where(
                    ClassSchedule.class_section_id.in_(section_ids)
                )
            )
        ).scalars().all()
        return [
            {
                "id": str(row.class_schedule_id),
                "section_id": str(row.class_section_id),
                "day": row.day_of_week,
                "start": row.start_time.hour,
                "end": row.end_time.hour,
                "end_minute": row.end_time.minute,
                "room_id": str(row.room_id) if row.room_id else None,
                "room_name": row.room_name,
            }
            for row in rows
        ]

    return client.portal.call(read)


def _generate(client, headers, **payload):
    return client.post(PATH + "/generate", json=payload, headers=headers)


def _unassigned(body, section_id):
    return next(
        (item for item in body["unassigned"] if item["class_section_id"] == section_id),
        None,
    )


def _section_codes(client, db_session, course_id):
    async def read():
        component_ids = (
            await db_session.execute(
                select(OfferingComponent.offering_component_id)
                .join(
                    CourseOffering,
                    CourseOffering.course_offering_id
                    == OfferingComponent.course_offering_id,
                )
                .where(CourseOffering.course_id == uuid.UUID(course_id))
            )
        ).scalars().all()
        return list(
            (
                await db_session.execute(
                    select(ClassSection.section_code, ClassSection.class_section_id).where(
                        ClassSection.offering_component_id.in_(component_ids)
                    )
                )
            ).all()
        )

    return client.portal.call(read)



def test_generate_assigns_full_hour_block_in_owned_room(client, db_session, admin_headers):
    case = _make_case(client, db_session)

    response = _generate(client, admin_headers, mode="fill_empty")

    assert response.status_code == 200
    body = response.json()
    assert body["assigned"] >= 1
    assert body["assigned"] == body["assigned_count"]
    assert body["unassigned_count"] == len(body["unassigned"])
    assert body["conflict_count"] == len(body["conflicts"])

    schedules = _schedules(client, db_session, [case["section_id"]])
    assert len(schedules) == 1
    schedule = schedules[0]
    assert 1 <= schedule["day"] <= 5
    assert 7 <= schedule["start"] <= 16
    assert schedule["end"] == schedule["start"] + 3
    assert schedule["end_minute"] == 0
    assert schedule["room_id"] in case["room_ids"]


def test_generate_reports_capacity_parity_and_unavailable(
    client, db_session, admin_headers
):
    scenarios = (
        ({"capacity": 100, "room_capacity": 20}, "room_capacity"),
        ({"course_term": "opposite"}, "parity_mismatch"),
        (
            {
                "preferences": [
                    {
                        "pool_index": 0,
                        "day": day,
                        "start": 7,
                        "end": 17,
                        "kind": "unavailable",
                    }
                    for day in range(1, 6)
                ]
            },
            "pool_exhausted",
        ),
    )
    for options, expected_code in scenarios:
        case = _make_case(client, db_session, **options)
        response = _generate(
            client,
            admin_headers,
            mode="fill_empty",
            academic_period_id=case["period_id"],
        )
        assert response.status_code == 200
        item = _unassigned(response.json(), case["section_id"])
        assert item is not None
        assert item["reason_code"] == expected_code
        assert _schedules(client, db_session, [case["section_id"]]) == []



def test_generate_uses_shared_room_when_no_owned_room(client, db_session, admin_headers):
    case = _make_case(client, db_session, room_count=0)
    response = _generate(
        client,
        admin_headers,
        mode="fill_empty",
        academic_period_id=case["period_id"],
    )
    assert response.status_code == 200, response.text
    assert _unassigned(response.json(), case["section_id"]) is None
    schedules = _schedules(client, db_session, [case["section_id"]])
    assert len(schedules) == 1

def test_demand_sets_one_two_and_three_class_sections(
    client, db_session, admin_headers
):
    for votes, expected_codes in (
        (0, {"A"}),
        (41, {"A", "B"}),
        (81, {"A", "B", "C"}),
    ):
        case = _make_case(
            client, db_session, course_type="pilihan", demand_votes=votes
        )
        response = _generate(
            client,
            admin_headers,
            mode="fill_empty",
            academic_period_id=case["period_id"],
        )
        assert response.status_code == 200, response.text
        rows = _section_codes(client, db_session, case["course_id"])
        assert {code for code, _ in rows} == expected_codes, rows
        schedules = _schedules(
            client, db_session, [str(section_id) for _, section_id in rows]
        )
        assert len(schedules) == 1, schedules
        generated_ids = {str(section_id) for _, section_id in rows}
        assert all(
            _unassigned(response.json(), section_id)["reason_code"]
            == "missing_assignment"
            for section_id in generated_ids - {case["section_id"]}
        )


def test_class_count_override_wins_over_demand(client, db_session, admin_headers):
    case = _make_case(client, db_session, course_type="pilihan", demand_votes=81)
    payload = {
        "academic_period_id": case["period_id"],
        "course_id": case["course_id"],
        "study_program_id": case["program_id"],
        "class_count": 1,
    }
    override = client.post(
        PATH + "/class-count-overrides", json=payload, headers=admin_headers
    )
    assert override.status_code == 200, override.text

    generated = _generate(
        client,
        admin_headers,
        mode="fill_empty",
        academic_period_id=case["period_id"],
    )
    assert generated.status_code == 200, generated.text
    rows = _section_codes(client, db_session, case["course_id"])
    assert {code for code, _ in rows} == {"A"}, rows


def test_inactive_curriculum_course_is_never_scheduled(
    client, db_session, admin_headers
):
    case = _make_case(client, db_session, course_active=False)
    response = _generate(
        client,
        admin_headers,
        mode="fill_empty",
        academic_period_id=case["period_id"],
    )
    assert response.status_code == 200, response.text
    assert _schedules(client, db_session, [case["section_id"]]) == []
    item = _unassigned(response.json(), case["section_id"])
    assert item is not None
    assert item["reason"] == "mk terkunci"
    rows = _section_codes(client, db_session, case["course_id"])
    assert {code for code, _ in rows} == {"A"}, rows


def test_empty_preferences_are_neutral(client, db_session, admin_headers):
    case = _make_case(client, db_session, instructor=True)

    response = _generate(
        client,
        admin_headers,
        mode="fill_empty",
        academic_period_id=case["period_id"],
    )
    assert response.status_code == 200, response.text
    assert _unassigned(response.json(), case["section_id"]) is None
    schedules = _schedules(client, db_session, [case["section_id"]])
    assert len(schedules) == 1
    assert schedules[0]["start"] == 7


def test_generate_prevents_lecturer_and_room_double_booking(
    client, db_session, admin_headers
):
    lecturer_case = _make_case(
        client,
        db_session,
        instructor=True,
        extra_section=True,
        shared_lecturer=True,
        room_count=2,
    )
    response = _generate(client, admin_headers, mode="fill_empty")
    assert response.status_code == 200

    schedules = _schedules(
        client, db_session, [lecturer_case["section_id"], lecturer_case["extra_section_id"]]
    )
    assert len(schedules) == 2
    first, second = schedules
    assert not (
        first["day"] == second["day"]
        and blocks_overlap(first["start"], first["end"], second["start"], second["end"])
    )

    room_case = _make_case(client, db_session, extra_section=True, room_count=1)
    response = _generate(client, admin_headers, mode="fill_empty")
    assert response.status_code == 200
    schedules = _schedules(
        client, db_session, [room_case["section_id"], room_case["extra_section_id"]]
    )
    assert len(schedules) == 2
    first, second = schedules
    assert not (
        first["room_id"] == second["room_id"]
        and first["day"] == second["day"]
        and blocks_overlap(first["start"], first["end"], second["start"], second["end"])
    )


def test_generate_is_blocked_when_krs_is_open(client, db_session, admin_headers):
    case = _make_case(client, db_session)

    async def lock():
        db_session.add(
            SchedulePeriodLock(
                academic_period_id=case["period_id"], krs_open=True
            )
        )
        await db_session.flush()

    client.portal.call(lock)
    response = _generate(client, admin_headers, mode="fill_empty")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "scheduling_locked"
    assert _schedules(client, db_session, [case["section_id"]]) == []


def test_full_reset_requires_confirmation_and_admin(client, db_session, admin_headers, lecturer_headers):
    case = _make_case(client, db_session, with_schedule=True)

    unconfirmed = _generate(client, admin_headers, mode="full_reset")
    assert unconfirmed.status_code == 422, unconfirmed.text
    assert unconfirmed.json()["error"]["code"] == "confirmation_required"

    non_admin = _generate(
        client,
        lecturer_headers,
        mode="full_reset",
        confirm_full_reset=True,
    )
    assert non_admin.status_code == 403, non_admin.text
    assert non_admin.json()["error"]["code"] == "forbidden"

    reset = _generate(
        client,
        admin_headers,
        mode="full_reset",
        confirm_full_reset=True,
    )
    assert reset.status_code == 200, reset.text
    assert reset.json()["mode"] == "full_reset"
    schedules = _schedules(client, db_session, [case["section_id"]])
    assert len(schedules) == 1, schedules
    assert schedules[0]["id"] != case["schedule_id"]
    assert schedules[0]["end"] == schedules[0]["start"] + 3
    assert schedules[0]["end_minute"] == 0


def test_fill_empty_keeps_existing_schedule(client, db_session, admin_headers):
    case = _make_case(client, db_session, with_schedule=True)

    response = _generate(client, admin_headers, mode="fill_empty")

    assert response.status_code == 200
    schedules = _schedules(client, db_session, [case["section_id"]])
    assert len(schedules) == 1
    assert schedules[0]["id"] == case["schedule_id"]
    assert schedules[0]["end"] == schedules[0]["start"] + 3
    assert schedules[0]["end_minute"] == 0
    assert schedules[0]["day"] == 2
    assert schedules[0]["start"] == 9


def test_class_count_override_bounds_idempotency_and_generation(
    client, db_session, admin_headers, lecturer_headers
):
    case = _make_case(client, db_session)
    payload = {
        "academic_period_id": case["period_id"],
        "course_id": case["course_id"],
        "study_program_id": case["program_id"],
        "class_count": 3,
    }

    async def course_is_visible():
        assert (
            await db_session.get(Course, uuid.UUID(case["course_id"])) is not None
        ), case["course_id"]

    client.portal.call(course_is_visible)

    for invalid_count in (0, 4):
        response = client.post(
            PATH + "/class-count-overrides",
            json={**payload, "class_count": invalid_count},
            headers=admin_headers,
        )
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "validation_error"

    denied = client.post(
        PATH + "/class-count-overrides", json=payload, headers=lecturer_headers
    )
    assert denied.status_code == 403, denied.text
    assert denied.json()["error"]["code"] == "akses_prodi_ditolak"

    first = client.post(
        PATH + "/class-count-overrides", json=payload, headers=admin_headers
    )
    assert first.status_code == 200, first.text
    assert first.json()["created"] is True

    again = client.post(
        PATH + "/class-count-overrides", json=payload, headers=admin_headers
    )
    assert again.status_code == 200, again.text
    assert again.json()["created"] is False
    assert again.json()["override_id"] == first.json()["override_id"]

    generated = _generate(client, admin_headers, mode="fill_empty")
    assert generated.status_code == 200, generated.text

    async def section_codes():
        component_ids = (
            await db_session.execute(
                select(OfferingComponent.offering_component_id).join(
                    CourseOffering,
                    CourseOffering.course_offering_id
                    == OfferingComponent.course_offering_id,
                ).where(CourseOffering.course_id == case["course_id"])
            )
        ).scalars().all()
        return list(
            (
                await db_session.execute(
                    select(ClassSection.section_code, ClassSection.class_section_id).where(
                        ClassSection.offering_component_id.in_(component_ids)
                    )
                )
            ).all()
        )

    rows = client.portal.call(section_codes)
    assert {code for code, _ in rows} == {"A", "B", "C"}, rows
    schedules = _schedules(client, db_session, [str(section_id) for _, section_id in rows])
    assert len(schedules) == 1, schedules
    generated_ids = {str(section_id) for _, section_id in rows}
    assert all(
        _unassigned(generated.json(), section_id)["reason_code"]
        == "missing_assignment"
        for section_id in generated_ids - {case["section_id"]}
    )


def test_class_count_override_blocked_after_krs_open(
    client, db_session, admin_headers
):
    case = _make_case(client, db_session)
    period_id = uuid.UUID(case["period_id"])

    async def open_krs():
        lock = await db_session.get(SchedulePeriodLock, period_id)
        if lock is None:
            lock = SchedulePeriodLock(academic_period_id=period_id)
            db_session.add(lock)
        lock.krs_open = True
        await db_session.flush()

    client.portal.call(open_krs)

    response = client.post(
        PATH + "/class-count-overrides",
        json={
            "academic_period_id": case["period_id"],
            "course_id": case["course_id"],
            "study_program_id": case["program_id"],
            "class_count": 2,
        },
        headers=admin_headers,
    )
    assert response.status_code == 409, response.text
    body = response.json()
    assert body["error"]["code"] == "scheduling_locked"
    assert "KRS" in body["error"]["message"]


def test_class_count_override_blocked_after_all_programs_final(
    client, db_session, admin_headers
):
    case = _make_case(client, db_session)
    period_id = uuid.UUID(case["period_id"])

    async def finalize_all_programs():
        for program_id in await all_study_program_ids(db_session):
            row = await db_session.get(
                ScheduleProgramStatus, (period_id, program_id)
            )
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
        await db_session.flush()

    client.portal.call(finalize_all_programs)

    response = client.post(
        PATH + "/class-count-overrides",
        json={
            "academic_period_id": case["period_id"],
            "course_id": case["course_id"],
            "study_program_id": case["program_id"],
            "class_count": 2,
        },
        headers=admin_headers,
    )
    assert response.status_code == 409, response.text
    body = response.json()
    assert body["error"]["code"] == "schedule_final"
    assert "final" in body["error"]["message"].lower()


def _pj_study_program_id(client, db_session):
    async def read():
        return (
            await db_session.execute(
                select(LecturerProfile.study_program_id)
                .join(User, User.user_id == LecturerProfile.user_id)
                .where(User.email == "dwi.rantini@ftmm.unair.ac.id")
            )
        ).scalar_one()

    return client.portal.call(read)


def test_class_count_override_blocked_when_actor_prodi_is_final(
    client, db_session, lecturer_headers
):
    case = _make_case(client, db_session)
    actor_program_id = _pj_study_program_id(client, db_session)

    async def finalize_actor_prodi():
        curriculum = Curriculum(
            study_program_id=actor_program_id,
            curriculum_name=f"Kurikulum PJ Uji {uuid.uuid4().hex[:6]}",
            curriculum_year=2024,
            is_active=True,
        )
        db_session.add(curriculum)
        await db_session.flush()
        db_session.add(
            CurriculumCourse(
                curriculum_id=curriculum.curriculum_id,
                course_id=uuid.UUID(case["course_id"]),
                credits_total=3,
                recommended_semester=1,
                term="ganjil",
                course_type="wajib",
                course_scope="program_studi",
                is_active=True,
            )
        )
        await db_session.execute(
            delete(ScheduleProgramStatus).where(
                ScheduleProgramStatus.academic_period_id
                == uuid.UUID(case["period_id"]),
                ScheduleProgramStatus.study_program_id == actor_program_id,
            )
        )
        db_session.add(
            ScheduleProgramStatus(
                academic_period_id=uuid.UUID(case["period_id"]),
                study_program_id=actor_program_id,
                state="final",
            )
        )
        await db_session.flush()

    client.portal.call(finalize_actor_prodi)

    response = client.post(
        PATH + "/class-count-overrides",
        json={
            "academic_period_id": case["period_id"],
            "course_id": case["course_id"],
            "study_program_id": str(actor_program_id),
            "class_count": 2,
        },
        headers=lecturer_headers,
    )
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "schedule_final"


def test_class_count_override_admin_allowed_until_all_programs_final(
    client, db_session, admin_headers
):
    case = _make_case(client, db_session)

    async def finalize_target_prodi():
        db_session.add(
            ScheduleProgramStatus(
                academic_period_id=uuid.UUID(case["period_id"]),
                study_program_id=uuid.UUID(case["program_id"]),
                state="final",
            )
        )
        await db_session.flush()

    client.portal.call(finalize_target_prodi)

    response = client.post(
        PATH + "/class-count-overrides",
        json={
            "academic_period_id": case["period_id"],
            "course_id": case["course_id"],
            "study_program_id": case["program_id"],
            "class_count": 2,
        },
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["created"] is True


def test_class_count_override_missing_course_or_prodi_precedes_guards(
    client, db_session, admin_headers
):
    case = _make_case(client, db_session)
    period_id = uuid.UUID(case["period_id"])

    async def seal_period():
        lock = await db_session.get(SchedulePeriodLock, period_id)
        if lock is None:
            lock = SchedulePeriodLock(academic_period_id=period_id)
            db_session.add(lock)
        lock.krs_open = True
        for program_id in await all_study_program_ids(db_session):
            row = await db_session.get(ScheduleProgramStatus, (period_id, program_id))
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
        await db_session.flush()

    client.portal.call(seal_period)

    for overrides, expected_code in (
        ({"course_id": str(uuid.uuid4())}, "course_not_found"),
        ({"study_program_id": str(uuid.uuid4())}, "study_program_not_found"),
    ):
        payload = {
            "academic_period_id": case["period_id"],
            "course_id": case["course_id"],
            "study_program_id": case["program_id"],
            "class_count": 2,
            **overrides,
        }
        response = client.post(
            PATH + "/class-count-overrides", json=payload, headers=admin_headers
        )
        assert response.status_code == 404, response.text
        assert response.json()["error"]["code"] == expected_code


def test_elective_demand_ignores_cohort_size(client, db_session, admin_headers):
    case = _make_case(client, db_session, course_type="pilihan")

    async def add_cohort():
        for index in range(41):
            student = User(
                email=f"cohort-{case['program_id']}-{index}@ftmm.unair.ac.id",
                full_name=f"Mahasiswa Angkatan {index}",
                role="student",
                is_active=True,
            )
            db_session.add(student)
            await db_session.flush()
            db_session.add(
                StudentProfile(
                    user_id=student.user_id,
                    study_program_id=uuid.UUID(case["program_id"]),
                    student_number=f"C{index:05d}",
                    admission_year=2024,
                    current_semester=1,
                )
            )
        await db_session.flush()

    client.portal.call(add_cohort)

    response = _generate(
        client,
        admin_headers,
        mode="fill_empty",
        academic_period_id=case["period_id"],
    )
    assert response.status_code == 200, response.text
    rows = _section_codes(client, db_session, case["course_id"])
    assert {code for code, _ in rows} == {"A"}, rows


def test_class_count_override_rejects_out_of_range_counts(
    client, db_session, admin_headers
):
    case = _make_case(client, db_session)
    payload = {
        "academic_period_id": case["period_id"],
        "course_id": case["course_id"],
        "study_program_id": case["program_id"],
    }
    for invalid_count in (0, 4):
        response = client.post(
            PATH + "/class-count-overrides",
            json={**payload, "class_count": invalid_count},
            headers=admin_headers,
        )
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "validation_error"


def test_two_sks_class_occupies_eight_to_ten(client, db_session, admin_headers):
    case = _make_case(
        client,
        db_session,
        credits=2,
        instructor=True,
        preferences=[
            {"pool_index": 0, "day": 1, "start": 8, "end": 10, "kind": "preferred"}
        ],
    )
    generated = _generate(
        client,
        admin_headers,
        mode="fill_empty",
        academic_period_id=case["period_id"],
    )
    assert generated.status_code == 200, generated.text
    body = generated.json()
    assert _unassigned(body, case["section_id"]) is None
    assert not any(
        case["section_id"]
        in (item["class_section_a_id"], item["class_section_b_id"])
        for item in body["conflicts"]
    )

    schedules = _schedules(client, db_session, [case["section_id"]])
    assert len(schedules) == 1, schedules
    schedule = schedules[0]
    assert (schedule["day"], schedule["start"], schedule["end"]) == (1, 8, 10)
    assert schedule["end_minute"] == 0


def test_two_prodi_reuse_shared_room_at_different_hours(
    client, db_session, admin_headers
):
    first = _make_case(
        client,
        db_session,
        credits=2,
        room_count=0,
        instructor=True,
        new_period=True,
        preferences=[
            {"pool_index": 0, "day": 1, "start": 8, "end": 10, "kind": "preferred"}
        ],
    )
    second = _make_case(
        client,
        db_session,
        credits=2,
        room_count=0,
        instructor=True,
        period_id=first["period_id"],
        preferences=[
            {"pool_index": 0, "day": 1, "start": 13, "end": 15, "kind": "preferred"}
        ],
    )
    assert first["period_id"] == second["period_id"]
    assert first["program_id"] != second["program_id"]

    async def leave_one_shared_room():
        shared = (
            await db_session.execute(
                select(Room).where(
                    Room.owner_study_program_id.is_(None),
                    Room.is_active.is_(True),
                )
            )
        ).scalars().all()
        for room in shared:
            room.capacity = 1
        db_session.add(
            Room(
                room_code=f"UJI-BERSAMA-{uuid.uuid4().hex[:8]}",
                capacity=80,
                owner_study_program_id=None,
                is_active=True,
            )
        )
        await db_session.flush()

    client.portal.call(leave_one_shared_room)

    generated = _generate(
        client,
        admin_headers,
        mode="fill_empty",
        academic_period_id=first["period_id"],
    )
    assert generated.status_code == 200, generated.text
    body = generated.json()
    involved = {first["section_id"], second["section_id"]}
    assert _unassigned(body, first["section_id"]) is None
    assert _unassigned(body, second["section_id"]) is None
    assert not any(
        {item["class_section_a_id"], item["class_section_b_id"]} & involved
        for item in body["conflicts"]
    )

    first_rows = _schedules(client, db_session, [first["section_id"]])
    second_rows = _schedules(client, db_session, [second["section_id"]])
    assert len(first_rows) == 1 and len(second_rows) == 1
    left, right = first_rows[0], second_rows[0]
    assert left["room_id"] is not None
    assert left["room_id"] == right["room_id"]
    assert left["day"] == right["day"] == 1
    assert {(left["start"], left["end"]), (right["start"], right["end"])} == {
        (8, 10),
        (13, 15),
    }
    assert not blocks_overlap(
        left["start"], left["end"], right["start"], right["end"]
    )


def test_unassigned_endpoint_returns_diagnostics(client, db_session, admin_headers):
    case = _make_case(client, db_session, capacity=100, room_capacity=20)

    generated = _generate(
        client,
        admin_headers,
        mode="fill_empty",
        academic_period_id=case["period_id"],
    )
    assert generated.status_code == 200

    diagnostics = client.get(
        PATH + "/unassigned",
        params={"academic_period_id": case["period_id"]},
        headers=admin_headers,
    )
    assert diagnostics.status_code == 200
    body = diagnostics.json()
    assert body["meta"]["total"] == len(body["data"])
    assert body["meta"]["run_id"] == generated.json()["run_id"]
    item = next(
        (
            row
            for row in body["data"]
            if row["class_section_id"] == case["section_id"]
        ),
        None,
    )
    assert item is not None
    assert item["reason"] == "kapasitas ruang"
    assert item["reason_code"] == "room_capacity"
    assert item["course_code"]


def _unavailable_all_week(pool_index=0):
    return [
        {
            "pool_index": pool_index,
            "day": day,
            "start": 7,
            "end": 17,
            "kind": "unavailable",
        }
        for day in range(1, 6)
    ]


def test_solver_uses_only_the_active_class_assignment(client, db_session, admin_headers):
    case = _make_case(
        client,
        db_session,
        pool_size=2,
        assigned_pool_index=1,
        preferences=_unavailable_all_week(0),
    )

    generated = _generate(
        client,
        admin_headers,
        mode="fill_empty",
        academic_period_id=case["period_id"],
    )
    assert generated.status_code == 200, generated.text
    assert _unassigned(generated.json(), case["section_id"]) is None
    assert len(_schedules(client, db_session, [case["section_id"]])) == 1

    board = client.get(
        PATH + "/board",
        params={"period_id": case["period_id"]},
        headers=admin_headers,
    )
    assert board.status_code == 200, board.text
    item = next(
        row
        for row in board.json()["data"]["classes"]
        if row["class_section_id"] == case["section_id"]
    )
    assert item["lecturers"] == [case["pool_names"][1]]
    assert item["is_manually_edited"] is False


def test_preferred_window_is_soft_binary_score(client, db_session, admin_headers):
    case = _make_case(
        client,
        db_session,
        credits=2,
        preferences=[
            {
                "pool_index": 0,
                "day": 1,
                "start": 13,
                "end": 15,
                "kind": "preferred",
            }
        ],
    )
    generated = _generate(
        client,
        admin_headers,
        mode="fill_empty",
        academic_period_id=case["period_id"],
    )
    assert generated.status_code == 200, generated.text
    schedule = _schedules(client, db_session, [case["section_id"]])[0]
    assert (schedule["day"], schedule["start"], schedule["end"]) == (1, 13, 15)


def test_unavailable_overlap_is_hard_exclusion(client, db_session, admin_headers):
    case = _make_case(
        client,
        db_session,
        credits=2,
        preferences=[
            {
                "pool_index": 0,
                "day": 1,
                "start": 7,
                "end": 9,
                "kind": "unavailable",
            }
        ],
    )
    generated = _generate(
        client,
        admin_headers,
        mode="fill_empty",
        academic_period_id=case["period_id"],
    )
    assert generated.status_code == 200, generated.text
    schedule = _schedules(client, db_session, [case["section_id"]])[0]
    assert schedule["day"] == 1
    assert schedule["start"] == 9
    assert schedule["end"] == 11


def test_auto_assignment_falls_back_and_persists_atomically(
    client, db_session, admin_headers
):
    case = _make_case(
        client,
        db_session,
        pool_size=2,
        preferences=_unavailable_all_week(0),
    )
    generated = _generate(
        client,
        admin_headers,
        mode="fill_empty",
        academic_period_id=case["period_id"],
    )
    assert generated.status_code == 200, generated.text
    assert _unassigned(generated.json(), case["section_id"]) is None

    async def state():
        assignment = await db_session.get(
            ClassInstructorAssignment, uuid.UUID(case["assignment_id"])
        )
        audit_count = await db_session.scalar(
            text(
                "SELECT count(*) FROM admin_authority_traces "
                "WHERE action = 'class_instructor_assignment_solver_fallback' "
                "AND field_name = :section_id"
            ),
            {"section_id": case["section_id"]},
        )
        return assignment, audit_count

    assignment, audit_count = client.portal.call(state)
    assert str(assignment.user_id) == case["pool_user_ids"][1]
    assert assignment.source == "auto"
    assert assignment.is_pinned is False
    assert audit_count == 1


def test_valid_assigned_slot_prevents_preferred_fallback(
    client, db_session, admin_headers
):
    case = _make_case(
        client,
        db_session,
        pool_size=2,
        preferences=[
            {
                "pool_index": 1,
                "day": 1,
                "start": 8,
                "end": 11,
                "kind": "preferred",
            }
        ],
    )
    generated = _generate(
        client,
        admin_headers,
        mode="fill_empty",
        academic_period_id=case["period_id"],
    )
    assert generated.status_code == 200, generated.text

    async def assigned_user():
        assignment = await db_session.get(
            ClassInstructorAssignment, uuid.UUID(case["assignment_id"])
        )
        return str(assignment.user_id)

    assert client.portal.call(assigned_user) == case["pool_user_ids"][0]
    schedule = _schedules(client, db_session, [case["section_id"]])[0]
    assert (schedule["day"], schedule["start"]) == (1, 7)


def test_manual_and_pinned_assignments_never_fall_back(
    client, db_session, admin_headers
):
    for options, expected_code in (
        ({"assignment_source": "manual"}, "manual_no_slot"),
        ({"is_pinned": True}, "pinned_no_slot"),
    ):
        case = _make_case(
            client,
            db_session,
            pool_size=2,
            preferences=_unavailable_all_week(0),
            **options,
        )
        generated = _generate(
            client,
            admin_headers,
            mode="fill_empty",
            academic_period_id=case["period_id"],
        )
        assert generated.status_code == 200, generated.text
        item = _unassigned(generated.json(), case["section_id"])
        assert item["reason_code"] == expected_code

        async def assigned_user():
            assignment = await db_session.get(
                ClassInstructorAssignment, uuid.UUID(case["assignment_id"])
            )
            return str(assignment.user_id)

        assert client.portal.call(assigned_user) == case["pool_user_ids"][0]


def test_missing_pjmk_pool_and_assignment_have_stable_reasons(
    client, db_session, admin_headers
):
    for options, expected_code in (
        ({"instructor": False}, "empty_pool"),
        ({"pool_size": 2, "pjmk": False}, "missing_pjmk"),
        ({"with_assignment": False}, "missing_assignment"),
    ):
        case = _make_case(client, db_session, **options)
        generated = _generate(
            client,
            admin_headers,
            mode="fill_empty",
            academic_period_id=case["period_id"],
        )
        assert generated.status_code == 200, generated.text
        item = _unassigned(generated.json(), case["section_id"])
        assert item["reason_code"] == expected_code
        assert _schedules(client, db_session, [case["section_id"]]) == []
        board = client.get(
            PATH + "/board",
            params={"period_id": case["period_id"]},
            headers=admin_headers,
        )
        assert board.status_code == 200, board.text
        board_item = next(
            row
            for row in board.json()["data"]["unassigned"]
            if row["class_section_id"] == case["section_id"]
        )
        assert board_item["reason_code"] == expected_code

    case = _make_case(client, db_session)

    async def deactivate_pjmk():
        lecturer = await db_session.get(User, uuid.UUID(case["pool_user_ids"][0]))
        lecturer.is_active = False
        await db_session.flush()

    client.portal.call(deactivate_pjmk)
    generated = _generate(
        client,
        admin_headers,
        mode="fill_empty",
        academic_period_id=case["period_id"],
    )
    assert generated.status_code == 200, generated.text
    assert _unassigned(generated.json(), case["section_id"])["reason_code"] == "missing_pjmk"


def test_ineligible_assignment_does_not_use_other_pool_members(
    client, db_session, admin_headers
):
    case = _make_case(client, db_session, pool_size=2)

    async def replace_assignment_user():
        outsider = (
            await db_session.execute(
                select(User).where(User.email == "dwi.rantini@ftmm.unair.ac.id")
            )
        ).scalars().first()
        assert outsider is not None
        assignment = await db_session.get(
            ClassInstructorAssignment, uuid.UUID(case["assignment_id"])
        )
        assignment.user_id = outsider.user_id
        await db_session.flush()

    client.portal.call(replace_assignment_user)
    generated = _generate(
        client,
        admin_headers,
        mode="fill_empty",
        academic_period_id=case["period_id"],
    )
    assert generated.status_code == 200, generated.text
    item = _unassigned(generated.json(), case["section_id"])
    assert item["reason_code"] == "ineligible_assignment"


def test_board_and_edit_conflicts_use_the_active_assignment(
    client, db_session, admin_headers
):
    case = _make_case(client, db_session, pool_size=2, room_count=2)

    async def add_parallel_class():
        section = ClassSection(
            offering_component_id=uuid.UUID(case["component_id"]),
            section_code="B",
            capacity=50,
            enrollment_status="open",
        )
        db_session.add(section)
        await db_session.flush()
        admin = (
            await db_session.execute(
                select(User).where(User.email == "admin@ftmm.unair.ac.id")
            )
        ).scalars().one()
        db_session.add(
            ClassInstructorAssignment(
                class_section_id=section.class_section_id,
                academic_period_id=uuid.UUID(case["period_id"]),
                user_id=uuid.UUID(case["pool_user_ids"][1]),
                source="manual",
                is_pinned=False,
                is_active=True,
                assigned_by=admin.user_id,
            )
        )
        await db_session.flush()
        return str(section.class_section_id)

    second_section = client.portal.call(add_parallel_class)
    generated = _generate(
        client,
        admin_headers,
        mode="fill_empty",
        academic_period_id=case["period_id"],
    )
    assert generated.status_code == 200, generated.text

    board = client.get(
        PATH + "/board",
        params={"period_id": case["period_id"]},
        headers=admin_headers,
    ).json()
    assert not any(
        conflict["kind"] == "lecturer"
        and {conflict["class_section_a_id"], conflict["class_section_b_id"]}
        == {case["section_id"], second_section}
        for conflict in board["data"]["conflicts"]
    )

    async def assign_same_lecturer():
        assignment = (
            await db_session.execute(
                select(ClassInstructorAssignment).where(
                    ClassInstructorAssignment.class_section_id == uuid.UUID(second_section)
                )
            )
        ).scalars().one()
        assignment.user_id = uuid.UUID(case["pool_user_ids"][0])
        await db_session.flush()
    client.portal.call(assign_same_lecturer)

    first = _schedules(client, db_session, [case["section_id"]])[0]
    moved = client.patch(
        PATH + f"/classes/{second_section}",
        json={
            "day_of_week": first["day"],
            "start_hour": first["start"],
            "room_id": first["room_id"],
            "reason": "Uji konflik assignment aktif",
        },
        headers=admin_headers,
    )
    assert moved.status_code == 200, moved.text
    assert any(
        conflict["kind"] == "lecturer"
        for conflict in moved.json()["conflicts"]
    )
    board = client.get(
        PATH + "/board",
        params={"period_id": case["period_id"]},
        headers=admin_headers,
    ).json()
    board_conflict = next(
        conflict
        for conflict in board["data"]["conflicts"]
        if conflict["kind"] == "lecturer"
        and {conflict["class_section_a_id"], conflict["class_section_b_id"]}
        == {case["section_id"], second_section}
    )
    assert board_conflict["object_id"] == case["pool_user_ids"][0]
    assert board_conflict["object_name"] == case["pool_names"][0]
    assert board_conflict["object_name"] in board_conflict["label"]
    assert board_conflict["class_section_a_label"] in board_conflict["label"]
    assert board_conflict["class_section_b_label"] in board_conflict["label"]
    regenerated = _generate(
        client,
        admin_headers,
        mode="fill_empty",
        academic_period_id=case["period_id"],
    )
    assert regenerated.status_code == 200, regenerated.text
    generated_conflict = next(
        conflict
        for conflict in regenerated.json()["conflicts"]
        if conflict["kind"] == "lecturer"
        and {conflict["class_section_a_id"], conflict["class_section_b_id"]}
        == {case["section_id"], second_section}
    )
    assert generated_conflict["object_name"] == case["pool_names"][0]
    assert generated_conflict["class_section_a_label"] in generated_conflict["label"]
    assert generated_conflict["class_section_b_label"] in generated_conflict["label"]


def test_canonical_and_legacy_generation_reason_codes_match(
    client, db_session, admin_headers
):
    case = _make_case(client, db_session, with_assignment=False)
    target_items = []
    for base in (PATH, "/api/scheduling"):
        response = client.post(
            base + "/generate",
            json={"mode": "fill_empty", "academic_period_id": case["period_id"]},
            headers=admin_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["mode"] == "fill_empty"
        item = _unassigned(body, case["section_id"])
        assert item["reason_code"] == "missing_assignment"
        target_items.append(item)
    assert target_items[0]["reason"] == target_items[1]["reason"]
    assert target_items[0]["course_code"] == target_items[1]["course_code"]


def _add_curriculum_context(client, db_session, case: dict[str, Any]) -> uuid.UUID:
    async def add_context():
        program = (
            await db_session.execute(
                select(StudyProgram).where(
                    StudyProgram.study_program_id == uuid.UUID(case["program_id"])
                )
            )
        ).scalars().one()
        period = await db_session.get(AcademicPeriod, uuid.UUID(case["period_id"]))
        other_program = (
            await db_session.execute(
                select(StudyProgram)
                .where(StudyProgram.study_program_id != program.study_program_id)
                .order_by(StudyProgram.program_code)
                .limit(1)
            )
        ).scalars().one()
        curriculum = Curriculum(
            study_program_id=other_program.study_program_id,
            curriculum_name=f"Kurikulum Konteks {uuid.uuid4().hex[:8]}",
            curriculum_year=2099,
            is_active=True,
        )
        db_session.add(curriculum)
        await db_session.flush()
        curriculum_course = CurriculumCourse(
            curriculum_id=curriculum.curriculum_id,
            course_id=uuid.UUID(case["course_id"]),
            credits_total=3,
            recommended_semester=1,
            term=period.term,
            course_type="wajib",
            is_active=True,
        )
        db_session.add(curriculum_course)
        await db_session.flush()
        offering_id = (
            await db_session.execute(
                select(CourseOffering.course_offering_id)
                .join(
                    OfferingComponent,
                    OfferingComponent.course_offering_id
                    == CourseOffering.course_offering_id,
                )
                .where(
                    OfferingComponent.offering_component_id
                    == uuid.UUID(case["component_id"])
                )
            )
        ).scalar_one()
        db_session.add(
            CourseOfferingEligibility(
                course_offering_id=offering_id,
                curriculum_course_id=curriculum_course.curriculum_course_id,
            )
        )
        await db_session.commit()
        return curriculum_course.curriculum_course_id

    return client.portal.call(add_context)


@pytest.mark.parametrize(
    ("options", "reason", "action"),
    (
        ({"with_assignment": False}, "missing_assignment", "open_assignment"),
        ({"capacity": 100, "room_capacity": 20}, "room_capacity", "open_room_detail"),
        ({"course_active": False}, "course_locked", "open_course_detail"),
        ({"course_term": "opposite"}, "parity_mismatch", "open_course_detail"),
    ),
)
def test_unassigned_items_include_context_and_action_everywhere(
    client, db_session, admin_headers, options, reason, action
):
    case = _make_case(client, db_session, **options)
    generated = _generate(
        client,
        admin_headers,
        mode="fill_empty",
        academic_period_id=case["period_id"],
    )
    assert generated.status_code == 200, generated.text
    items = (
        _unassigned(generated.json(), case["section_id"]),
        next(
            item
            for item in client.get(
                PATH + "/unassigned",
                params={"academic_period_id": case["period_id"]},
                headers=admin_headers,
            ).json()["data"]
            if item["class_section_id"] == case["section_id"]
        ),
        next(
            item
            for item in client.get(
                PATH + "/board",
                params={"period_id": case["period_id"]},
                headers=admin_headers,
            ).json()["data"]["unassigned"]
            if item["class_section_id"] == case["section_id"]
        ),
    )
    for item in items:
        assert item["course_name"] == "Mata Kuliah Uji"
        assert item["section_code"] == "A"
        assert item["reason_code"] == reason
        assert item["action"] == action
        assert item["programs"][0]["study_program_id"] == case["program_id"]
        assert item["programs"][0]["study_program_code"]
        assert item["programs"][0]["study_program_name"]
        assert len(item["eligible_curriculum_contexts"]) == 1
        context = item["eligible_curriculum_contexts"][0]
        assert context["curriculum_course_id"] == case["curriculum_course_id"]
        assert context["study_program_code"]
        assert context["pjmk_reference_id"]


def test_missing_pjmk_action_edits_existing_reference(
    client, db_session, admin_headers
):
    case = _make_case(client, db_session)

    async def deactivate_pjmk():
        lecturer = await db_session.get(User, uuid.UUID(case["pool_user_ids"][0]))
        lecturer.is_active = False
        await db_session.commit()

    client.portal.call(deactivate_pjmk)
    generated = _generate(
        client,
        admin_headers,
        mode="fill_empty",
        academic_period_id=case["period_id"],
    )
    item = _unassigned(generated.json(), case["section_id"])
    assert item["reason_code"] == "missing_pjmk"
    assert item["action"] == "edit_pjmk"

    async def reference_id():
        return (
            await db_session.execute(
                select(CourseInstructorReference.instructor_reference_id).where(
                    CourseInstructorReference.curriculum_course_id
                    == uuid.UUID(case["curriculum_course_id"]),
                    CourseInstructorReference.instructor_role == "pjmk",
                )
            )
        ).scalar_one()

    assert item["pjmk_reference_id"] == str(client.portal.call(reference_id))


def test_ambiguous_unassigned_context_lists_all_eligible_curricula(
    client, db_session, admin_headers
):
    case = _make_case(client, db_session)
    other_context = _add_curriculum_context(client, db_session, case)
    generated = _generate(
        client,
        admin_headers,
        mode="fill_empty",
        academic_period_id=case["period_id"],
    )
    item = _unassigned(generated.json(), case["section_id"])
    assert item["reason_code"] == "curriculum_context_required"
    assert item["action"] == "open_assignment"
    assert {row["curriculum_course_id"] for row in item["eligible_curriculum_contexts"]} == {
        case["curriculum_course_id"],
        str(other_context),
    }


def test_scheduler_uses_union_pool_after_explicit_cross_program_context(
    client, db_session, admin_headers
):
    case = _make_case(
        client,
        db_session,
        pool_size=2,
        preferences=_unavailable_all_week(0),
    )
    other_context = _add_curriculum_context(client, db_session, case)

    async def choose_context_and_add_pool():
        assignment = await db_session.get(
            ClassInstructorAssignment, uuid.UUID(case["assignment_id"])
        )
        assignment.curriculum_course_id = uuid.UUID(case["curriculum_course_id"])
        lecturer = User(
            email=f"cross-pool-{uuid.uuid4().hex[:8]}@ftmm.unair.ac.id",
            full_name="Dosen Pool Lintas Prodi",
            role="lecturer",
            is_active=True,
        )
        db_session.add(lecturer)
        await db_session.flush()
        program = await db_session.get(StudyProgram, uuid.UUID(case["program_id"]))
        db_session.add(
            LecturerProfile(
                user_id=lecturer.user_id, study_program_id=program.study_program_id
            )
        )
        db_session.add(
            CourseInstructorReference(
                curriculum_course_id=other_context,
                academic_period_id=uuid.UUID(case["period_id"]),
                instructor_name=lecturer.full_name,
                instructor_role="pjmk",
                user_id=lecturer.user_id,
                position=1,
            )
        )
        await db_session.commit()
        return lecturer.user_id

    fallback_id = client.portal.call(choose_context_and_add_pool)
    generated = _generate(
        client,
        admin_headers,
        mode="fill_empty",
        academic_period_id=case["period_id"],
    )
    assert generated.status_code == 200, generated.text
    assert _unassigned(generated.json(), case["section_id"]) is None
    schedules = _schedules(client, db_session, [case["section_id"]])
    assert len(schedules) == 1

    async def assigned_user():
        assignment = await db_session.get(
            ClassInstructorAssignment, uuid.UUID(case["assignment_id"])
        )
        return assignment.user_id

    assert client.portal.call(assigned_user) == fallback_id
