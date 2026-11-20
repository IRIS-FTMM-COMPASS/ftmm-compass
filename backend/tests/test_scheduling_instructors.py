"""Kontrak HTTP pemetaan referensi nama dosen ke akun LecturerProfile."""

import uuid

import pytest
from sqlalchemy import select

from auth import get_password_hash
from models import (
    Course,
    CourseInstructorReference,
    Curriculum,
    CurriculumCourse,
    LecturerProfile,
    StudyProgram,
    User,
)

V1 = "/api/v1"
PATH = f"{V1}/scheduling/instructor-references"
PASSWORD = "PemetaanUji2026!"


def _create_reference(client, db_session) -> dict:
    async def run():
        label = uuid.uuid4().hex[:8]
        program = (
            await db_session.execute(
                select(StudyProgram).where(StudyProgram.program_code == "TSD")
            )
        ).scalars().one()
        curriculum = Curriculum(
            study_program_id=program.study_program_id,
            curriculum_name=f"Kurikulum Uji {label}",
            curriculum_year=2026,
        )
        db_session.add(curriculum)
        await db_session.flush()
        course = Course(
            course_code=f"UJI{uuid.uuid4().int % 10000:04d}",
            course_name=f"Mata Kuliah Uji {label}",
        )
        db_session.add(course)
        await db_session.flush()
        offering = CurriculumCourse(
            curriculum_id=curriculum.curriculum_id,
            course_id=course.course_id,
            credits_total=3,
            course_type="pilihan",
        )
        db_session.add(offering)
        await db_session.flush()
        reference = CourseInstructorReference(
            curriculum_course_id=offering.curriculum_course_id,
            instructor_name=f"Nama Teks {label}",
            instructor_role="pjmk",
        )
        db_session.add(reference)
        await db_session.commit()
        return {
            "reference_id": str(reference.instructor_reference_id),
            "instructor_name": reference.instructor_name,
            "instructor_role": reference.instructor_role,
            "course_code": course.course_code,
            "course_name": course.course_name,
        }

    return client.portal.call(run)


def _create_account(client, db_session, *, role: str, with_profile: bool) -> dict:
    async def run():
        label = uuid.uuid4().hex[:8]
        email = f"pemetaan.{label}@ftmm.unair.ac.id"
        full_name = f"Akun Uji {label}"
        user = User(
            email=email,
            full_name=full_name,
            role=role,
            password_hash=get_password_hash(PASSWORD),
        )
        db_session.add(user)
        await db_session.flush()
        if with_profile:
            program = (
                await db_session.execute(
                    select(StudyProgram).where(StudyProgram.program_code == "TSD")
                )
            ).scalars().one()
            db_session.add(
                LecturerProfile(
                    user_id=user.user_id,
                    study_program_id=program.study_program_id,
                    is_program_coordinator=False,
                )
            )
        await db_session.commit()
        return {"user_id": str(user.user_id), "full_name": full_name}

    return client.portal.call(run)


def _find(data: list[dict], reference_id: str) -> dict:
    return next(item for item in data if item["reference_id"] == reference_id)


def test_unmapped_reference_stays_visible_with_course_info(client, admin_headers, db_session):
    reference = _create_reference(client, db_session)

    response = client.get(PATH, headers=admin_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    item = _find(body["data"], reference["reference_id"])
    assert item == {
        "reference_id": reference["reference_id"],
        "instructor_name": reference["instructor_name"],
        "instructor_role": reference["instructor_role"],
        "course_code": reference["course_code"],
        "course_name": reference["course_name"],
        "user_id": None,
        "is_mapped": False,
        "lecturer_name": None,
    }
    assert body["meta"]["unmapped"] >= 1

    legacy = client.get("/api/scheduling/instructor-references", headers=admin_headers)
    assert legacy.status_code == 200, legacy.text
    assert legacy.json() == body


def test_mapping_is_idempotent_changeable_and_clearable(
    client, admin_headers, db_session
):
    reference = _create_reference(client, db_session)
    first = _create_account(client, db_session, role="lecturer", with_profile=True)
    second = _create_account(client, db_session, role="lecturer", with_profile=True)
    url = f"{PATH}/{reference['reference_id']}"

    mapped = client.patch(
        url, headers=admin_headers, json={"user_id": first["user_id"]}
    )
    assert mapped.status_code == 200, mapped.text
    assert mapped.json() == {
        "reference_id": reference["reference_id"],
        "instructor_name": reference["instructor_name"],
        "instructor_role": reference["instructor_role"],
        "course_code": reference["course_code"],
        "course_name": reference["course_name"],
        "user_id": first["user_id"],
        "is_mapped": True,
        "lecturer_name": first["full_name"],
    }

    again = client.patch(
        url, headers=admin_headers, json={"user_id": first["user_id"]}
    )
    assert again.status_code == 200, again.text
    assert again.json() == mapped.json()

    changed = client.patch(
        url, headers=admin_headers, json={"user_id": second["user_id"]}
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["user_id"] == second["user_id"]
    assert changed.json()["lecturer_name"] == second["full_name"]

    listed = client.get(PATH, headers=admin_headers).json()
    assert _find(listed["data"], reference["reference_id"])[
        "lecturer_name"
    ] == second["full_name"]

    cleared = client.patch(url, headers=admin_headers, json={"user_id": None})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["user_id"] is None
    assert cleared.json()["is_mapped"] is False
    assert cleared.json()["lecturer_name"] is None


def test_missing_reference_returns_404(client, admin_headers):
    response = client.patch(
        f"{PATH}/{uuid.uuid4()}",
        headers=admin_headers,
        json={"user_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "reference_not_found"


@pytest.mark.parametrize(
    ("role", "with_profile"),
    [
        pytest.param("student", False, id="student_account"),
        pytest.param("lecturer", False, id="lecturer_without_profile"),
    ],
)
def test_account_without_lecturer_profile_rejected_422(
    client, admin_headers, db_session, role, with_profile
):
    reference = _create_reference(client, db_session)
    account = _create_account(client, db_session, role=role, with_profile=with_profile)

    response = client.patch(
        f"{PATH}/{reference['reference_id']}",
        headers=admin_headers,
        json={"user_id": account["user_id"]},
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "not_lecturer"


def test_non_admin_cannot_read_or_map_references(
    client, student_headers, pj_headers, db_session
):
    reference = _create_reference(client, db_session)
    url = f"{PATH}/{reference['reference_id']}"

    student_list = client.get(PATH, headers=student_headers)
    assert student_list.status_code == 403, student_list.text
    assert student_list.json()["error"]["code"] == "forbidden"

    pj_list = client.get(PATH, headers=pj_headers)
    assert pj_list.status_code == 403, pj_list.text

    student_patch = client.patch(
        url, headers=student_headers, json={"user_id": str(uuid.uuid4())}
    )
    assert student_patch.status_code == 403, student_patch.text

    pj_patch = client.patch(
        url, headers=pj_headers, json={"user_id": str(uuid.uuid4())}
    )
    assert pj_patch.status_code == 403, pj_patch.text
