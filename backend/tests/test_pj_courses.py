"""Kontrak HTTP untuk rekap dan toggle ketersediaan MK PJ prodi."""

import uuid

from sqlalchemy import select

from auth import create_access_token
from catalog import authoritative_curriculum_id
from models import (
    Course,
    Curriculum,
    CurriculumCourse,
    ElectivePollingPeriod,
    LecturerProfile,
    StudyProgram,
    User,
)

V1 = "/api/v1"
LEGACY = "/api"
PJ_EMAIL = "dwi.rantini@ftmm.unair.ac.id"
ITEM_KEYS = {
    "curriculum_course_id",
    "course_id",
    "course_code",
    "course_name",
    "credits",
    "semester",
    "type",
    "course_scope",
    "is_active",
    "can_toggle",
    "lock_reason",
    "class_count",
    "capacity_per_class",
    "total_quota",
    "enrolled_count",
}


def _assert_error(response, status_code, code):
    assert response.status_code == status_code, response.text
    assert response.json()["error"]["code"] == code, response.json()


def _active_period(client, db_session):
    async def query():
        period = (
            await db_session.execute(
                select(ElectivePollingPeriod)
                .where(ElectivePollingPeriod.status == "open")
                .order_by(ElectivePollingPeriod.created_at.desc())
            )
        ).scalars().first()
        assert period is not None
        return str(period.polling_period_id), int(period.target_semester)

    return client.portal.call(query)


def _course_id(client, db_session):
    async def query():
        course = (
            await db_session.execute(select(Course).order_by(Course.course_code))
        ).scalars().first()
        assert course is not None
        return str(course.course_id)

    return client.portal.call(query)


def _pj_user_id(client, db_session):
    async def query():
        user = (
            await db_session.execute(select(User).where(User.email == PJ_EMAIL))
        ).scalars().first()
        assert user is not None
        return str(user.user_id)

    return client.portal.call(query)


def _term_for(semester: int) -> str:
    return "ganjil" if semester % 2 else "genap"


async def _create_course(db_session):
    code = f"UJI{int(uuid.uuid4().hex[:4], 16) % 10000:04d}"
    course = Course(course_code=code, course_name=f"MK Uji {code}", is_active=True)
    db_session.add(course)
    await db_session.flush()
    return course


def _prepare_own_course(
    client,
    db_session,
    *,
    target,
    semester=None,
    course_type="Pilihan",
    is_active=True,
    course_scope="program_studi",
):
    async def prepare():
        curriculum_id = await authoritative_curriculum_id(
            db_session, "Teknologi Sains Data"
        )
        assert curriculum_id is not None
        course = await _create_course(db_session)

        chosen_semester = semester if semester is not None else target
        curriculum_course = CurriculumCourse(
            curriculum_id=curriculum_id,
            course_id=course.course_id,
            credits_total=3,
            recommended_semester=chosen_semester,
            term=_term_for(chosen_semester),
            course_type="wajib" if course_type == "Wajib" else "pilihan",
            course_scope=course_scope,
            is_active=is_active,
        )
        db_session.add(curriculum_course)
        await db_session.flush()
        return str(curriculum_course.curriculum_course_id)

    return client.portal.call(prepare)


def _create_scoped_course(client, db_session, *, scope, program_code="TRKB"):
    """Buat MK di prodi lain dengan scope tertentu untuk uji batas PJ."""

    async def create():
        program = (
            await db_session.execute(
                select(StudyProgram).where(StudyProgram.program_code == program_code)
            )
        ).scalars().first()
        assert program is not None
        curriculum = (
            await db_session.execute(
                select(Curriculum)
                .where(Curriculum.study_program_id == program.study_program_id)
                .order_by(Curriculum.curriculum_year.desc())
            )
        ).scalars().first()
        if curriculum is None:
            curriculum = Curriculum(
                study_program_id=program.study_program_id,
                curriculum_name=f"Kurikulum uji {program_code}",
                curriculum_year=2030,
                minimum_graduation_credits=144,
                standard_duration_semesters=8,
                is_active=True,
            )
            db_session.add(curriculum)
            await db_session.flush()

        course = await _create_course(db_session)
        curriculum_course = CurriculumCourse(
            curriculum_id=curriculum.curriculum_id,
            course_id=course.course_id,
            credits_total=3,
            recommended_semester=4,
            term="genap",
            course_type="pilihan",
            course_scope=scope,
            is_active=True,
        )
        db_session.add(curriculum_course)
        await db_session.flush()
        return str(curriculum_course.curriculum_course_id), str(course.course_id)

    return client.portal.call(create)


