"""Kontrak dashboard dosen dari penugasan, jadwal, dan preferensi nyata."""

import importlib
import uuid
from datetime import date, datetime, time, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

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
    LecturerSchedulePreference,
    OfferingComponent,
    SchedulePeriodSettings,
    ScheduleProgramStatus,
    StudyProgram,
    User,
)
from rate_limit import limiter

DASHBOARD = "/api/v1/dashboard/me"
LECTURER_PASSWORD = "DashboardDosen2026!"


def _login(client: TestClient, email: str) -> dict[str, str]:
    limiter.reset()
    response = client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": LECTURER_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _dashboard_case(client: TestClient, db_session):
    async def setup():
        suffix = uuid.uuid4().hex[:8]
        period = (
            await db_session.execute(
                select(AcademicPeriod)
                .where(AcademicPeriod.is_active.is_(True))
                .limit(1)
            )
        ).scalars().first()
        assert period is not None
        admin = (
            await db_session.execute(
                select(User).where(User.email == "admin@ftmm.unair.ac.id")
            )
        ).scalars().one()

        programs = []
        for index in range(2):
            program = StudyProgram(
                program_code=f"DSH{suffix}{index}",
                program_name=f"Program Studi Dashboard {index} {suffix}",
                degree_level="sarjana",
                is_active=True,
            )
            db_session.add(program)
            programs.append(program)
        await db_session.flush()

        lecturer = User(
            email=f"dosen-dashboard-{suffix}@ftmm.unair.ac.id",
            full_name=f"Dosen Dashboard {suffix}",
            role="lecturer",
            is_active=True,
            password_hash=get_password_hash(LECTURER_PASSWORD),
        )
        other_lecturer = User(
            email=f"dosen-lain-{suffix}@ftmm.unair.ac.id",
            full_name=f"Dosen Lain {suffix}",
            role="lecturer",
            is_active=True,
            password_hash=get_password_hash(LECTURER_PASSWORD),
        )
        db_session.add_all([lecturer, other_lecturer])
        await db_session.flush()
        db_session.add(
            LecturerProfile(
                user_id=lecturer.user_id,
                study_program_id=programs[0].study_program_id,
            )
        )
        db_session.add(
            LecturerProfile(
                user_id=other_lecturer.user_id,
                study_program_id=programs[0].study_program_id,
            )
        )

        sections = []
        curricula = {}
        for index in range(3):
            program = programs[0] if index != 1 else programs[1]
            if program.study_program_id not in curricula:
                curriculum = Curriculum(
                    study_program_id=program.study_program_id,
                    curriculum_name=f"Kurikulum Dashboard {suffix}",
                    curriculum_year=2026,
                    is_active=True,
                )
                db_session.add(curriculum)
                await db_session.flush()
                curricula[program.study_program_id] = curriculum
            curriculum = curricula[program.study_program_id]
            course = Course(
                course_code=f"DSH{100 + (int(suffix, 16) + index) % 900}",
                course_name=f"Mata Kuliah Dashboard {index}",
                is_active=True,
            )
            db_session.add(course)
            await db_session.flush()
            curriculum_course = CurriculumCourse(
                curriculum_id=curriculum.curriculum_id,
                course_id=course.course_id,
                credits_total=2 + index,
                recommended_semester=1,
                term=period.term,
                course_type="wajib",
                course_scope="program_studi",
                is_active=True,
            )
            db_session.add(curriculum_course)
            await db_session.flush()
            offering = CourseOffering(
                academic_period_id=period.academic_period_id,
                course_id=course.course_id,
                offering_code=f"DSH-OFFER-{suffix}-{index}",
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
                section_code=chr(ord("A") + index),
                capacity=40,
                enrollment_status="open",
            )
            db_session.add(section)
            await db_session.flush()
            assignment = ClassInstructorAssignment(
                class_section_id=section.class_section_id,
                academic_period_id=period.academic_period_id,
                user_id=lecturer.user_id,
                source="auto",
                is_pinned=False,
                is_active=True,
                assigned_by=admin.user_id,
            )
            db_session.add(assignment)
            sections.append((section, course, curriculum_course, program))

        global_settings = (
            await db_session.execute(
                select(SchedulePeriodSettings).where(
                    SchedulePeriodSettings.academic_period_id
                    == period.academic_period_id,
                    SchedulePeriodSettings.study_program_id.is_(None),
                )
            )
        ).scalar_one_or_none()
        if global_settings is None:
            db_session.add(
                SchedulePeriodSettings(
                    academic_period_id=period.academic_period_id,
                    study_program_id=None,
                    preference_deadline=datetime(
                        2026, 11, 20, 8, tzinfo=timezone.utc
                    ),
                )
            )
        else:
            global_settings.preference_deadline = datetime(
                2026, 11, 20, 8, tzinfo=timezone.utc
            )

        db_session.add_all(
            [
                ClassSchedule(
                    class_section_id=sections[0][0].class_section_id,
                    day_of_week=1,
                    start_time=time(8, 0),
                    end_time=time(10, 0),
                    room_name="Ruang Dashboard Hari Ini",
                ),
                ClassSchedule(
                    class_section_id=sections[1][0].class_section_id,
                    day_of_week=3,
                    start_time=time(13, 0),
                    end_time=time(16, 0),
                    room_name="Ruang Dashboard Minggu Ini",
                ),
                ClassInstructorAssignment(
                    class_section_id=sections[2][0].class_section_id,
                    academic_period_id=period.academic_period_id,
                    user_id=other_lecturer.user_id,
                    source="manual",
                    is_pinned=True,
                    is_active=False,
                    assigned_by=admin.user_id,
                ),
                ScheduleProgramStatus(
                    academic_period_id=period.academic_period_id,
                    study_program_id=programs[0].study_program_id,
                    state="draft",
                ),
                ScheduleProgramStatus(
                    academic_period_id=period.academic_period_id,
                    study_program_id=programs[1].study_program_id,
                    state="final",
                ),
                SchedulePeriodSettings(
                    academic_period_id=period.academic_period_id,
                    study_program_id=programs[0].study_program_id,
                    preference_deadline=datetime(2026, 11, 28, 8, tzinfo=timezone.utc),
                ),
                LecturerSchedulePreference(
                    user_id=lecturer.user_id,
                    academic_period_id=period.academic_period_id,
                    day_of_week=1,
                    start_time=time(7, 0),
                    end_time=time(8, 0),
                    kind="preferred",
                ),
                LecturerSchedulePreference(
                    user_id=lecturer.user_id,
                    academic_period_id=period.academic_period_id,
                    day_of_week=5,
                    start_time=time(16, 0),
                    end_time=time(17, 0),
                    kind="unavailable",
                ),
            ]
        )
        await db_session.commit()
        return {
            "email": lecturer.email,
            "other_email": other_lecturer.email,
            "period_id": str(period.academic_period_id),
            "program_ids": [str(program.study_program_id) for program in programs],
            "program_codes": [program.program_code for program in programs],
            "sections": [str(section.class_section_id) for section, *_ in sections],
            "course_codes": [course.course_code for _, course, *_ in sections],
            "credits": [credits.credits_total for _, _, credits, _ in sections],
        }

    case = client.portal.call(setup)
    case["headers"] = _login(client, case["email"])
    case["other_headers"] = _login(client, case["other_email"])
    return case


