"""Uji HTTP untuk pembangkit jadwal, batas kelas, dan diagnosis."""

import uuid
from datetime import datetime, time, timezone

from sqlalchemy import select, text

from models import (
    AcademicPeriod,
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
    LecturerAvailability,
    OfferingComponent,
    Room,
    SchedulePeriodLock,
    ScheduleProgramStatus,
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
    instructor=False,
    availability=None,
    with_schedule=False,
    extra_section=False,
    shared_lecturer=False,
    credits=3,
    room_count=1,
):
    async def setup():
        suffix = uuid.uuid4().hex[:8]
        period = (
            await db_session.execute(
                select(AcademicPeriod).where(AcademicPeriod.is_active.is_(True)).limit(1)
            )
        ).scalars().first()
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
        if instructor or shared_lecturer:
            lecturer = (
                await db_session.execute(
                    select(User).where(User.email == "pj.tsd@ftmm.unair.ac.id").limit(1)
                )
            ).scalars().first()
            assert lecturer is not None

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
            db_session.add(
                CourseInstructorReference(
                    curriculum_course_id=curriculum_course.curriculum_course_id,
                    instructor_name="Dosen Uji",
                    instructor_role="pjmk",
                    user_id=lecturer.user_id,
                )
            )

        if availability is not None and lecturer is not None:
            day, start, end = availability
            db_session.add(
                LecturerAvailability(
                    user_id=lecturer.user_id,
                    day_of_week=day,
                    start_hour=start,
                    end_hour=end,
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
            if shared_lecturer:
                db_session.add(
                    CourseInstructorReference(
                        curriculum_course_id=second_cc.curriculum_course_id,
                        instructor_name="Dosen Uji",
                        instructor_role="pjmk",
                        user_id=lecturer.user_id,
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


def test_generate_reports_capacity_parity_and_availability(
    client, db_session, admin_headers
):
    scenarios = (
        ({"capacity": 100, "room_capacity": 20}, "kapasitas ruang"),
        ({"course_term": "opposite"}, "paritas tidak sesuai"),
        (
            {"instructor": True, "availability": (1, 7, 9)},
            "dosen tidak tersedia",
        ),
    )
    for options, expected_reason in scenarios:
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
        assert item["reason"] == expected_reason
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
        assert len(schedules) == len(expected_codes), schedules


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


def test_mapped_lecturer_without_availability_blocks_section(
    client, db_session, admin_headers
):
    case = _make_case(client, db_session, instructor=True)

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
    assert item["reason"] == "tidak ada availabilitas dosen"


def test_generate_prevents_lecturer_and_room_double_booking(
    client, db_session, admin_headers
):
    lecturer_case = _make_case(
        client,
        db_session,
        instructor=True,
        extra_section=True,
        shared_lecturer=True,
        availability=(1, 7, 17),
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
    assert len(schedules) == 3, schedules


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
        availability=(1, 8, 10),
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
        availability=(1, 8, 10),
    )
    second = _make_case(
        client,
        db_session,
        credits=2,
        room_count=0,
        instructor=True,
        availability=(1, 13, 15),
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
    assert item["course_code"]
