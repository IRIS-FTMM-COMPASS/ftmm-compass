"""Kontrak HTTP pemetaan PJ MK dan Tim Pengajar per periode akademik."""

import json
import uuid
from importlib import import_module
from typing import Any

from sqlalchemy import func, select, text

from auth import get_password_hash
from models import (
    AcademicPeriod,
    ClassInstructorAssignment,
    Course,
    CourseInstructorReference,
    Curriculum,
    CurriculumCourse,
    LecturerProfile,
    SchedulePeriodSettings,
    StudyProgram,
    User,
)

V1 = "/api/v1"
LEGACY = "/api"
PATH = f"{V1}/scheduling/instructor-references"
COPY_PATH = f"{PATH}/copy"
ORDER_PATH = f"{PATH}/order"
PASSWORD = "PemetaanPeriodeUji2026!"


def _periods(client, db_session, count: int = 3) -> list[str]:
    async def setup():
        max_year = (
            await db_session.execute(select(func.max(AcademicPeriod.academic_year_start)))
        ).scalar()
        base_year = int(max_year or 2024) + 20
        rows = []
        for index in range(count):
            period = AcademicPeriod(
                academic_year_start=base_year + index,
                semester_number=1,
                term="ganjil",
                is_active=False,
            )
            db_session.add(period)
            await db_session.flush()
            rows.append(str(period.academic_period_id))
        await db_session.commit()
        return rows

    return client.portal.call(setup)


def _course(client, db_session, *, program_code: str = "TSD") -> dict[str, str]:
    async def setup():
        label = uuid.uuid4().hex[:8]
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
        curriculum = Curriculum(
            study_program_id=program.study_program_id,
            curriculum_name=f"Kurikulum Periode {label}",
            curriculum_year=(latest_year or 2025) + 1,
        )
        db_session.add(curriculum)
        await db_session.flush()
        course = Course(
            course_code=f"PRD{uuid.uuid4().int % 10000:04d}",
            course_name=f"Mata Kuliah Periode {label}",
        )
        db_session.add(course)
        await db_session.flush()
        offering = CurriculumCourse(
            curriculum_id=curriculum.curriculum_id,
            course_id=course.course_id,
            credits_total=3,
            course_type="wajib",
        )
        db_session.add(offering)
        await db_session.flush()
        await db_session.commit()
        return {
            "curriculum_course_id": str(offering.curriculum_course_id),
            "course_code": course.course_code,
            "study_program_id": str(program.study_program_id),
        }

    return client.portal.call(setup)


def _lecturer(
    client,
    db_session,
    *,
    program_code: str = "TSD",
    active: bool = True,
    role: str = "lecturer",
) -> dict[str, Any]:
    async def setup():
        label = uuid.uuid4().hex[:8]
        program = (
            await db_session.execute(
                select(StudyProgram).where(StudyProgram.program_code == program_code)
            )
        ).scalars().one()
        user = User(
            email=f"periode.{label}@ftmm.unair.ac.id",
            full_name=f"Dosen Periode {label}",
            role=role,
            is_active=active,
            password_hash=get_password_hash(PASSWORD),
        )
        db_session.add(user)
        await db_session.flush()
        db_session.add(
            LecturerProfile(
                user_id=user.user_id,
                study_program_id=program.study_program_id,
                is_program_coordinator=False,
            )
        )
        await db_session.commit()
        return {
            "user_id": str(user.user_id),
            "full_name": user.full_name,
            "study_program_id": str(program.study_program_id),
        }

    return client.portal.call(setup)


def _create_reference(
    client,
    headers,
    case: dict[str, str],
    period_id: str,
    *,
    role: str = "teaching_team",
    name: str = "Dosen Eksternal",
    user_id: str | None = None,
    position: int | None = None,
    prefix: str = V1,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "curriculum_course_id": case["curriculum_course_id"],
        "instructor_name": name,
        "instructor_role": role,
        "user_id": user_id,
        "academic_period_id": period_id,
    }
    if position is not None:
        payload["position"] = position
    response = client.post(
        f"{prefix}/scheduling/instructor-references", headers=headers, json=payload
    )
    assert response.status_code == 201, response.text
    return response.json()


