"""HTTP foundation for period preferences, assignments, and scheduling settings."""

import uuid
from datetime import datetime, time, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, IntegrityError

from auth import get_password_hash
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
    SchedulePeriodSettings,
    ScheduleRun,
    StudyProgram,
    User,
)
from rate_limit import limiter

V1 = "/api/v1"
LEGACY = "/api"
PASSWORD = "FoundationUji2026!"


def _login_headers(
    client, email: str, password: str = PASSWORD
) -> dict[str, str]:
    limiter.reset()
    response = client.post(
        f"{V1}/auth/login",
        json={"identifier": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _period_pair(client, db_session) -> dict[str, Any]:
    async def setup():
        active = (
            await db_session.execute(
                select(AcademicPeriod)
                .where(AcademicPeriod.is_active.is_(True))
                .order_by(AcademicPeriod.academic_year_start.desc())
                .limit(1)
            )
        ).scalars().one()
        other = AcademicPeriod(
            academic_year_start=active.academic_year_start + 1,
            semester_number=1,
            term="ganjil",
            is_active=False,
        )
        db_session.add(other)
        await db_session.commit()
        return {
            "active_id": active.academic_period_id,
            "other_id": other.academic_period_id,
        }

    return client.portal.call(setup)


def _assignment_case(client, db_session, *, with_schedule: bool = True) -> dict[str, Any]:
    async def setup():
        suffix = uuid.uuid4().hex[:8]
        active = (
            await db_session.execute(
                select(AcademicPeriod).where(AcademicPeriod.is_active.is_(True)).limit(1)
            )
        ).scalars().one()
        program = (
            await db_session.execute(
                select(StudyProgram).where(StudyProgram.program_code == "TSD")
            )
        ).scalars().one()
        other_program = (
            await db_session.execute(
                select(StudyProgram).where(StudyProgram.program_code == "TI")
            )
        ).scalars().one()

        def account(label: str, *, role: str, active: bool) -> User:
            user = User(
                email=f"foundation.{label}.{suffix}@ftmm.unair.ac.id",
                full_name=f"Dosen Foundation {label}",
                role=role,
                is_active=active,
                password_hash=get_password_hash(PASSWORD),
            )
            db_session.add(user)
            return user

        lecturer = account("lecturer", role="lecturer", active=True)
        second = account("second", role="lecturer", active=True)
        inactive = account("inactive", role="lecturer", active=False)
        no_profile = account("no-profile", role="lecturer", active=True)
        ordinary = account("ordinary", role="lecturer", active=True)
        db_session.add_all([lecturer, second, inactive, no_profile, ordinary])
        await db_session.flush()
        db_session.add_all(
            [
                LecturerProfile(
                    user_id=lecturer.user_id,
                    study_program_id=program.study_program_id,
                    is_program_coordinator=False,
                ),
                LecturerProfile(
                    user_id=second.user_id,
                    study_program_id=program.study_program_id,
                    is_program_coordinator=False,
                ),
                LecturerProfile(
                    user_id=inactive.user_id,
                    study_program_id=program.study_program_id,
                    is_program_coordinator=False,
                ),
                LecturerProfile(
                    user_id=ordinary.user_id,
                    study_program_id=program.study_program_id,
                    is_program_coordinator=False,
                ),
            ]
        )

        own_pj_email = (
            await db_session.execute(
                select(User.email)
                .join(LecturerProfile, LecturerProfile.user_id == User.user_id)
                .where(
                    LecturerProfile.study_program_id == program.study_program_id,
                    LecturerProfile.is_program_coordinator.is_(True),
                    User.is_active.is_(True),
                )
                .limit(1)
            )
        ).scalar_one()
        other_pj_email = (
            await db_session.execute(
                select(User.email)
                .join(LecturerProfile, LecturerProfile.user_id == User.user_id)
                .where(
                    LecturerProfile.study_program_id == other_program.study_program_id,
                    LecturerProfile.is_program_coordinator.is_(True),
                    User.is_active.is_(True),
                )
                .limit(1)
            )
        ).scalar_one()

        curriculum = Curriculum(
            study_program_id=program.study_program_id,
            curriculum_name=f"Kurikulum Foundation {suffix}",
            curriculum_year=2026,
            is_active=True,
        )
        db_session.add(curriculum)
        await db_session.flush()
        course_number = uuid.uuid4().int % 10_000
        course_code = f"FD{course_number:04d}"
        while (
            await db_session.execute(
                select(Course.course_id).where(Course.course_code == course_code)
            )
        ).first() is not None:
            course_number = (course_number + 1) % 10_000
            course_code = f"FD{course_number:04d}"
        course = Course(
            course_code=course_code,
            course_name=f"Mata Kuliah Foundation {suffix}",
            is_active=True,
        )
        db_session.add(course)
        await db_session.flush()
        curriculum_course = CurriculumCourse(
            curriculum_id=curriculum.curriculum_id,
            course_id=course.course_id,
            credits_total=3,
            recommended_semester=1,
            term=active.term,
            course_type="wajib",
            course_scope="program_studi",
            is_active=True,
        )
        db_session.add(curriculum_course)
        await db_session.flush()
        db_session.add_all(
            [
                CourseInstructorReference(
                    curriculum_course_id=curriculum_course.curriculum_course_id,
                    academic_period_id=active.academic_period_id,
                    instructor_name=lecturer.full_name,
                    instructor_role="teaching_team",
                    user_id=lecturer.user_id,
                    position=1,
                ),
                CourseInstructorReference(
                    curriculum_course_id=curriculum_course.curriculum_course_id,
                    academic_period_id=active.academic_period_id,
                    instructor_name=second.full_name,
                    instructor_role="teaching_team",
                    user_id=second.user_id,
                    position=2,
                ),
            ]
        )
        offering = CourseOffering(
            academic_period_id=active.academic_period_id,
            course_id=course.course_id,
            offering_code=f"FOUND-{suffix}",
        )
        db_session.add(offering)
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
        section = ClassSection(
            offering_component_id=component.offering_component_id,
            section_code="A",
            capacity=40,
            enrollment_status="open",
        )
        db_session.add(section)
        await db_session.flush()
        if with_schedule:
            db_session.add(
                ClassSchedule(
                    class_section_id=section.class_section_id,
                    day_of_week=1,
                    start_time=time(8),
                    end_time=time(10),
                    room_name=f"RUANG-{suffix}",
                )
            )
        await db_session.commit()
        return {
            "period_id": active.academic_period_id,
            "program_id": program.study_program_id,
            "other_program_id": other_program.study_program_id,
            "course_id": course.course_id,
            "offering_id": offering.course_offering_id,
            "class_id": section.class_section_id,
            "curriculum_course_id": curriculum_course.curriculum_course_id,
            "lecturer_id": lecturer.user_id,
            "second_id": second.user_id,
            "inactive_id": inactive.user_id,
            "no_profile_id": no_profile.user_id,
            "ordinary_email": ordinary.email,
            "own_pj_email": own_pj_email,
            "other_pj_email": other_pj_email,
            "course_code": course.course_code,
            "course_name": course.course_name,
        }

    return client.portal.call(setup)


def _add_cross_program_eligibility(client, db_session, case: dict[str, Any]) -> None:
    async def setup():
        suffix = uuid.uuid4().hex[:8]
        curriculum = Curriculum(
            study_program_id=case["other_program_id"],
            curriculum_name=f"Kurikulum Lintas Prodi {suffix}",
            curriculum_year=2026,
            is_active=True,
        )
        db_session.add(curriculum)
        await db_session.flush()
        curriculum_course = CurriculumCourse(
            curriculum_id=curriculum.curriculum_id,
            course_id=case["course_id"],
            credits_total=3,
            recommended_semester=1,
            term="ganjil",
            course_type="wajib",
            course_scope="program_studi",
            is_active=True,
        )
        db_session.add(curriculum_course)
        await db_session.flush()
        db_session.add(
            CourseOfferingEligibility(
                course_offering_id=case["offering_id"],
                curriculum_course_id=curriculum_course.curriculum_course_id,
            )
        )
        await db_session.commit()

    client.portal.call(setup)


def _assignment_payload(case: dict[str, Any], **overrides) -> dict[str, Any]:
    payload = {
        "academic_period_id": str(case["period_id"]),
        "user_id": str(case["lecturer_id"]),
        "source": "manual",
        "is_pinned": False,
    }
    payload.update(overrides)
    return payload


def _assignment_url(case: dict[str, Any], prefix: str = V1) -> str:
    return f"{prefix}/scheduling/classes/{case['class_id']}/assignment"


def test_assignment_requires_authentication(client):
    class_id = uuid.uuid4()
    assert client.get(f"{V1}/scheduling/classes/{class_id}/assignment").status_code == 401
    assert client.put(
        f"{V1}/scheduling/classes/{class_id}/assignment",
        json={"academic_period_id": str(uuid.uuid4()), "user_id": str(uuid.uuid4())},
    ).status_code == 401


def test_assignment_rejects_non_scheduler_roles(client, db_session, student_headers, admin_headers):
    case = _assignment_case(client, db_session)
    ordinary_headers = _login_headers(client, case["ordinary_email"])
    payload = _assignment_payload(case)
    for headers in (student_headers, ordinary_headers):
        response = client.put(_assignment_url(case), json=payload, headers=headers)
        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == "forbidden"
        assert client.get(_assignment_url(case), headers=headers).status_code == 403
    assert client.get(_assignment_url(case), headers=admin_headers).status_code == 200


def test_assignment_payload_and_period_validation(client, db_session, admin_headers):
    case = _assignment_case(client, db_session)
    payload = _assignment_payload(case)
    invalid_payloads = [
        {"user_id": payload["user_id"]},
        {"academic_period_id": payload["academic_period_id"]},
        {**payload, "source": "imported"},
        {**payload, "academic_period_id": "not-a-uuid"},
        {**payload, "assigned_by": str(uuid.uuid4())},
    ]
    for invalid in invalid_payloads:
        response = client.put(_assignment_url(case), json=invalid, headers=admin_headers)
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "validation_error"

    mismatch = client.put(
        _assignment_url(case),
        json=_assignment_payload(case, academic_period_id=str(uuid.uuid4())),
        headers=admin_headers,
    )
    assert mismatch.status_code == 422, mismatch.text
    assert mismatch.json()["error"]["code"] == "period_mismatch"
    assert mismatch.json()["error"]["details"][0]["field"] == "academic_period_id"


def test_assignment_requires_active_lecturer_account(client, db_session, admin_headers):
    case = _assignment_case(client, db_session)
    for field in ("inactive_id", "no_profile_id"):
        response = client.put(
            _assignment_url(case),
            json=_assignment_payload(case, user_id=str(case[field])),
            headers=admin_headers,
        )
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "invalid_lecturer"
        assert response.json()["error"]["details"][0]["field"] == "user_id"


def test_assignment_upsert_is_idempotent_and_keeps_one_active_row(
    client, db_session, admin_headers
):
    case = _assignment_case(client, db_session)
    empty = client.get(_assignment_url(case), headers=admin_headers)
    assert empty.status_code == 200
    assert empty.json() == {"data": None}

    payload = _assignment_payload(case)
    first = client.put(_assignment_url(case), json=payload, headers=admin_headers)
    assert first.status_code == 200, first.text
    body = first.json()["data"]
    assert body["class_section_id"] == str(case["class_id"])
    assert body["academic_period_id"] == str(case["period_id"])
    assert body["user_id"] == str(case["lecturer_id"])
    assert body["source"] == "manual"
    assert body["is_pinned"] is False
    assert body["is_active"] is True

    repeated = client.put(_assignment_url(case), json=payload, headers=admin_headers)
    assert repeated.status_code == 200, repeated.text
    assert repeated.json() == first.json()

    changed_payload = _assignment_payload(
        case,
        user_id=str(case["second_id"]),
        source="auto",
        is_pinned=True,
    )
    changed = client.put(_assignment_url(case), json=changed_payload, headers=admin_headers)
    assert changed.status_code == 200, changed.text
    assert changed.json()["data"]["assignment_id"] == body["assignment_id"]
    assert changed.json()["data"]["user_id"] == str(case["second_id"])
    assert changed.json()["data"]["source"] == "auto"
    assert changed.json()["data"]["is_pinned"] is True

    legacy = client.put(
        _assignment_url(case, LEGACY), json=changed_payload, headers=admin_headers
    )
    assert legacy.status_code == 200, legacy.text
    assert legacy.json() == changed.json()
    assert client.get(_assignment_url(case), headers=admin_headers).json() == changed.json()

    async def assert_single_active_and_reject_duplicate():
        count = (
            await db_session.execute(
                select(ClassInstructorAssignment.assignment_id).where(
                    ClassInstructorAssignment.class_section_id == case["class_id"],
                    ClassInstructorAssignment.is_active.is_(True),
                )
            )
        ).scalars().all()
        assert len(count) == 1
        try:
            async with db_session.begin_nested():
                db_session.add(
                    ClassInstructorAssignment(
                        class_section_id=case["class_id"],
                        academic_period_id=case["period_id"],
                        user_id=case["lecturer_id"],
                        source="manual",
                        is_pinned=False,
                        is_active=True,
                        assigned_by=case["lecturer_id"],
                    )
                )
                await db_session.flush()
        except IntegrityError:
            return
        raise AssertionError("Duplicate active assignment was accepted")

    client.portal.call(assert_single_active_and_reject_duplicate)


def test_assignment_scope_uses_authenticated_program(client, db_session, admin_headers):
    case = _assignment_case(client, db_session)
    payload = _assignment_payload(case)
    own_pj = _login_headers(client, case["own_pj_email"], "PjProdi2026!")
    other_pj = _login_headers(client, case["other_pj_email"], "PjProdi2026!")

    own = client.put(_assignment_url(case), json=payload, headers=own_pj)
    assert own.status_code == 200, own.text
    denied = client.put(_assignment_url(case), json=payload, headers=other_pj)
    assert denied.status_code == 403, denied.text
    assert denied.json()["error"]["code"] == "forbidden"
    assert client.put(_assignment_url(case), json=payload, headers=admin_headers).status_code == 200


def test_assignment_rejects_ambiguous_cross_program_context(
    client, db_session, admin_headers, pj_headers
):
    case = _assignment_case(client, db_session)
    _add_cross_program_eligibility(client, db_session, case)
    payload = _assignment_payload(case)

    for headers in (admin_headers, pj_headers):
        for response in (
            client.get(_assignment_url(case), headers=headers),
            client.put(_assignment_url(case), json=payload, headers=headers),
        ):
            assert response.status_code == 409, response.text
            assert response.json()["error"]["code"] == "curriculum_context_required"


def test_assignment_does_not_modify_class_schedule(client, db_session, admin_headers):
    case = _assignment_case(client, db_session, with_schedule=True)

    async def schedule_snapshot():
        row = (
            await db_session.execute(
                select(ClassSchedule).where(
                    ClassSchedule.class_section_id == case["class_id"]
                )
            )
        ).scalar_one()
        return (
            row.day_of_week,
            row.start_time,
            row.end_time,
            row.room_name,
            row.room_id,
        )

    before = client.portal.call(schedule_snapshot)
    response = client.put(
        _assignment_url(case), json=_assignment_payload(case), headers=admin_headers
    )
    assert response.status_code == 200, response.text
    assert client.portal.call(schedule_snapshot) == before


def test_assignment_missing_class_returns_404(client, admin_headers):
    missing = uuid.uuid4()
    response = client.get(f"{V1}/scheduling/classes/{missing}/assignment", headers=admin_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "class_not_found"


def test_period_settings_scope_uniqueness_and_monotonic_revision(client, db_session):
    periods = _period_pair(client, db_session)
    case = _assignment_case(client, db_session, with_schedule=False)

    async def setup_and_check():
        global_settings = SchedulePeriodSettings(
            academic_period_id=periods["active_id"],
            study_program_id=None,
            preference_deadline=datetime(2027, 1, 1, tzinfo=timezone.utc),
            input_revision=2,
        )
        program_settings = SchedulePeriodSettings(
            academic_period_id=periods["active_id"],
            study_program_id=case["program_id"],
            input_revision=1,
        )
        db_session.add_all([global_settings, program_settings])
        await db_session.commit()

        for duplicate in (
            SchedulePeriodSettings(
                academic_period_id=periods["active_id"],
                study_program_id=None,
            ),
            SchedulePeriodSettings(
                academic_period_id=periods["active_id"],
                study_program_id=case["program_id"],
            ),
        ):
            try:
                async with db_session.begin_nested():
                    db_session.add(duplicate)
                    await db_session.flush()
            except IntegrityError:
                continue
            raise AssertionError("Duplicate period settings scope was accepted")

        try:
            async with db_session.begin_nested():
                global_settings.input_revision = 1
                await db_session.flush()
        except DBAPIError:
            pass
        else:
            raise AssertionError("Decreasing input_revision was accepted")

        global_settings.input_revision = 3
        await db_session.commit()
        run = ScheduleRun(
            academic_period_id=periods["active_id"],
            mode="fill_empty",
        )
        db_session.add(run)
        await db_session.commit()
        return run.input_revision

    assert client.portal.call(setup_and_check) == 0


def test_period_scoped_pjmk_uniqueness_preserves_legacy_rows(client, db_session, admin_headers):
    periods = _period_pair(client, db_session)
    case = _assignment_case(client, db_session, with_schedule=False)

    async def create_references():
        rows = [
            CourseInstructorReference(
                curriculum_course_id=case["curriculum_course_id"],
                academic_period_id=period_id,
                instructor_name=f"PJ MK {index}",
                instructor_role="pjmk",
                user_id=case["lecturer_id"],
            )
            for index, period_id in enumerate(
                (periods["active_id"], periods["other_id"], None)
            )
        ]
        db_session.add_all(rows)
        await db_session.commit()
        try:
            async with db_session.begin_nested():
                db_session.add(
                    CourseInstructorReference(
                        curriculum_course_id=case["curriculum_course_id"],
                        academic_period_id=periods["active_id"],
                        instructor_name="PJ MK Duplikat",
                        instructor_role="pjmk",
                        user_id=case["second_id"],
                    )
                )
                await db_session.flush()
        except IntegrityError:
            pass
        else:
            raise AssertionError("Duplicate period PJ MK was accepted")
        try:
            async with db_session.begin_nested():
                db_session.add(
                    CourseInstructorReference(
                        curriculum_course_id=case["curriculum_course_id"],
                        academic_period_id=None,
                        instructor_name="PJ MK Legacy Duplikat",
                        instructor_role="pjmk",
                        user_id=case["second_id"],
                    )
                )
                await db_session.flush()
        except IntegrityError:
            pass
        else:
            raise AssertionError("Duplicate legacy PJ MK was accepted")
        return str(rows[0].instructor_reference_id)

    period_reference_id = client.portal.call(create_references)
    canonical = client.get(
        f"{V1}/scheduling/instructor-references",
        params={"academic_period_id": str(periods["active_id"])},
        headers=admin_headers,
    )
    legacy = client.get(
        f"{LEGACY}/scheduling/instructor-references",
        params={"academic_period_id": str(periods["active_id"])},
        headers=admin_headers,
    )
    assert canonical.status_code == legacy.status_code == 200
    assert canonical.json() == legacy.json()
    item = next(
        row
        for row in canonical.json()["data"]
        if row["reference_id"] == period_reference_id
    )
    assert item["curriculum_course_id"] == str(case["curriculum_course_id"])
    assert item["course_code"] == case["course_code"]
    assert item["user_id"] == str(case["lecturer_id"])
    assert item["is_mapped"] is True