def test_student_dashboard_uses_transcript_records(client, student_headers):
    response = client.get(DASHBOARD, headers=student_headers)
    assert response.status_code == 200
    body = response.json()
    stats = body["stats"]
    assert stats["type"] == "student"
    assert stats["sks_target"] == 144
    assert 0 <= stats["sks_completed"] <= stats["sks_target"]
    assert 0 <= stats["gpa"] <= 4
    assert isinstance(body["schedule"], list)


def test_admin_dashboard_reports_real_counts(client, admin_headers):
    body = client.get(DASHBOARD, headers=admin_headers).json()
    stats = body["stats"]
    assert stats["type"] == "admin"
    assert stats["total_active_students"] >= 1
    assert stats["total_courses"] >= 1
    assert stats["total_study_programs"] == 5


def test_lecturer_dashboard_has_real_today_week_and_unscheduled_classes(
    client, db_session, monkeypatch
):
    case = _dashboard_case(client, db_session)

    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 11, 23)

    dashboard_module = importlib.import_module("features.dashboard.router")
    monkeypatch.setattr(dashboard_module, "date", FixedDate)
    response = client.get(DASHBOARD, headers=case["headers"])
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["today"] == "2026-11-23"
    assert body["academic_period_id"] == case["period_id"]
    assert len(body["today_schedule"]) == 1
    assert len(body["schedule"]) == 2
    assert body["today_schedule"][0]["day"] == "Senin"
    assert body["today_schedule"][0]["start_time"] == "08:00"
    assert body["today_schedule"][0]["end_time"] == "10:00"
    assert body["today_schedule"][0]["room"] == "Ruang Dashboard Hari Ini"
    assert body["today_schedule"][0]["credits"] == case["credits"][0]
    assert body["today_schedule"][0]["study_program_codes"] == [case["program_codes"][0]]
    assert body["today_schedule"][0]["schedule_state"] == "draft"
    assert body["schedule"][1]["schedule_state"] == "final"
    assert body["schedule"][1]["study_program_codes"] == [case["program_codes"][1]]

    assert len(body["assigned_classes"]) == 3
    unscheduled = [item for item in body["assigned_classes"] if not item["schedules"]]
    assert len(body["unscheduled_classes"]) == 1
    assert unscheduled[0]["class_section_id"] == case["sections"][2]
    assert unscheduled[0]["course_code"] == case["course_codes"][2]
    assert unscheduled[0]["class_name"] == "C"
    assert unscheduled[0]["schedule_state"] == "draft"
    assert body["stats"] == {
        "type": "lecturer",
        "assigned_classes": 3,
        "scheduled_classes": 2,
        "unscheduled_classes": 1,
    }
    assert set(body["stats"]) == {
        "type",
        "assigned_classes",
        "scheduled_classes",
        "unscheduled_classes",
    }