def _listed(client, headers, period_id: str, *, prefix: str = V1) -> list[dict]:
    params = {"academic_period_id": period_id}
    response = client.get(
        f"{prefix}/scheduling/instructor-references", headers=headers, params=params
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _by_id(items: list[dict], reference_id: str) -> dict:
    return next(item for item in items if item["reference_id"] == reference_id)


async def _mapping_audit(db_session, actor_id: str) -> list[dict[str, Any]]:
    rows = (
        await db_session.execute(
            text(
                "SELECT action, actor_user_id, field_name, old_value, new_value, "
                "created_at FROM admin_authority_traces "
                "WHERE actor_user_id = CAST(:actor_id AS uuid) "
                "AND action LIKE 'instructor_reference_%' "
                "ORDER BY created_at, action"
            ),
            {"actor_id": actor_id},
        )
    ).mappings().all()
    return [dict(row) for row in rows]


def _actor_id(client, db_session, email: str = "admin@ftmm.unair.ac.id") -> str:
    async def read():
        user = (
            await db_session.execute(select(User).where(User.email == email))
        ).scalars().one()
        return str(user.user_id)

    return client.portal.call(read)


def test_instructor_reference_endpoints_require_academic_period(
    client, db_session, admin_headers
):
    period_id = _periods(client, db_session, count=1)[0]
    case = _course(client, db_session)
    reference_id = str(uuid.uuid4())
    for prefix in (V1, LEGACY):
        path = f"{prefix}/scheduling/instructor-references"
        assert client.get(path, headers=admin_headers).status_code == 422
        assert client.get(
            f"{prefix}/scheduling/instructor-candidates", headers=admin_headers
        ).status_code == 422
        assert client.post(
            path,
            headers=admin_headers,
            json={
                "curriculum_course_id": case["curriculum_course_id"],
                "instructor_name": "Tanpa Periode",
                "instructor_role": "teaching_team",
            },
        ).status_code == 422
        assert client.patch(
            f"{path}/{reference_id}",
            headers=admin_headers,
            json={"instructor_name": "Tanpa Periode"},
        ).status_code == 422
        assert client.delete(
            f"{path}/{reference_id}", headers=admin_headers
        ).status_code == 422

    wrong_period = client.patch(
        f"{PATH}/{reference_id}",
        headers=admin_headers,
        json={"academic_period_id": period_id, "instructor_name": "Periode Salah"},
    )
    assert wrong_period.status_code == 404
    assert wrong_period.json()["error"]["code"] == "reference_not_found"


def test_period_filter_isolates_rows_and_uses_canonical_shape(
    client, db_session, admin_headers
):
    periods = _periods(client, db_session, count=2)
    case = _course(client, db_session)
    lecturer = _lecturer(client, db_session)
    first = _create_reference(
        client,
        admin_headers,
        case,
        periods[0],
        role="pjmk",
        user_id=lecturer["user_id"],
        name=lecturer["full_name"],
    )
    second = _create_reference(
        client,
        admin_headers,
        case,
        periods[1],
        role="pjmk",
        user_id=lecturer["user_id"],
        name=lecturer["full_name"],
    )
    async def create_global_source():
        db_session.add(
            CourseInstructorReference(
                curriculum_course_id=uuid.UUID(case["curriculum_course_id"]),
                instructor_name="PJ MK Legacy",
                instructor_role="pjmk",
            )
        )
        await db_session.commit()

    client.portal.call(create_global_source)

    first_items = _listed(client, admin_headers, periods[0])
    second_items = _listed(client, admin_headers, periods[1])
    first_item = _by_id(first_items, first["reference_id"])
    second_item = _by_id(second_items, second["reference_id"])
    assert first_item["academic_period_id"] == periods[0]
    assert second_item["academic_period_id"] == periods[1]
    assert first["reference_id"] not in {item["reference_id"] for item in second_items}
    assert second["reference_id"] not in {item["reference_id"] for item in first_items}
    assert all(item["academic_period_id"] == periods[0] for item in first_items)
    assert all(item["academic_period_id"] == periods[1] for item in second_items)
    assert set(first_item) == {
        "reference_id",
        "instructor_name",
        "instructor_role",
        "course_code",
        "course_name",
        "curriculum_course_id",
        "study_program_id",
        "study_program_code",
        "study_program_name",
        "user_id",
        "is_mapped",
        "lecturer_name",
        "academic_period_id",
        "position",
        "can_auto_assign",
        "eligibility_reason",
        "source_reference_id",
    }
    assert first_item["position"] == 1
    assert first_item["can_auto_assign"] is True
    assert first_item["eligibility_reason"] == "eligible"
    assert first_item["source_reference_id"] is None

    canonical = client.get(
        PATH, headers=admin_headers, params={"academic_period_id": periods[0]}
    )
    mirror = client.get(
        f"{LEGACY}/scheduling/instructor-references",
        headers=admin_headers,
        params={"academic_period_id": periods[0]},
    )
    assert canonical.status_code == mirror.status_code == 200
    assert canonical.json() == mirror.json()

    missing = client.get(
        PATH, headers=admin_headers, params={"academic_period_id": str(uuid.uuid4())}
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "period_not_found"
    mirrored_patch = client.patch(
        f"{LEGACY}/scheduling/instructor-references/{first['reference_id']}",
        headers=admin_headers,
        json={
            "academic_period_id": periods[0],
            "instructor_name": lecturer["full_name"],
        },
    )
    assert mirrored_patch.status_code == 200
    assert mirrored_patch.json() == first


def test_migrated_null_positions_are_derived_per_course(
    client, db_session, admin_headers
):
    period_id = _periods(client, db_session, count=1)[0]
    first_case = _course(client, db_session)
    second_case = _course(client, db_session)
    lecturer = _lecturer(client, db_session)

    async def setup():
        db_session.add_all(
            [
                CourseInstructorReference(
                    curriculum_course_id=uuid.UUID(case["curriculum_course_id"]),
                    academic_period_id=uuid.UUID(period_id),
                    instructor_name=lecturer["full_name"],
                    instructor_role="pjmk",
                    user_id=uuid.UUID(lecturer["user_id"]),
                )
                for case in (first_case, second_case)
            ]
        )
        await db_session.commit()

    client.portal.call(setup)
    items = _listed(client, admin_headers, period_id)
    assert len(items) == 2
    assert {item["position"] for item in items} == {1}
    assert all(item["can_auto_assign"] is True for item in items)


def test_one_pjmk_per_curriculum_and_period(client, db_session, admin_headers):
    periods = _periods(client, db_session, count=2)
    case = _course(client, db_session)
    first = _lecturer(client, db_session)
    second = _lecturer(client, db_session)
    _create_reference(
        client,
        admin_headers,
        case,
        periods[0],
        role="pjmk",
        user_id=first["user_id"],
        name=first["full_name"],
    )
    _create_reference(
        client,
        admin_headers,
        case,
        periods[1],
        role="pjmk",
        user_id=second["user_id"],
        name=second["full_name"],
    )

    duplicate = client.post(
        PATH,
        headers=admin_headers,
        json={
            "curriculum_course_id": case["curriculum_course_id"],
            "academic_period_id": periods[0],
            "instructor_name": second["full_name"],
            "instructor_role": "pjmk",
            "user_id": second["user_id"],
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "pjmk_exists"

    member = _create_reference(client, admin_headers, case, periods[0])
    promoted = client.patch(
        f"{PATH}/{member['reference_id']}",
        headers=admin_headers,
        json={
            "academic_period_id": periods[0],
            "instructor_role": "pjmk",
            "user_id": second["user_id"],
        },
    )
    assert promoted.status_code == 409
    assert promoted.json()["error"]["code"] == "pjmk_exists"


def test_period_pjmk_requires_active_lecturer_and_external_members_are_ineligible(
    client, db_session, admin_headers
):
    period_id = _periods(client, db_session, count=1)[0]
    case = _course(client, db_session)
    active = _lecturer(client, db_session)
    inactive = _lecturer(client, db_session, active=False)

    missing_account = client.post(
        PATH,
        headers=admin_headers,
        json={
            "curriculum_course_id": case["curriculum_course_id"],
            "academic_period_id": period_id,
            "instructor_name": "PJ MK Tanpa Akun",
            "instructor_role": "pjmk",
        },
    )
    assert missing_account.status_code == 422
    assert missing_account.json()["error"]["code"] == "pjmk_requires_account"

    inactive_account = client.post(
        PATH,
        headers=admin_headers,
        json={
            "curriculum_course_id": case["curriculum_course_id"],
            "academic_period_id": period_id,
            "instructor_name": inactive["full_name"],
            "instructor_role": "pjmk",
            "user_id": inactive["user_id"],
        },
    )
    assert inactive_account.status_code == 422
    assert inactive_account.json()["error"]["code"] == "pjmk_requires_account"

    pjmk = _create_reference(
        client,
        admin_headers,
        case,
        period_id,
        role="pjmk",
        user_id=active["user_id"],
        name=active["full_name"],
    )
    assert pjmk["position"] == 1
    cleared = client.patch(
        f"{PATH}/{pjmk['reference_id']}",
        headers=admin_headers,
        json={"academic_period_id": period_id, "user_id": None},
    )
    assert cleared.status_code == 422
    assert cleared.json()["error"]["code"] == "pjmk_requires_account"

    external = _create_reference(
        client, admin_headers, case, period_id, name="Narasumber Eksternal"
    )
    assert external["position"] == 2
    assert external["can_auto_assign"] is False
    assert external["eligibility_reason"] == "external"

    inactive_member = _create_reference(
        client,
        admin_headers,
        case,
        period_id,
        name=inactive["full_name"],
        user_id=inactive["user_id"],
    )
    assert inactive_member["is_mapped"] is True
    assert inactive_member["can_auto_assign"] is False
    assert inactive_member["eligibility_reason"] == "inactive_account"


def test_copy_forward_preserves_order_provenance_and_is_idempotent(
    client, db_session, admin_headers
):
    periods = _periods(client, db_session, count=3)
    case = _course(client, db_session)
    lecturer = _lecturer(client, db_session)
    member = _lecturer(client, db_session)
    pjmk = _create_reference(
        client,
        admin_headers,
        case,
        periods[0],
        role="pjmk",
        user_id=lecturer["user_id"],
        name=lecturer["full_name"],
    )
    first_member = _create_reference(
        client,
        admin_headers,
        case,
        periods[0],
        name="Anggota Pertama",
        user_id=member["user_id"],
    )
    second_member = _create_reference(
        client, admin_headers, case, periods[0], name="Anggota Kedua"
    )
    ordered = client.put(
        ORDER_PATH,
        headers=admin_headers,
        json={
            "curriculum_course_id": case["curriculum_course_id"],
            "academic_period_id": periods[0],
            "ordered_reference_ids": [
                pjmk["reference_id"],
                second_member["reference_id"],
                first_member["reference_id"],
            ],
        },
    )
    assert ordered.status_code == 200, ordered.text

    copied = client.post(
        COPY_PATH,
        headers=admin_headers,
        json={
            "from_academic_period_id": periods[0],
            "academic_period_id": periods[1],
        },
    )
    assert copied.status_code == 200, copied.text
    body = copied.json()
    assert body["meta"] == {"copied": 3, "skipped": 0, "total": 3}
    by_source = {
        item["source_reference_id"]: item
        for item in body["data"]
    }
    assert by_source[pjmk["reference_id"]]["position"] == 1
    assert by_source[second_member["reference_id"]]["position"] == 2
    assert by_source[first_member["reference_id"]]["position"] == 3

    renamed = client.patch(
        f"{PATH}/{by_source[second_member['reference_id']]['reference_id']}",
        headers=admin_headers,
        json={
            "academic_period_id": periods[1],
            "instructor_name": "Nama Yang Dipertahankan",
        },
    )
    assert renamed.status_code == 200, renamed.text
    audit_count = len(
        client.portal.call(_mapping_audit, db_session, _actor_id(client, db_session))
    )
    repeated = client.post(
        COPY_PATH,
        headers=admin_headers,
        json={
            "from_academic_period_id": periods[0],
            "academic_period_id": periods[1],
        },
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["meta"] == {"copied": 0, "skipped": 3, "total": 3}
    target = _listed(client, admin_headers, periods[1])
    assert _by_id(target, renamed.json()["reference_id"])["instructor_name"] == (
        "Nama Yang Dipertahankan"
    )
    assert len(target) == 3
    assert len(
        client.portal.call(_mapping_audit, db_session, _actor_id(client, db_session))
    ) == audit_count

    invalid = client.post(
        COPY_PATH,
        headers=admin_headers,
        json={
            "from_academic_period_id": periods[1],
            "academic_period_id": periods[0],
        },
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_source_period"

    mirrored = client.post(
        f"{LEGACY}/scheduling/instructor-references/copy",
        headers=admin_headers,
        json={
            "from_academic_period_id": periods[0],
            "academic_period_id": periods[2],
        },
    )
    assert mirrored.status_code == 200, mirrored.text
    assert mirrored.json()["meta"] == {"copied": 3, "skipped": 0, "total": 3}


def test_ordered_pool_validates_members_and_is_idempotent(
    client, db_session, admin_headers
):
    period_id = _periods(client, db_session, count=1)[0]
    case = _course(client, db_session)
    lecturer = _lecturer(client, db_session)
    pjmk = _create_reference(
        client,
        admin_headers,
        case,
        period_id,
        role="pjmk",
        user_id=lecturer["user_id"],
        name=lecturer["full_name"],
    )
    first = _create_reference(client, admin_headers, case, period_id, name="Anggota A")
    second = _create_reference(client, admin_headers, case, period_id, name="Anggota B")
    payload = {
        "curriculum_course_id": case["curriculum_course_id"],
        "academic_period_id": period_id,
        "ordered_reference_ids": [
            pjmk["reference_id"],
            second["reference_id"],
            first["reference_id"],
        ],
    }
    ordered = client.put(ORDER_PATH, headers=admin_headers, json=payload)
    assert ordered.status_code == 200, ordered.text
    assert [item["position"] for item in ordered.json()["data"]] == [1, 2, 3]
    assert [item["reference_id"] for item in ordered.json()["data"]] == payload[
        "ordered_reference_ids"
    ]

    wrong_lead = client.put(
        ORDER_PATH,
        headers=admin_headers,
        json={**payload, "ordered_reference_ids": [second["reference_id"], pjmk["reference_id"], first["reference_id"]]},
    )
    assert wrong_lead.status_code == 422
    assert wrong_lead.json()["error"]["code"] == "invalid_pool_order"

    duplicate = client.put(
        ORDER_PATH,
        headers=admin_headers,
        json={
            **payload,
            "ordered_reference_ids": [
                pjmk["reference_id"],
                first["reference_id"],
                first["reference_id"],
            ],
        },
    )
    assert duplicate.status_code == 422
    assert duplicate.json()["error"]["code"] == "invalid_pool_order"

    missing = client.put(
        ORDER_PATH,
        headers=admin_headers,
        json={**payload, "ordered_reference_ids": [pjmk["reference_id"], first["reference_id"]]},
    )
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "invalid_pool_order"

    audit_count = len(
        client.portal.call(_mapping_audit, db_session, _actor_id(client, db_session))
    )
    repeated = client.put(ORDER_PATH, headers=admin_headers, json=payload)
    assert repeated.status_code == 200, repeated.text
    assert repeated.json() == ordered.json()
    assert len(
        client.portal.call(_mapping_audit, db_session, _actor_id(client, db_session))
    ) == audit_count

    legacy_order = client.put(
        f"{LEGACY}/scheduling/instructor-references/order",
        headers=admin_headers,
        json=payload,
    )
    assert legacy_order.status_code == 200
    assert legacy_order.json() == ordered.json()


def test_position_validation_and_pjmk_insertion_moves_team_members(
    client, db_session, admin_headers
):
    period_id = _periods(client, db_session, count=1)[0]
    case = _course(client, db_session)
    team = _create_reference(client, admin_headers, case, period_id, name="Anggota Awal")
    assert team["position"] == 1
    lecturer = _lecturer(client, db_session)
    invalid_position = client.post(
        PATH,
        headers=admin_headers,
        json={
            "curriculum_course_id": case["curriculum_course_id"],
            "academic_period_id": period_id,
            "instructor_name": lecturer["full_name"],
            "instructor_role": "pjmk",
            "user_id": lecturer["user_id"],
            "position": 2,
        },
    )
    assert invalid_position.status_code == 422
    assert invalid_position.json()["error"]["code"] == "invalid_position"
    pjmk = _create_reference(
        client,
        admin_headers,
        case,
        period_id,
        role="pjmk",
        user_id=lecturer["user_id"],
        name=lecturer["full_name"],
    )
    assert pjmk["position"] == 1
    items = _listed(client, admin_headers, period_id)
    assert _by_id(items, pjmk["reference_id"])["position"] == 1
    assert _by_id(items, team["reference_id"])["position"] == 2

    occupied = client.post(
        PATH,
        headers=admin_headers,
        json={
            "curriculum_course_id": case["curriculum_course_id"],
            "academic_period_id": period_id,
            "instructor_name": "Anggota Bentrok",
            "instructor_role": "teaching_team",
            "position": 2,
        },
    )
    assert occupied.status_code == 409
    assert occupied.json()["error"]["code"] == "position_exists"


def test_pj_scope_applies_to_every_mutation_and_admin_can_cross_program(
    client, db_session, admin_headers, pj_headers, student_headers
):
    periods = _periods(client, db_session, count=2)
    own = _course(client, db_session, program_code="TSD")
    foreign = _course(client, db_session, program_code="TI")
    own_lecturer = _lecturer(client, db_session, program_code="TSD")
    foreign_lecturer = _lecturer(client, db_session, program_code="TI")
    foreign_ref = _create_reference(
        client,
        admin_headers,
        foreign,
        periods[0],
        role="pjmk",
        user_id=foreign_lecturer["user_id"],
        name=foreign_lecturer["full_name"],
    )

    create_foreign = client.post(
        PATH,
        headers=pj_headers,
        json={
            "curriculum_course_id": foreign["curriculum_course_id"],
            "academic_period_id": periods[0],
            "instructor_name": "PJ MK Asing",
            "instructor_role": "pjmk",
            "user_id": foreign_lecturer["user_id"],
        },
    )
    assert create_foreign.status_code == 403
    assert client.patch(
        f"{PATH}/{foreign_ref['reference_id']}",
        headers=pj_headers,
        json={"academic_period_id": periods[0], "instructor_name": "Nama Asing"},
    ).status_code == 403
    assert client.delete(
        f"{PATH}/{foreign_ref['reference_id']}",
        headers=pj_headers,
        params={"academic_period_id": periods[0]},
    ).status_code == 403
    assert client.put(
        ORDER_PATH,
        headers=pj_headers,
        json={
            "curriculum_course_id": foreign["curriculum_course_id"],
            "academic_period_id": periods[0],
            "ordered_reference_ids": [foreign_ref["reference_id"]],
        },
    ).status_code == 403
    own_ref = _create_reference(
        client,
        pj_headers,
        own,
        periods[0],
        role="pjmk",
        user_id=own_lecturer["user_id"],
        name=own_lecturer["full_name"],
    )
    assert own_ref["study_program_id"] == own["study_program_id"]

    copied = client.post(
        COPY_PATH,
        headers=pj_headers,
        json={
            "from_academic_period_id": periods[0],
            "academic_period_id": periods[1],
        },
    )
    assert copied.status_code == 200, copied.text
    assert copied.json()["meta"] == {"copied": 1, "skipped": 0, "total": 1}
    assert [item["reference_id"] for item in _listed(client, pj_headers, periods[0])] == [
        own_ref["reference_id"]
    ]
    assert [item["source_reference_id"] for item in copied.json()["data"]] == [
        own_ref["reference_id"]
    ]
    assert foreign_ref["reference_id"] in {
        item["reference_id"] for item in _listed(client, admin_headers, periods[0])
    }

    assert client.post(
        PATH,
        headers=student_headers,
        json={
            "curriculum_course_id": own["curriculum_course_id"],
            "academic_period_id": periods[0],
            "instructor_name": own_lecturer["full_name"],
            "instructor_role": "pjmk",
            "user_id": own_lecturer["user_id"],
        },
    ).status_code == 403
    assert client.patch(
        f"{PATH}/{own_ref['reference_id']}",
        headers=student_headers,
        json={"academic_period_id": periods[0], "instructor_name": "Nama Tidak Sah"},
    ).status_code == 403
    assert client.delete(
        f"{PATH}/{own_ref['reference_id']}",
        headers=student_headers,
        params={"academic_period_id": periods[0]},
    ).status_code == 403
    assert client.post(
        COPY_PATH,
        headers=student_headers,
        json={
            "from_academic_period_id": periods[0],
            "academic_period_id": periods[1],
        },
    ).status_code == 403
    assert client.put(
        ORDER_PATH,
        headers=student_headers,
        json={
            "curriculum_course_id": own["curriculum_course_id"],
            "academic_period_id": periods[0],
            "ordered_reference_ids": [own_ref["reference_id"]],
        },
    ).status_code == 403

    assert client.patch(
        f"{PATH}/{foreign_ref['reference_id']}",
        headers=admin_headers,
        json={"academic_period_id": periods[0], "instructor_name": "Diubah Admin"},
    ).status_code == 200


def test_mapping_mutations_are_audited_and_bump_period_revision(
    client, db_session, admin_headers
):
    periods = _periods(client, db_session, count=2)
    case = _course(client, db_session)
    lecturer = _lecturer(client, db_session)

    async def settings():
        for period_id in periods[:2]:
            db_session.add(
                SchedulePeriodSettings(
                    academic_period_id=uuid.UUID(period_id),
                    study_program_id=uuid.UUID(case["study_program_id"]),
                    input_revision=0,
                )
            )
        await db_session.commit()

    client.portal.call(settings)
    pjmk = _create_reference(
        client,
        admin_headers,
        case,
        periods[0],
        role="pjmk",
        user_id=lecturer["user_id"],
        name=lecturer["full_name"],
    )
    member = _create_reference(
        client, admin_headers, case, periods[0], name="Anggota Audit"
    )
    changed = client.patch(
        f"{PATH}/{member['reference_id']}",
        headers=admin_headers,
        json={
            "academic_period_id": periods[0],
            "instructor_name": "Anggota Audit Diubah",
            "position": 3,
        },
    )
    assert changed.status_code == 200, changed.text
    ordered = client.put(
        ORDER_PATH,
        headers=admin_headers,
        json={
            "curriculum_course_id": case["curriculum_course_id"],
            "academic_period_id": periods[0],
            "ordered_reference_ids": [pjmk["reference_id"], member["reference_id"]],
        },
    )
    assert ordered.status_code == 200, ordered.text
    copied = client.post(
        COPY_PATH,
        headers=admin_headers,
        json={
            "from_academic_period_id": periods[0],
            "academic_period_id": periods[1],
        },
    )
    assert copied.status_code == 200, copied.text
    assert client.delete(
        f"{PATH}/{member['reference_id']}",
        headers=admin_headers,
        params={"academic_period_id": periods[0]},
    ).status_code == 204

    actor_id = _actor_id(client, db_session)
    audit = client.portal.call(_mapping_audit, db_session, actor_id)
    actions = {row["action"] for row in audit}
    assert {
        "instructor_reference_create",
        "instructor_reference_update",
        "instructor_reference_order",
        "instructor_reference_copy",
        "instructor_reference_delete",
    } <= actions
    assert all(str(row["actor_user_id"]) == actor_id for row in audit)
    assert all(row["created_at"] is not None for row in audit)
    created = next(
        row
        for row in audit
        if row["action"] == "instructor_reference_create"
        and json.loads(row["new_value"])["reference_id"] == pjmk["reference_id"]
    )
    assert created["old_value"] is None
    assert json.loads(created["new_value"])["reference_id"] == pjmk["reference_id"]
    updated = next(
        row
        for row in audit
        if row["action"] == "instructor_reference_update"
        and json.loads(row["old_value"])["reference_id"] == member["reference_id"]
    )
    assert json.loads(updated["old_value"])["instructor_name"] == "Anggota Audit"
    assert json.loads(updated["new_value"])["instructor_name"] == "Anggota Audit Diubah"
    deleted = next(
        row
        for row in audit
        if row["action"] == "instructor_reference_delete"
        and json.loads(row["old_value"])["reference_id"] == member["reference_id"]
    )
    assert deleted["new_value"] is None
    copy_row = next(
        row
        for row in audit
        if row["action"] == "instructor_reference_copy"
        and json.loads(row["new_value"])["source_reference_id"]
        in {pjmk["reference_id"], member["reference_id"]}
    )
    order_row = next(
        row
        for row in audit
        if row["action"] == "instructor_reference_order"
        and json.loads(row["old_value"])["reference_id"]
        in {pjmk["reference_id"], member["reference_id"]}
        and json.loads(row["old_value"])["position"]
        != json.loads(row["new_value"])["position"]
    )

    async def revisions():
        rows = (
            await db_session.execute(
                select(SchedulePeriodSettings).where(
                    SchedulePeriodSettings.academic_period_id.in_(
                        [uuid.UUID(period_id) for period_id in periods[:2]]
                    )
                )
            )
        ).scalars().all()
        return {str(row.academic_period_id): row.input_revision for row in rows}

    revisions_by_period = client.portal.call(revisions)
    assert revisions_by_period[periods[0]] == 5
    assert revisions_by_period[periods[1]] == 1

    audit_count = len(audit)
    noop = client.patch(
        f"{PATH}/{pjmk['reference_id']}",
        headers=admin_headers,
        json={"academic_period_id": periods[0], "user_id": lecturer["user_id"]},
    )
    assert noop.status_code == 200, noop.text
    assert len(
        client.portal.call(_mapping_audit, db_session, actor_id)
    ) == audit_count
    assert client.portal.call(revisions) == revisions_by_period


def test_copy_rejects_period_pjmk_without_active_account(
    client, db_session, admin_headers
):
    periods = _periods(client, db_session, count=2)
    case = _course(client, db_session)

    async def invalid_source():
        db_session.add(
            CourseInstructorReference(
                curriculum_course_id=uuid.UUID(case["curriculum_course_id"]),
                academic_period_id=uuid.UUID(periods[0]),
                instructor_name="PJ MK Eksternal",
                instructor_role="pjmk",
            )
        )
        await db_session.commit()

    client.portal.call(invalid_source)
    response = client.post(
        COPY_PATH,
        headers=admin_headers,
        json={
            "from_academic_period_id": periods[0],
            "academic_period_id": periods[1],
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "pjmk_requires_account"
    assert _listed(client, admin_headers, periods[1]) == []


def test_mapping_period_options_are_available_to_admin_and_pj(
    client, db_session, admin_headers, pj_headers, student_headers
):
    periods = _periods(client, db_session, count=2)
    path = f"{PATH}/periods"
    admin = client.get(path, headers=admin_headers)
    pj = client.get(path, headers=pj_headers)
    assert admin.status_code == pj.status_code == 200
    assert admin.json() == pj.json()
    ids = {item["academic_period_id"] for item in admin.json()["data"]}
    assert set(periods) <= ids
    assert admin.json()["meta"]["total"] == len(admin.json()["data"])
    assert client.get(path, headers=student_headers).status_code == 403


def test_position_migration_is_reversible_schema_only(monkeypatch):
    migration = import_module(
        "migrations.versions.a6f3c4d5e72_add_instructor_reference_position"
    )
    statements: list[str] = []

    def execute(statement):
        statements.append(str(statement))

    monkeypatch.setattr(migration.op, "execute", execute)
    migration.upgrade()
    migration.downgrade()
    assert migration.revision == "a6f3c4d5e72"
    assert migration.down_revision == "9d5e2f3a4b61"
    assert any("ADD COLUMN IF NOT EXISTS position" in item for item in statements)
    assert any("DROP COLUMN IF EXISTS position" in item for item in statements)
    assert all(
        statement.lstrip().upper().startswith(("ALTER ", "CREATE ", "DROP ", "DO "))
        for statement in statements
    )
    assert CourseInstructorReference.__table__.c.position.nullable is True
    assert CourseInstructorReference.__table__.c.source_reference_id.nullable is True


def test_ordinary_lecturer_cannot_mutate_period_instructor_references(client):
    login = client.post(
        f"{V1}/auth/login",
        json={
            "identifier": "aisyahdm@ftmm.unair.ac.id",
            "password": "DosenFTMM2026!",
        },
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    period_id = uuid.uuid4()
    curriculum_course_id = uuid.uuid4()
    reference_id = uuid.uuid4()
    assert (
        client.post(
            PATH,
            headers=headers,
            json={
                "curriculum_course_id": str(curriculum_course_id),
                "academic_period_id": str(period_id),
                "instructor_name": "Dosen Tidak Sah",
                "instructor_role": "teaching_team",
            },
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"{PATH}/{reference_id}",
            headers=headers,
            json={
                "academic_period_id": str(period_id),
                "instructor_name": "Nama Tidak Sah",
            },
        ).status_code
        == 403
    )
    assert client.delete(
        f"{PATH}/{reference_id}",
        headers=headers,
        params={"academic_period_id": str(period_id)},
    ).status_code == 403
    assert (
        client.post(
            COPY_PATH,
            headers=headers,
            json={
                "from_academic_period_id": str(period_id),
                "academic_period_id": str(uuid.uuid4()),
            },
        ).status_code
        == 403
    )
    assert (
        client.put(
            ORDER_PATH,
            headers=headers,
            json={
                "curriculum_course_id": str(curriculum_course_id),
                "academic_period_id": str(period_id),
                "ordered_reference_ids": [str(reference_id)],
            },
        ).status_code
        == 403
    )


def test_assignment_curriculum_migration_is_reversible_and_preserves_rows(
    monkeypatch,
):
    migration = import_module(
        "migrations.versions.c9d0e1f2a3b4_add_assignment_curriculum_context"
    )
    statements: list[str] = []

    def execute(statement):
        statements.append(str(statement))

    monkeypatch.setattr(migration.op, "execute", execute)
    migration.upgrade()
    migration.downgrade()
    assert migration.revision == "c9d0e1f2a3b4"
    assert migration.down_revision == "b8c9d0e1f2a3"
    assert any(
        "ADD COLUMN IF NOT EXISTS curriculum_course_id UUID NULL" in item
        for item in statements
    )
    assert any(
        "REFERENCES curriculum_courses(curriculum_course_id)" in item
        for item in statements
    )
    assert any("DROP COLUMN IF EXISTS curriculum_course_id" in item for item in statements)
    assert not any(
        item.lstrip().upper().startswith(("UPDATE ", "DELETE ", "TRUNCATE "))
        for item in statements
    )
    column = ClassInstructorAssignment.__table__.c.curriculum_course_id
    assert column.nullable is True
    assert column.foreign_keys
