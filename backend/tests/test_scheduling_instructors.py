"""Kontrak HTTP pemetaan referensi nama dosen ke akun LecturerProfile."""

import uuid

import pytest
from sqlalchemy import func, select

from auth import get_password_hash
from models import (
    AcademicPeriod,
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
CANDIDATES_PATH = f"{V1}/scheduling/instructor-candidates"
LEGACY_PATH = "/api/scheduling/instructor-references"
PASSWORD = "PemetaanUji2026!"


def _create_reference(
    client,
    db_session,
    *,
    program_code: str = "TSD",
    role: str = "teaching_team",
    instructor_name: str | None = None,
    user_id: str | None = None,
) -> dict:
    async def run():
        label = uuid.uuid4().hex[:8]
        active_period = (
            await db_session.execute(
                select(AcademicPeriod).where(AcademicPeriod.is_active.is_(True))
            )
        ).scalars().one()
        program = (
            await db_session.execute(
                select(StudyProgram).where(StudyProgram.program_code == program_code)
            )
        ).scalars().one()
        latest_year = (
            await db_session.execute(
                select(func.max(Curriculum.curriculum_year)).where(
                    Curriculum.study_program_id == program.study_program_id
                )
            )
        ).scalar()
        curriculum_year = (latest_year or 2025) + 1
        curriculum = Curriculum(
            study_program_id=program.study_program_id,
            curriculum_name=f"Kurikulum Uji {label}",
            curriculum_year=curriculum_year,
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
            academic_period_id=active_period.academic_period_id,
            instructor_name=instructor_name or f"Nama Teks {label}",
            instructor_role=role,
            user_id=uuid.UUID(user_id) if user_id else None,
            position=1,
        )
        db_session.add(reference)
        await db_session.commit()
        return {
            "reference_id": str(reference.instructor_reference_id),
            "academic_period_id": str(active_period.academic_period_id),
            "instructor_name": reference.instructor_name,
            "instructor_role": reference.instructor_role,
            "course_code": course.course_code,
            "course_name": course.course_name,
            "curriculum_course_id": str(offering.curriculum_course_id),
            "study_program_id": str(program.study_program_id),
            "study_program_code": program.program_code,
            "study_program_name": program.program_name,
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

    response = client.get(
        PATH, headers=admin_headers, params={"academic_period_id": reference["academic_period_id"]}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    item = _find(body["data"], reference["reference_id"])
    assert item == {
        "reference_id": reference["reference_id"],
        "instructor_name": reference["instructor_name"],
        "instructor_role": reference["instructor_role"],
        "course_code": reference["course_code"],
        "course_name": reference["course_name"],
        "curriculum_course_id": reference["curriculum_course_id"],
        "study_program_id": reference["study_program_id"],
        "study_program_code": "TSD",
        "study_program_name": reference["study_program_name"],
        "user_id": None,
        "is_mapped": False,
        "lecturer_name": None,
        "academic_period_id": reference["academic_period_id"],
        "position": 1,
        "can_auto_assign": False,
        "eligibility_reason": "external",
        "source_reference_id": None,
    }
    assert body["meta"]["unmapped"] >= 1

    legacy = client.get(
        LEGACY_PATH,
        headers=admin_headers,
        params={"academic_period_id": reference["academic_period_id"]},
    )
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
        url,
        headers=admin_headers,
        json={
            "academic_period_id": reference["academic_period_id"],
            "user_id": first["user_id"],
        },
    )
    assert mapped.status_code == 200, mapped.text
    assert mapped.json() == {
        "reference_id": reference["reference_id"],
        "instructor_name": first["full_name"],
        "instructor_role": reference["instructor_role"],
        "course_code": reference["course_code"],
        "course_name": reference["course_name"],
        "curriculum_course_id": reference["curriculum_course_id"],
        "study_program_id": reference["study_program_id"],
        "study_program_code": "TSD",
        "study_program_name": reference["study_program_name"],
        "user_id": first["user_id"],
        "is_mapped": True,
        "lecturer_name": first["full_name"],
        "academic_period_id": reference["academic_period_id"],
        "position": 1,
        "can_auto_assign": True,
        "eligibility_reason": "eligible",
        "source_reference_id": None,
    }
    again = client.patch(
        url,
        headers=admin_headers,
        json={
            "academic_period_id": reference["academic_period_id"],
            "user_id": first["user_id"],
        },
    )
    assert again.status_code == 200, again.text
    assert again.json() == mapped.json()

    changed = client.patch(
        url,
        headers=admin_headers,
        json={
            "academic_period_id": reference["academic_period_id"],
            "user_id": second["user_id"],
        },
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["user_id"] == second["user_id"]
    assert changed.json()["lecturer_name"] == second["full_name"]

    listed = client.get(
        PATH,
        headers=admin_headers,
        params={"academic_period_id": reference["academic_period_id"]},
    ).json()
    assert _find(listed["data"], reference["reference_id"])[
        "lecturer_name"
    ] == second["full_name"]

    cleared = client.patch(
        url,
        headers=admin_headers,
        json={"academic_period_id": reference["academic_period_id"], "user_id": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["user_id"] is None
    assert cleared.json()["is_mapped"] is False
    assert cleared.json()["lecturer_name"] is None


def test_missing_reference_returns_404(client, admin_headers, db_session):
    reference = _create_reference(client, db_session)
    response = client.patch(
        f"{PATH}/{uuid.uuid4()}",
        headers=admin_headers,
        json={
            "academic_period_id": reference["academic_period_id"],
            "user_id": str(uuid.uuid4()),
        },
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
        json={
            "academic_period_id": reference["academic_period_id"],
            "user_id": account["user_id"],
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "not_lecturer"


def test_student_cannot_read_or_map_references(
    client, student_headers, pj_headers, db_session
):
    reference = _create_reference(client, db_session)
    url = f"{PATH}/{reference['reference_id']}"

    student_list = client.get(
        PATH,
        headers=student_headers,
        params={"academic_period_id": reference["academic_period_id"]},
    )
    assert student_list.status_code == 403, student_list.text
    assert student_list.json()["error"]["code"] == "forbidden"

    pj_list = client.get(
        PATH,
        headers=pj_headers,
        params={"academic_period_id": reference["academic_period_id"]},
    )
    assert pj_list.status_code == 200, pj_list.text

    student_patch = client.patch(
        url,
        headers=student_headers,
        json={
            "academic_period_id": reference["academic_period_id"],
            "user_id": str(uuid.uuid4()),
        },
    )
    assert student_patch.status_code == 403, student_patch.text

    pj_patch = client.patch(
        url,
        headers=pj_headers,
        json={
            "academic_period_id": reference["academic_period_id"],
            "user_id": str(uuid.uuid4()),
        },
    )
    assert pj_patch.status_code == 422, pj_patch.text
    assert pj_patch.json()["error"]["code"] == "not_lecturer"


def test_admin_and_pj_can_create_and_delete_references(
    client, admin_headers, pj_headers, db_session
):
    reference = _create_reference(client, db_session)
    curriculum_course_id = reference["curriculum_course_id"]
    period_id = reference["academic_period_id"]

    created = client.post(
        PATH,
        headers=pj_headers,
        json={
            "curriculum_course_id": curriculum_course_id,
            "academic_period_id": period_id,
            "instructor_name": "Dosen Uji Tambah",
            "instructor_role": "teaching_team",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["instructor_role"] == "teaching_team"
    assert created.json()["is_mapped"] is False

    reference_id = created.json()["reference_id"]
    deleted = client.delete(
        f"{PATH}/{reference_id}",
        headers=admin_headers,
        params={"academic_period_id": period_id},
    )
    assert deleted.status_code == 204, deleted.text

    missing = client.delete(
        f"{PATH}/{reference_id}",
        headers=admin_headers,
        params={"academic_period_id": period_id},
    )
    assert missing.status_code == 404, missing.text

def test_create_reference_uses_account_full_name(client, admin_headers, db_session):
    reference = _create_reference(client, db_session, role="teaching_team")
    account = _create_account(client, db_session, role="lecturer", with_profile=True)

    created = client.post(
        PATH,
        headers=admin_headers,
        json={
            "curriculum_course_id": reference["curriculum_course_id"],
            "academic_period_id": reference["academic_period_id"],
            "instructor_name": "Nama Ketikan Manual",
            "instructor_role": "pjmk",
            "user_id": account["user_id"],
        },
    )

    assert created.status_code == 201, created.text
    assert created.json()["instructor_name"] == account["full_name"]


def test_partial_update_preserves_mapping(client, admin_headers, db_session):
    reference = _create_reference(client, db_session)
    other = _create_reference(client, db_session)
    lecturer = _create_account(client, db_session, role="lecturer", with_profile=True)
    url = f"{PATH}/{reference['reference_id']}"

    mapped = client.patch(
        url,
        headers=admin_headers,
        json={
            "academic_period_id": reference["academic_period_id"],
            "user_id": lecturer["user_id"],
        },
    )
    assert mapped.status_code == 200, mapped.text
    assert mapped.json()["user_id"] == lecturer["user_id"]

    renamed = client.patch(
        url,
        headers=admin_headers,
        json={
            "academic_period_id": reference["academic_period_id"],
            "instructor_name": "Nama Baru Uji",
            "instructor_role": "teaching_team",
        },
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json() == {
        **mapped.json(),
        "instructor_name": "Nama Baru Uji",
        "instructor_role": "teaching_team",
    }

    recoursed = client.patch(
        url,
        headers=admin_headers,
        json={
            "academic_period_id": reference["academic_period_id"],
            "curriculum_course_id": other["curriculum_course_id"],
        },
    )
    assert recoursed.status_code == 200, recoursed.text
    assert recoursed.json()["user_id"] == lecturer["user_id"]
    assert recoursed.json()["course_code"] == other["course_code"]
    assert recoursed.json()["course_name"] == other["course_name"]

    legacy = client.patch(
        f"{LEGACY_PATH}/{reference['reference_id']}",
        headers=admin_headers,
        json={
            "academic_period_id": reference["academic_period_id"],
            "instructor_name": "Nama Legacy Uji",
        },
    )
    assert legacy.status_code == 200, legacy.text
    assert legacy.json()["user_id"] == lecturer["user_id"]
    assert legacy.json()["instructor_name"] == "Nama Legacy Uji"


def test_update_validates_fields(client, admin_headers, db_session):
    reference = _create_reference(client, db_session)
    url = f"{PATH}/{reference['reference_id']}"

    invalid = client.patch(
        url,
        headers=admin_headers,
        json={
            "academic_period_id": reference["academic_period_id"],
            "curriculum_course_id": "bukan-uuid",
        },
    )
    assert invalid.status_code == 422, invalid.text
    assert invalid.json()["error"]["code"] == "invalid_uuid"

    missing = client.patch(
        url,
        headers=admin_headers,
        json={
            "academic_period_id": reference["academic_period_id"],
            "curriculum_course_id": str(uuid.uuid4()),
        },
    )
    assert missing.status_code == 404, missing.text
    assert missing.json()["error"]["code"] == "curriculum_course_not_found"

    long_name = client.patch(
        url,
        headers=admin_headers,
        json={
            "academic_period_id": reference["academic_period_id"],
            "instructor_name": "x" * 201,
        },
    )
    assert long_name.status_code == 422, long_name.text

    rejected = client.patch(
        url,
        headers=admin_headers,
        json={
            "academic_period_id": reference["academic_period_id"],
            "curriculum_course_id": str(uuid.uuid4()),
        },
    )
    assert rejected.status_code == 404, rejected.text

    listed = client.get(
        PATH,
        headers=admin_headers,
        params={"academic_period_id": reference["academic_period_id"]},
    ).json()
    item = _find(listed["data"], reference["reference_id"])
    assert item["instructor_name"] == reference["instructor_name"]
    assert item["course_code"] == reference["course_code"]


def test_pj_cannot_edit_or_delete_foreign_reference(
    client, pj_headers, admin_headers, db_session
):
    foreign = _create_reference(client, db_session, program_code="TI")
    url = f"{PATH}/{foreign['reference_id']}"

    patch = client.patch(
        url,
        headers=pj_headers,
        json={
            "academic_period_id": foreign["academic_period_id"],
            "instructor_name": "Dosen Asing",
        },
    )
    assert patch.status_code == 403, patch.text
    assert patch.json()["error"]["code"] == "forbidden"

    delete = client.delete(
        url, headers=pj_headers, params={"academic_period_id": foreign["academic_period_id"]}
    )
    assert delete.status_code == 403, delete.text
    assert delete.json()["error"]["code"] == "forbidden"

    legacy = client.patch(
        f"{LEGACY_PATH}/{foreign['reference_id']}",
        headers=pj_headers,
        json={
            "academic_period_id": foreign["academic_period_id"],
            "user_id": None,
        },
    )
    assert legacy.status_code == 403, legacy.text
    assert legacy.json()["error"]["code"] == "forbidden"

    allowed = client.patch(
        url,
        headers=admin_headers,
        json={
            "academic_period_id": foreign["academic_period_id"],
            "instructor_name": "Dosen Admin",
        },
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["instructor_name"] == "Dosen Admin"


def test_pj_cannot_create_reference_for_foreign_course(client, pj_headers, db_session):
    foreign = _create_reference(client, db_session, program_code="TI")

    response = client.post(
        PATH,
        headers=pj_headers,
        json={
            "curriculum_course_id": foreign["curriculum_course_id"],
            "academic_period_id": foreign["academic_period_id"],
            "instructor_name": "Dosen Uji Lintas Prodi",
        },
    )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "forbidden"


def test_list_references_filters_by_role(client, admin_headers, db_session):
    pjmk = _create_reference(client, db_session, role="pjmk")
    team = _create_reference(client, db_session, role="teaching_team")
    period_id = pjmk["academic_period_id"]

    filtered = client.get(
        PATH, headers=admin_headers, params={"academic_period_id": period_id, "role": "pjmk"}
    )
    assert filtered.status_code == 200, filtered.text
    body = filtered.json()
    ids = {item["reference_id"] for item in body["data"]}
    assert pjmk["reference_id"] in ids
    assert team["reference_id"] not in ids
    assert all(item["instructor_role"] == "pjmk" for item in body["data"])
    assert set(body["meta"]) == {"total", "mapped", "unmapped"}
    assert body["meta"]["total"] == len(body["data"])

    team_filtered = client.get(
        PATH,
        headers=admin_headers,
        params={"academic_period_id": period_id, "role": "teaching_team"},
    )
    assert team_filtered.status_code == 200, team_filtered.text
    team_ids = {item["reference_id"] for item in team_filtered.json()["data"]}
    assert team["reference_id"] in team_ids
    assert pjmk["reference_id"] not in team_ids
    assert all(
        item["instructor_role"] == "teaching_team"
        for item in team_filtered.json()["data"]
    )

    unfiltered = client.get(PATH, headers=admin_headers, params={"academic_period_id": period_id})
    assert unfiltered.status_code == 200, unfiltered.text
    unfiltered_ids = {item["reference_id"] for item in unfiltered.json()["data"]}
    assert {pjmk["reference_id"], team["reference_id"]} <= unfiltered_ids


def test_list_references_rejects_unknown_role(client, admin_headers, db_session):
    reference = _create_reference(client, db_session)
    response = client.get(
        PATH,
        headers=admin_headers,
        params={"academic_period_id": reference["academic_period_id"], "role": "ketua"},
    )
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "invalid_role"
    assert error["details"][0]["field"] == "role"


def test_second_pjmk_for_same_course_rejected_409(client, admin_headers, db_session):
    reference = _create_reference(client, db_session, role="pjmk")
    account = _create_account(client, db_session, role="lecturer", with_profile=True)
    period_id = reference["academic_period_id"]
    duplicate = client.post(
        PATH,
        headers=admin_headers,
        json={
            "academic_period_id": period_id,
            "curriculum_course_id": reference["curriculum_course_id"],
            "instructor_name": account["full_name"],
            "instructor_role": "pjmk",
            "user_id": account["user_id"],
        },
    )
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["error"]["code"] == "pjmk_exists"

    team = client.post(
        PATH,
        headers=admin_headers,
        json={
            "academic_period_id": period_id,
            "curriculum_course_id": reference["curriculum_course_id"],
            "instructor_name": "Anggota Tim Pengajar",
            "instructor_role": "teaching_team",
        },
    )
    assert team.status_code == 201, team.text
    assert team.json()["instructor_role"] == "teaching_team"

    listed = client.get(PATH, headers=admin_headers, params={"academic_period_id": period_id}).json()
    pjmk_items = [
        item
        for item in listed["data"]
        if item["curriculum_course_id"] == reference["curriculum_course_id"]
        and item["instructor_role"] == "pjmk"
    ]
    assert [item["reference_id"] for item in pjmk_items] == [
        reference["reference_id"]
    ]


def test_patch_to_pjmk_rejected_when_course_already_has_pjmk(
    client, admin_headers, db_session
):
    account = _create_account(client, db_session, role="lecturer", with_profile=True)
    pjmk = _create_reference(
        client, db_session, role="pjmk", user_id=account["user_id"]
    )
    other = _create_reference(
        client, db_session, role="pjmk", user_id=account["user_id"]
    )
    team = _create_reference(client, db_session, role="teaching_team")
    period_id = pjmk["academic_period_id"]

    created = client.post(
        PATH,
        headers=admin_headers,
        json={
            "academic_period_id": period_id,
            "curriculum_course_id": pjmk["curriculum_course_id"],
            "instructor_name": "Anggota Tim Pengajar",
            "instructor_role": "teaching_team",
        },
    )
    assert created.status_code == 201, created.text
    member_id = created.json()["reference_id"]

    promoted = client.patch(
        f"{PATH}/{member_id}",
        headers=admin_headers,
        json={
            "academic_period_id": period_id,
            "instructor_role": "pjmk",
            "user_id": account["user_id"],
        },
    )
    assert promoted.status_code == 409, promoted.text
    assert promoted.json()["error"]["code"] == "pjmk_exists"

    listed = client.get(PATH, headers=admin_headers, params={"academic_period_id": period_id}).json()
    unchanged = _find(listed["data"], member_id)
    assert unchanged["instructor_role"] == "teaching_team"

    moved = client.patch(
        f"{PATH}/{other['reference_id']}",
        headers=admin_headers,
        json={
            "academic_period_id": period_id,
            "curriculum_course_id": pjmk["curriculum_course_id"],
        },
    )
    assert moved.status_code == 409, moved.text
    assert moved.json()["error"]["code"] == "pjmk_exists"

    moved_back = client.get(PATH, headers=admin_headers, params={"academic_period_id": period_id}).json()
    assert _find(moved_back["data"], other["reference_id"])[
        "curriculum_course_id"
    ] == other["curriculum_course_id"]

    promoted_without_conflict = client.patch(
        f"{PATH}/{team['reference_id']}",
        headers=admin_headers,
        json={
            "academic_period_id": period_id,
            "instructor_role": "pjmk",
            "user_id": account["user_id"],
        },
    )
    assert promoted_without_conflict.status_code == 200, promoted_without_conflict.text
    assert promoted_without_conflict.json()["instructor_role"] == "pjmk"


def test_pjmk_cannot_be_added_as_team_member_by_mapped_account(
    client, admin_headers, db_session
):
    reference = _create_reference(client, db_session, role="pjmk")
    account = _create_account(client, db_session, role="lecturer", with_profile=True)

    mapped = client.patch(
        f"{PATH}/{reference['reference_id']}",
        headers=admin_headers,
        json={
            "academic_period_id": reference["academic_period_id"],
            "user_id": account["user_id"],
        },
    )
    assert mapped.status_code == 200, mapped.text

    conflict = client.post(
        PATH,
        headers=admin_headers,
        json={
            "academic_period_id": reference["academic_period_id"],
            "curriculum_course_id": reference["curriculum_course_id"],
            "instructor_name": "Anggota Tim Pengajar",
            "instructor_role": "teaching_team",
            "user_id": account["user_id"],
        },
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["error"]["code"] == "pjmk_is_team"


def test_pjmk_cannot_be_added_as_team_member_by_normalized_name(
    client, admin_headers, db_session
):
    reference = _create_reference(
        client,
        db_session,
        role="pjmk",
        instructor_name="Prof. Budi Santoso, S.T., M.T.",
    )

    conflict = client.post(
        PATH,
        headers=admin_headers,
        json={
            "academic_period_id": reference["academic_period_id"],
            "curriculum_course_id": reference["curriculum_course_id"],
            "instructor_name": "BUDI   SANTOSO",
            "instructor_role": "teaching_team",
        },
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["error"]["code"] == "pjmk_is_team"

    other_course = _create_reference(client, db_session)
    allowed = client.post(
        PATH,
        headers=admin_headers,
        json={
            "academic_period_id": other_course["academic_period_id"],
            "curriculum_course_id": other_course["curriculum_course_id"],
            "instructor_name": "BUDI   SANTOSO",
            "instructor_role": "teaching_team",
        },
    )
    assert allowed.status_code == 201, allowed.text


def test_duplicate_team_member_rejected_409(client, admin_headers, db_session):
    reference = _create_reference(
        client,
        db_session,
        role="teaching_team",
        instructor_name="Citra Dewi, S.Kom.",
    )

    duplicate = client.post(
        PATH,
        headers=admin_headers,
        json={
            "academic_period_id": reference["academic_period_id"],
            "curriculum_course_id": reference["curriculum_course_id"],
            "instructor_name": "citra dewi",
            "instructor_role": "teaching_team",
        },
    )
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["error"]["code"] == "team_member_exists"

    account = _create_account(client, db_session, role="lecturer", with_profile=True)
    first = client.post(
        PATH,
        headers=admin_headers,
        json={
            "academic_period_id": reference["academic_period_id"],
            "curriculum_course_id": reference["curriculum_course_id"],
            "instructor_name": "Anggota Lain",
            "instructor_role": "teaching_team",
            "user_id": account["user_id"],
        },
    )
    assert first.status_code == 201, first.text
    mapped_duplicate = client.post(
        PATH,
        headers=admin_headers,
        json={
            "academic_period_id": reference["academic_period_id"],
            "curriculum_course_id": reference["curriculum_course_id"],
            "instructor_name": "Anggota Lain Lagi",
            "instructor_role": "teaching_team",
            "user_id": account["user_id"],
        },
    )
    assert mapped_duplicate.status_code == 409, mapped_duplicate.text
    assert mapped_duplicate.json()["error"]["code"] == "team_member_exists"


def test_patch_to_team_role_rejects_pjmk_and_duplicates(
    client, admin_headers, db_session
):
    pjmk = _create_reference(
        client,
        db_session,
        role="pjmk",
        instructor_name="Dewi Lestari, S.Si., M.Sc.",
    )
    team = _create_reference(
        client,
        db_session,
        role="teaching_team",
        instructor_name="Dewi Lestari",
    )

    moved = client.patch(
        f"{PATH}/{team['reference_id']}",
        headers=admin_headers,
        json={
            "academic_period_id": pjmk["academic_period_id"],
            "curriculum_course_id": pjmk["curriculum_course_id"],
        },
    )
    assert moved.status_code == 409, moved.text
    assert moved.json()["error"]["code"] == "pjmk_is_team"

    course = _create_reference(
        client,
        db_session,
        role="teaching_team",
        instructor_name="Rudi Hartono",
    )
    second = client.post(
        PATH,
        headers=admin_headers,
        json={
            "academic_period_id": course["academic_period_id"],
            "curriculum_course_id": course["curriculum_course_id"],
            "instructor_name": "Siti Aminah",
            "instructor_role": "teaching_team",
        },
    )
    assert second.status_code == 201, second.text
    renamed = client.patch(
        f"{PATH}/{second.json()['reference_id']}",
        headers=admin_headers,
        json={
            "academic_period_id": course["academic_period_id"],
            "instructor_name": "RUDI   HARTONO",
        },
    )
    assert renamed.status_code == 409, renamed.text
    assert renamed.json()["error"]["code"] == "team_member_exists"

    # Menimpa nama baris itu sendiri bukan duplikat.
    self_rename = client.patch(
        f"{PATH}/{course['reference_id']}",
        headers=admin_headers,
        json={
            "academic_period_id": course["academic_period_id"],
            "curriculum_course_id": course["curriculum_course_id"],
            "instructor_name": "Rudi Hartono, S.T.",
        },
    )
    assert self_rename.status_code == 200, self_rename.text


def test_candidates_exclude_pjmk_when_course_given(client, admin_headers, db_session):
    reference = _create_reference(client, db_session, role="pjmk")
    account = _create_account(client, db_session, role="lecturer", with_profile=True)
    mapped = client.patch(
        f"{PATH}/{reference['reference_id']}",
        headers=admin_headers,
        json={
            "academic_period_id": reference["academic_period_id"],
            "user_id": account["user_id"],
        },
    )
    assert mapped.status_code == 200, mapped.text

    search = {
        "academic_period_id": reference["academic_period_id"],
        "search": account["full_name"],
    }
    unfiltered = client.get(CANDIDATES_PATH, headers=admin_headers, params=search)
    assert unfiltered.status_code == 200, unfiltered.text
    assert account["user_id"] in {
        item["user_id"] for item in unfiltered.json()["data"]
    }

    filtered = client.get(
        CANDIDATES_PATH,
        headers=admin_headers,
        params={**search, "curriculum_course_id": reference["curriculum_course_id"]},
    )
    assert filtered.status_code == 200, filtered.text
    body = filtered.json()
    assert body["data"] == []
    assert body["meta"]["total"] == 0
    assert body["meta"]["page"] == 1
    assert body["meta"]["pages"] == 0

    other = _create_reference(client, db_session, role="teaching_team")
    other_course = client.get(
        CANDIDATES_PATH,
        headers=admin_headers,
        params={**search, "curriculum_course_id": other["curriculum_course_id"]},
    )
    assert other_course.status_code == 200, other_course.text
    assert account["user_id"] in {
        item["user_id"] for item in other_course.json()["data"]
    }


def test_candidates_unknown_course_returns_404(client, admin_headers, db_session):
    reference = _create_reference(client, db_session)
    period_id = reference["academic_period_id"]
    missing = client.get(
        CANDIDATES_PATH,
        headers=admin_headers,
        params={"academic_period_id": period_id, "curriculum_course_id": str(uuid.uuid4())},
    )
    assert missing.status_code == 404, missing.text
    assert missing.json()["error"]["code"] == "course_not_found"

    invalid = client.get(
        CANDIDATES_PATH,
        headers=admin_headers,
        params={"academic_period_id": period_id, "curriculum_course_id": "bukan-uuid"},
    )
    assert invalid.status_code == 404, invalid.text
    assert invalid.json()["error"]["code"] == "course_not_found"


def test_candidates_course_filter_respects_pj_scope(
    client, pj_headers, db_session
):
    foreign = _create_reference(client, db_session, program_code="TI")

    response = client.get(
        CANDIDATES_PATH,
        headers=pj_headers,
        params={
            "academic_period_id": foreign["academic_period_id"],
            "curriculum_course_id": foreign["curriculum_course_id"],
        },
    )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "forbidden"