def test_lecturer_dashboard_returns_preference_status_and_program_deadline(
    client, db_session
):
    case = _dashboard_case(client, db_session)
    body = client.get(DASHBOARD, headers=case["headers"]).json()

    assert body["preference"] == {
        "academic_period_id": case["period_id"],
        "status": "filled",
        "preferred_count": 1,
        "unavailable_count": 1,
        "deadline": "2026-11-28T08:00:00Z",
        "deadline_scope": "program",
    }


def test_ordinary_lecturer_is_scoped_to_session_and_has_no_polling_analytics(
    client, db_session
):
    case = _dashboard_case(client, db_session)
    body = client.get(DASHBOARD, headers=case["headers"]).json()
    other = client.get(DASHBOARD, headers=case["other_headers"]).json()

    assert {item["class_section_id"] for item in body["assigned_classes"]} == set(
        case["sections"]
    )
    assert other["assigned_classes"] == []
    assert other["schedule"] == []
    assert other["stats"]["assigned_classes"] == 0
    assert other["preference"]["status"] == "empty"
    assert not {"demand_analytics", "polling", "total_students", "advisee_students"}.intersection(
        body
    )
    assert not {"courses_taught", "sks_taught", "total_students", "advisee_students"}.intersection(
        body["stats"]
    )


def test_dashboard_canonical_and_legacy_lecturer_responses_match(
    client, db_session
):
    case = _dashboard_case(client, db_session)
    canonical = client.get(DASHBOARD, headers=case["headers"])
    legacy = client.get("/api/dashboard/me", headers=case["headers"])

    assert canonical.status_code == legacy.status_code == 200
    assert canonical.json() == legacy.json()


def test_dashboard_requires_authentication(client):
    assert client.get(DASHBOARD).status_code == 401
    assert client.get("/api/dashboard/me").status_code == 401