def _create_lecturer(client, db_session, *, coordinator=False):
    async def insert():
        program = (
            await db_session.execute(
                select(StudyProgram).where(StudyProgram.program_code == "TSD")
            )
        ).scalars().first()
        user = User(
            email=f"dosen.{uuid.uuid4().hex[:10]}@ftmm.unair.ac.id",
            full_name="Dosen Uji",
            role="lecturer",
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()
        db_session.add(
            LecturerProfile(
                user_id=user.user_id,
                study_program_id=program.study_program_id,
                is_program_coordinator=coordinator,
            )
        )
        await db_session.flush()
        return user.user_id

    user_id = client.portal.call(insert)
    token = create_access_token(
        data={"sub": str(user_id), "role": "lecturer", "ver": 0}
    )
    return {"Authorization": f"Bearer {token}"}


def _set_active_target(client, db_session, target):
    async def update():
        period = (
            await db_session.execute(
                select(ElectivePollingPeriod).where(
                    ElectivePollingPeriod.status == "open"
                )
            )
        ).scalars().first()
        period.target_semester = target
        await db_session.flush()

    client.portal.call(update)


def _is_active(client, db_session, curriculum_course_id):
    async def query():
        course = (
            await db_session.execute(
                select(CurriculumCourse).where(
                    CurriculumCourse.curriculum_course_id == uuid.UUID(curriculum_course_id)
                )
            )
        ).scalars().one()
        return bool(course.is_active)

    return client.portal.call(query)


def _own_course_ids(client, db_session, curriculum_course_ids):
    async def query():
        curriculum_id = await authoritative_curriculum_id(
            db_session, "Teknologi Sains Data"
        )
        result = await db_session.execute(
            select(CurriculumCourse.curriculum_course_id).where(
                CurriculumCourse.curriculum_course_id.in_(curriculum_course_ids),
                CurriculumCourse.curriculum_id == curriculum_id,
            )
        )
        return {str(row[0]) for row in result}

    return client.portal.call(query)


def test_pj_sees_only_own_and_shared_courses(client, db_session, pj_headers):
    _, target = _active_period(client, db_session)
    own_id = _prepare_own_course(client, db_session, target=target)
    foreign_id, _ = _create_scoped_course(client, db_session, scope="program_studi")
    shared_id, shared_course_id = _create_scoped_course(
        client, db_session, scope="fakultas"
    )

    response = client.get(f"{V1}/pj/course-availability", headers=pj_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"data", "meta"}
    assert body["meta"]["study_program"] == "Teknologi Sains Data"
    assert body["meta"]["target_semester"] == target
    assert body["meta"]["total"] == len(body["data"])

    items = body["data"]
    assert own_id in {item["curriculum_course_id"] for item in items}
    assert shared_id in {item["curriculum_course_id"] for item in items}
    assert foreign_id not in {item["curriculum_course_id"] for item in items}
    assert any(item["course_id"] == shared_course_id for item in items)
    assert all(set(item) == ITEM_KEYS for item in items)
    own_ids = _own_course_ids(
        client,
        db_session,
        [uuid.UUID(item["curriculum_course_id"]) for item in items],
    )

    for item in items:
        semester = item["semester"]
        is_foreign = item["curriculum_course_id"] not in own_ids
        assert item["can_toggle"] == (
            not is_foreign
            and item["type"] == "Pilihan"
            and (semester is None or semester >= target)
        )
        if is_foreign:
            expected_reason = "prodi_lain"
        elif semester is not None and semester < target:
            expected_reason = "semester_berjalan"
        elif item["type"] != "Pilihan":
            expected_reason = "bukan_pilihan"
        elif not item["is_active"]:
            expected_reason = "dinonaktifkan"
        else:
            expected_reason = None
        assert item["lock_reason"] == expected_reason, item


def test_get_supports_explicit_period_and_semester(client, db_session, pj_headers):
    period_id, target = _active_period(client, db_session)
    course_id = _course_id(client, db_session)
    course_cc_id = _prepare_own_course(client, db_session, target=target)

    missing = client.get(
        f"{V1}/pj/course-availability",
        headers=pj_headers,
        params={"period_id": course_id},
    )
    _assert_error(missing, 404, "polling_period_not_found")

    override = min(8, target + 1)
    explicit = client.get(
        f"{V1}/pj/course-availability",
        headers=pj_headers,
        params={"period_id": period_id, "semester": override},
    )
    assert explicit.status_code == 200, explicit.text
    assert explicit.json()["meta"]["period_id"] == period_id
    assert explicit.json()["meta"]["target_semester"] == override

    if override > target:
        item = next(
            row
            for row in explicit.json()["data"]
            if row["curriculum_course_id"] == course_cc_id
        )
        assert item["lock_reason"] == "semester_berjalan"
        assert item["can_toggle"] is False


def test_toggle_updates_curriculum_and_writes_audit(
    client, db_session, pj_headers, admin_headers
):
    _, target = _active_period(client, db_session)
    cc_id = _prepare_own_course(client, db_session, target=target)
    pj_id = _pj_user_id(client, db_session)

    changed = client.patch(
        f"{V1}/pj/course-availability/{cc_id}",
        headers=pj_headers,
        json={"is_active": False, "reason": "Kuota kelas tidak tersedia"},
    )
    assert changed.status_code == 200, changed.text
    item = changed.json()
    assert set(item) == ITEM_KEYS
    assert item["curriculum_course_id"] == cc_id
    assert item["is_active"] is False
    assert item["can_toggle"] is True
    assert item["lock_reason"] == "dinonaktifkan"
    assert _is_active(client, db_session, cc_id) is False

    listed = client.get(f"{V1}/pj/course-availability", headers=pj_headers).json()
    persisted = next(
        row for row in listed["data"] if row["curriculum_course_id"] == cc_id
    )
    assert persisted["is_active"] is False

    traces = client.get(
        f"{V1}/admin/authority-traces",
        headers=admin_headers,
        params={"page": 1, "page_size": 100},
    )
    assert traces.status_code == 200, traces.text
    entry = next(
        (
            row
            for row in traces.json()["data"]
            if row["action"] == "course_availability_change"
            and row["field_name"] == f"curriculum_course:{cc_id}"
            and row["new_value"] == "false"
        ),
        None,
    )
    assert entry is not None, traces.json()
    assert entry["actor_user_id"] == pj_id
    assert entry["target_user_id"] == pj_id
    assert entry["old_value"] == "true"
    assert entry["reason"] == "Kuota kelas tidak tersedia"

    restored = client.patch(
        f"{V1}/pj/course-availability/{cc_id}",
        headers=pj_headers,
        json={"is_active": True},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["is_active"] is True
    assert restored.json()["lock_reason"] is None
    assert _is_active(client, db_session, cc_id) is True

    traces = client.get(
        f"{V1}/admin/authority-traces",
        headers=admin_headers,
        params={"page": 1, "page_size": 100},
    ).json()
    assert any(
        row["action"] == "course_availability_change"
        and row["field_name"] == f"curriculum_course:{cc_id}"
        and row["old_value"] == "false"
        and row["new_value"] == "true"
        and row["reason"] == ""
        for row in traces["data"]
    )


def test_cross_prodi_patch_is_denied(client, db_session, pj_headers):
    foreign_id, _ = _create_scoped_course(client, db_session, scope="program_studi")
    response = client.patch(
        f"{V1}/pj/course-availability/{foreign_id}",
        headers=pj_headers,
        json={"is_active": False},
    )
    _assert_error(response, 403, "prodi_mismatch")


def test_cross_prodi_shared_scope_patch_is_denied(client, db_session, pj_headers):
    for scope in ("fakultas", "universitas"):
        foreign_id, _ = _create_scoped_course(client, db_session, scope=scope)
        response = client.patch(
            f"{V1}/pj/course-availability/{foreign_id}",
            headers=pj_headers,
            json={"is_active": False},
        )
        _assert_error(response, 403, "prodi_mismatch")
        assert _is_active(client, db_session, foreign_id) is True


def test_foreign_shared_scope_course_is_locked(client, db_session, pj_headers):
    for scope in ("fakultas", "universitas"):
        foreign_id, _ = _create_scoped_course(client, db_session, scope=scope)
        listed = client.get(f"{V1}/pj/course-availability", headers=pj_headers)
        assert listed.status_code == 200, listed.text
        item = next(
            row
            for row in listed.json()["data"]
            if row["curriculum_course_id"] == foreign_id
        )
        assert item["course_scope"] == scope
        assert item["can_toggle"] is False
        assert isinstance(item["lock_reason"], str) and item["lock_reason"]
        assert item["lock_reason"] == "prodi_lain"


def test_own_shared_scope_course_can_be_toggled(
    client, db_session, pj_headers, admin_headers
):
    _, target = _active_period(client, db_session)
    for scope in ("fakultas", "universitas"):
        cc_id = _prepare_own_course(
            client, db_session, target=target, course_scope=scope
        )
        listed = client.get(f"{V1}/pj/course-availability", headers=pj_headers)
        item = next(
            row
            for row in listed.json()["data"]
            if row["curriculum_course_id"] == cc_id
        )
        assert item["course_scope"] == scope
        assert item["can_toggle"] is True
        assert item["lock_reason"] is None

        changed = client.patch(
            f"{V1}/pj/course-availability/{cc_id}",
            headers=pj_headers,
            json={"is_active": False, "reason": f"Alasan {scope}"},
        )
        assert changed.status_code == 200, changed.text
        assert changed.json()["is_active"] is False
        assert changed.json()["lock_reason"] == "dinonaktifkan"
        assert _is_active(client, db_session, cc_id) is False

        traces = client.get(
            f"{V1}/admin/authority-traces",
            headers=admin_headers,
            params={"page": 1, "page_size": 100},
        )
        assert traces.status_code == 200, traces.text
        assert any(
            row["action"] == "course_availability_change"
            and row["field_name"] == f"curriculum_course:{cc_id}"
            and row["old_value"] == "true"
            and row["new_value"] == "false"
            and row["reason"] == f"Alasan {scope}"
            for row in traces.json()["data"]
        ), traces.json()


def test_running_semester_patch_is_denied(client, db_session, pj_headers):
    target = max(2, _active_period(client, db_session)[1])
    _set_active_target(client, db_session, target)
    cc_id = _prepare_own_course(
        client, db_session, target=target, semester=target - 1
    )
    response = client.patch(
        f"{V1}/pj/course-availability/{cc_id}",
        headers=pj_headers,
        json={"is_active": False},
    )
    _assert_error(response, 409, "semester_not_eligible")


def test_wajib_patch_is_denied(client, db_session, pj_headers):
    _, target = _active_period(client, db_session)
    cc_id = _prepare_own_course(client, db_session, target=target, course_type="Wajib")
    response = client.patch(
        f"{V1}/pj/course-availability/{cc_id}",
        headers=pj_headers,
        json={"is_active": False},
    )
    _assert_error(response, 422, "not_elective")


def test_unknown_and_invalid_payload_are_denied(client, db_session, pj_headers):
    _, target = _active_period(client, db_session)
    cc_id = _prepare_own_course(client, db_session, target=target)
    unknown_id = _course_id(client, db_session)

    unknown = client.patch(
        f"{V1}/pj/course-availability/{unknown_id}",
        headers=pj_headers,
        json={"is_active": False},
    )
    _assert_error(unknown, 404, "not_found")

    for payload in ({"is_active": "tidak"}, {}, {"is_active": True, "extra": 1}):
        invalid = client.patch(
            f"{V1}/pj/course-availability/{cc_id}",
            headers=pj_headers,
            json=payload,
        )
        _assert_error(invalid, 422, "validation_error")


def test_non_pj_callers_are_denied(
    client, db_session, pj_headers, student_headers, admin_headers
):
    _, target = _active_period(client, db_session)
    cc_id = _prepare_own_course(client, db_session, target=target)
    lecturer_headers = _create_lecturer(client, db_session, coordinator=False)

    for headers, code in (
        (student_headers, "forbidden"),
        (lecturer_headers, "not_program_coordinator"),
        (admin_headers, "forbidden"),
    ):
        listed = client.get(f"{V1}/pj/course-availability", headers=headers)
        _assert_error(listed, 403, code)
        changed = client.patch(
            f"{V1}/pj/course-availability/{cc_id}",
            headers=headers,
            json={"is_active": False},
        )
        _assert_error(changed, 403, code)

    unauthenticated = client.get(f"{V1}/pj/course-availability")
    _assert_error(unauthenticated, 401, "unauthorized")

    allowed = client.get(f"{LEGACY}/pj/course-availability", headers=pj_headers)
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["meta"]["period_id"] == _active_period(client, db_session)[0]


def test_legacy_patch_tier_is_mounted(client, db_session, pj_headers):
    _, target = _active_period(client, db_session)
    cc_id = _prepare_own_course(client, db_session, target=target)
    response = client.patch(
        f"{LEGACY}/pj/course-availability/{cc_id}",
        headers=pj_headers,
        json={"is_active": False},
    )
    assert response.status_code == 200, response.text
    assert response.json()["curriculum_course_id"] == cc_id
    assert response.json()["is_active"] is False
