"""HTTP kontrak pengecualian MK universitas dari penjadwalan FTMM."""

import uuid
from datetime import time

import pytest
from sqlalchemy import select

from models import (
    AcademicPeriod,
    ClassSchedule,
    ClassSection,
    Course,
    CourseOffering,
    CourseOfferingEligibility,
    Curriculum,
    CurriculumCourse,
    OfferingComponent,
    StudyProgram,
)
from scheduling_common import UNIVERSITY_SCOPE

V1 = "/api/v1"


def _create_university_class(client, db_session) -> dict[str, str]:
    async def setup():
        period_id = (
            await db_session.execute(
                select(AcademicPeriod.academic_period_id)
                .where(AcademicPeriod.is_active.is_(True))
                .order_by(AcademicPeriod.academic_year_start.desc())
                .limit(1)
            )
        ).scalar_one()
        program = (
            await db_session.execute(
                select(StudyProgram).where(StudyProgram.is_active.is_(True)).limit(1)
            )
        ).scalars().one()
        suffix = uuid.uuid4().hex[:8]
        course = Course(
            course_code=f"UM{int(suffix, 16) % 9000 + 1000}",
            course_name=f"MK Universitas Uji {suffix}",
            is_active=True,
        )
        curriculum = Curriculum(
            study_program_id=program.study_program_id,
            curriculum_name=f"Kurikulum Universitas Uji {suffix}",
            curriculum_year=2024,
            minimum_graduation_credits=144,
            standard_duration_semesters=8,
            is_active=True,
        )
        db_session.add_all([course, curriculum])
        await db_session.flush()
        curriculum_course = CurriculumCourse(
            curriculum_id=curriculum.curriculum_id,
            course_id=course.course_id,
            credits_total=2,
            recommended_semester=1,
            term="ganjil",
            course_type="wajib",
            course_scope=UNIVERSITY_SCOPE,
            is_active=True,
        )
        offering = CourseOffering(
            academic_period_id=period_id,
            course_id=course.course_id,
            offering_code=f"UM-{suffix}",
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
        section = ClassSection(
            offering_component_id=component.offering_component_id,
            section_code="A",
            capacity=40,
            enrollment_status="open",
        )
        db_session.add(section)
        await db_session.flush()
        db_session.add(
            ClassSchedule(
                class_section_id=section.class_section_id,
                day_of_week=1,
                start_time=time(8, 0),
                end_time=time(10, 0),
                room_name=f"Ruang UM {suffix}",
            )
        )
        await db_session.commit()
        return {
            "course_id": str(course.course_id),
            "course_code": course.course_code,
            "curriculum_course_id": str(curriculum_course.curriculum_course_id),
            "class_section_id": str(section.class_section_id),
        }

    return client.portal.call(setup)


def _course_ids(client, db_session, scopes) -> set[str]:
    async def read():
        rows = (
            await db_session.execute(
                select(CurriculumCourse.course_id)
                .where(CurriculumCourse.course_scope.in_(scopes))
                .distinct()
            )
        ).scalars().all()
        return {str(row) for row in rows}

    return client.portal.call(read)


def _curriculum_course_ids(client, db_session, scopes) -> set[str]:
    async def read():
        rows = (
            await db_session.execute(
                select(CurriculumCourse.curriculum_course_id).where(
                    CurriculumCourse.course_scope.in_(scopes)
                )
            )
        ).scalars().all()
        return {str(row) for row in rows}

    return client.portal.call(read)


def _university_course_code(client, db_session) -> str | None:
    async def read():
        period_id = (
            await db_session.execute(
                select(AcademicPeriod.academic_period_id)
                .where(AcademicPeriod.is_active.is_(True))
                .order_by(AcademicPeriod.academic_year_start.desc())
                .limit(1)
            )
        ).scalar_one()
        return (
            await db_session.execute(
                select(Course.course_code)
                .join(
                    CurriculumCourse, CurriculumCourse.course_id == Course.course_id
                )
                .join(CourseOffering, CourseOffering.course_id == Course.course_id)
                .join(
                    OfferingComponent,
                    OfferingComponent.course_offering_id
                    == CourseOffering.course_offering_id,
                )
                .join(
                    ClassSection,
                    ClassSection.offering_component_id
                    == OfferingComponent.offering_component_id,
                )
                .where(
                    CurriculumCourse.course_scope == UNIVERSITY_SCOPE,
                    CourseOffering.academic_period_id == period_id,
                )
                .limit(1)
            )
        ).scalars().first()

    return client.portal.call(read)


def test_board_excludes_university_scope_classes(client, db_session, admin_headers):
    """Papan jadwal tidak memuat kelas MK universitas."""
    created = _create_university_class(client, db_session)
    response = client.get(f"{V1}/scheduling/board", headers=admin_headers)
    assert response.status_code == 200, response.text
    classes = response.json()["data"]["classes"]
    if not classes:
        pytest.skip("Papan jadwal kosong; pengecualian tidak dapat dibuktikan.")
    assert created["class_section_id"] not in {
        item["class_section_id"] for item in classes
    }
    university_ids = _course_ids(client, db_session, (UNIVERSITY_SCOPE,))
    assert all(item["course_id"] not in university_ids for item in classes)
    regular_ids = _course_ids(client, db_session, ("fakultas", "program_studi"))
    assert any(item["course_id"] in regular_ids for item in classes)


def test_preview_excludes_university_scope_classes(client, db_session, admin_headers):
    """Preview penugasan tidak memuat konteks MK universitas."""
    created = _create_university_class(client, db_session)
    response = client.get(f"{V1}/scheduling/assignments/preview", headers=admin_headers)
    assert response.status_code == 200, response.text
    groups = response.json()["data"]
    if not groups:
        pytest.skip("Preview kosong; pengecualian tidak dapat dibuktikan.")
    university_ids = _curriculum_course_ids(client, db_session, (UNIVERSITY_SCOPE,))
    assert all(group["curriculum_course_id"] not in university_ids for group in groups)
    assert all(
        item["curriculum_course_id"] not in university_ids
        for group in groups
        for item in group["classes"]
    )
    assert created["curriculum_course_id"] in university_ids
    regular_ids = _curriculum_course_ids(
        client, db_session, ("fakultas", "program_studi")
    )
    assert any(group["curriculum_course_id"] in regular_ids for group in groups)


def test_class_sections_hide_university_course(client, db_session, admin_headers):
    """Daftar seksi MK universitas kosong."""
    _create_university_class(client, db_session)
    code = _university_course_code(client, db_session)
    if code is None:
        pytest.skip("Tidak ada MK universitas dengan seksi pada periode aktif.")
    response = client.get(
        f"{V1}/class-sections", params={"course_code": code}, headers=admin_headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["data"] == []
    assert body["meta"]["total"] == 0


def test_instructor_candidates_reject_university_course(
    client, db_session, admin_headers
):
    """Pool calon dosen menolak MK universitas."""

    async def read():
        period_id = (
            await db_session.execute(
                select(AcademicPeriod.academic_period_id)
                .where(AcademicPeriod.is_active.is_(True))
                .order_by(AcademicPeriod.academic_year_start.desc())
                .limit(1)
            )
        ).scalar_one()
        course_id = (
            await db_session.execute(
                select(CurriculumCourse.curriculum_course_id).where(
                    CurriculumCourse.course_scope == UNIVERSITY_SCOPE,
                    CurriculumCourse.is_active.is_(True),
                )
            )
        ).scalars().first()
        return str(period_id), (None if course_id is None else str(course_id))

    period_id, course_id = client.portal.call(read)
    if course_id is None:
        pytest.skip("Tidak ada MK universitas aktif pada kurikulum.")

    response = client.get(
        f"{V1}/scheduling/instructor-candidates",
        params={
            "academic_period_id": period_id,
            "curriculum_course_id": course_id,
        },
        headers=admin_headers,
    )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "university_scope"
