"""HTTP contract for period-scoped lecturer schedule preferences."""

import uuid
from datetime import time
from typing import Any

from pytest import mark
from sqlalchemy import delete, select, update

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
    LecturerSchedulePreference,
    OfferingComponent,
    StudyProgram,
    User,
)
from rate_limit import limiter
from tests.conftest import SEEDED_LECTURER, SEEDED_STUDENT

V1 = "/api/v1"
LEGACY = "/api"
PREFERENCES = f"{V1}/scheduling/preferences/me"
PERIODS = f"{V1}/scheduling/preferences/periods"
COPY = f"{V1}/scheduling/preferences/me/copy"
PASSWORD = "PreferenceUji2026!"
SLOT = {
    "day_of_week": 1,
    "start_time": "08:00:00",
    "end_time": "10:00:00",
    "kind": "preferred",
}


def _login_headers(client, email: str, password: str = PASSWORD) -> dict[str, str]:
    limiter.reset()
    response = client.post(
        f"{V1}/auth/login",
        json={"identifier": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _periods(client, db_session) -> dict[str, uuid.UUID]:
    async def setup():
        active = (
            await db_session.execute(
                select(AcademicPeriod)
                .where(AcademicPeriod.is_active.is_(True))
                .order_by(
                    AcademicPeriod.academic_year_start.desc(),
                    AcademicPeriod.created_at.desc(),
                    AcademicPeriod.academic_period_id,
                )
                .limit(1)
            )
        ).scalars().one()
        used_years = set(
            (await db_session.execute(select(AcademicPeriod.academic_year_start)))
            .scalars()
            .all()
        )
        used_ids = set(
            (await db_session.execute(select(AcademicPeriod.academic_period_id)))
            .scalars()
            .all()
        )

        def unused_period_id(year: int, term: str) -> uuid.UUID:
            seed = f"ftmm-compass:preference-period:{year}:{term}"
            candidate = uuid.uuid5(uuid.NAMESPACE_URL, seed)
            suffix = 1
            while candidate in used_ids:
                candidate = uuid.uuid5(uuid.NAMESPACE_URL, f"{seed}:{suffix}")
                suffix += 1
            used_ids.add(candidate)
            return candidate

        previous_year = active.academic_year_start - 1
        while previous_year in used_years:
            previous_year -= 1
        following_year = active.academic_year_start + 1
        while following_year in used_years:
            following_year += 1
        previous = AcademicPeriod(
            academic_period_id=unused_period_id(previous_year, "genap"),
            academic_year_start=previous_year,
            semester_number=2,
            term="genap",
            is_active=False,
        )
        following = AcademicPeriod(
            academic_period_id=unused_period_id(following_year, "ganjil"),
            academic_year_start=following_year,
            semester_number=1,
            term="ganjil",
            is_active=False,
        )
        db_session.add_all([previous, following])
        await db_session.commit()
        return {
            "active": active.academic_period_id,
            "previous": previous.academic_period_id,
            "following": following.academic_period_id,
        }

    return client.portal.call(setup)


def _user_id(client, db_session, email: str) -> uuid.UUID:
    async def read():
        return (
            await db_session.execute(select(User.user_id).where(User.email == email))
        ).scalar_one()

    return client.portal.call(read)


def _clear_lecturer_preferences(client, db_session) -> None:
    async def clear():
        user_id = (
            await db_session.execute(
                select(User.user_id).where(User.email == SEEDED_LECTURER[0])
            )
        ).scalar_one()
        await db_session.execute(
            delete(LecturerSchedulePreference).where(
                LecturerSchedulePreference.user_id == user_id
            )
        )
        await db_session.commit()

    client.portal.call(clear)


def _slot(**overrides: Any) -> dict[str, Any]:
    value = dict(SLOT)
    value.update(overrides)
    return value


def _copy_payload(
    source: uuid.UUID, target: uuid.UUID, *, overwrite: bool = False
) -> dict[str, Any]:
    return {
        "from_academic_period_id": str(source),
        "academic_period_id": str(target),
        "overwrite": overwrite,
    }


def _assert_empty_meta(body: dict[str, Any]) -> None:
    assert body["meta"]["count"] == 0
    assert body["meta"]["status"] == "empty"
    assert body["meta"]["preferred_count"] == 0
    assert body["meta"]["unavailable_count"] == 0
    assert body["meta"]["completeness"] == {
        "filled": False,
        "preferred_count": 0,
        "unavailable_count": 0,
    }
    assert body["meta"]["deadline"] is None
    assert body["meta"]["warnings"] == []


def _assert_valid_overlap_warning(warning: dict[str, Any]) -> None:
    assert warning["code"] == "assigned_class_overlap"
    uuid.UUID(warning["class_section_id"])
    assert warning["course_code"]
    assert warning["course_name"]
    assert warning["section_code"]
    assert 1 <= warning["day_of_week"] <= 5
    assert warning["day_name"]
    unavailable_start = time.fromisoformat(warning["unavailable_start_time"])
    unavailable_end = time.fromisoformat(warning["unavailable_end_time"])
    class_start = time.fromisoformat(warning["class_start_time"])
    class_end = time.fromisoformat(warning["class_end_time"])
    overlap_start = time.fromisoformat(warning["overlap_start_time"])
    overlap_end = time.fromisoformat(warning["overlap_end_time"])
    assert unavailable_start < unavailable_end
    assert class_start < class_end
    assert unavailable_start <= overlap_start < overlap_end <= unavailable_end
    assert class_start <= overlap_start < overlap_end <= class_end


def test_preferences_require_authentication(client):
    assert client.get(PREFERENCES).status_code == 401
    assert client.put(PREFERENCES, json=[SLOT]).status_code == 401
    assert client.get(PERIODS).status_code == 401
    assert client.post(
        COPY,
        json={
            "from_academic_period_id": str(uuid.uuid4()),
            "academic_period_id": str(uuid.uuid4()),
        },
    ).status_code == 401


def test_empty_filled_edit_and_clear_states(client, db_session, lecturer_headers):
    periods = _periods(client, db_session)
    lecturer_id = _user_id(client, db_session, SEEDED_LECTURER[0])
    _clear_lecturer_preferences(client, db_session)

    empty = client.get(
        PREFERENCES,
        params={"academic_period_id": str(periods["active"])},
        headers=lecturer_headers,
    )
    assert empty.status_code == 200, empty.text
    assert empty.json()["academic_period_id"] == str(periods["active"])
    assert empty.json()["user_id"] == str(lecturer_id)
    assert empty.json()["data"] == []
    _assert_empty_meta(empty.json())

    slots = [
        _slot(kind="unavailable", start_time="13:00:00", end_time="15:00:00"),
        _slot(),
    ]
    filled = client.put(
        PREFERENCES,
        json={
            "academic_period_id": str(periods["active"]),
            "slots": slots,
        },
        headers=lecturer_headers,
    )
    assert filled.status_code == 200, filled.text
    body = filled.json()
    assert [item["start_time"] for item in body["data"]] == ["08:00:00", "13:00:00"]
    assert body["meta"]["count"] == 2
    assert body["meta"]["status"] == "filled"
    assert body["meta"]["preferred_count"] == 1
    assert body["meta"]["unavailable_count"] == 1
    assert body["meta"]["completeness"] == {
        "filled": True,
        "preferred_count": 1,
        "unavailable_count": 1,
    }
    assert body["meta"]["deadline"] is None
    assert isinstance(body["meta"]["warnings"], list)
    assert client.get(
        PREFERENCES,
        params={"academic_period_id": str(periods["active"])},
        headers=lecturer_headers,
    ).json() == body

    edited = client.put(
        PREFERENCES,
        params={"academic_period_id": str(periods["active"])},
        json=[_slot(day_of_week=3, start_time="09:00:00", end_time="11:00:00")],
        headers=lecturer_headers,
    )
    assert edited.status_code == 200, edited.text
    assert len(edited.json()["data"]) == 1
    assert edited.json()["data"][0]["day_of_week"] == 3
    assert edited.json()["meta"]["preferred_count"] == 1
    assert edited.json()["meta"]["unavailable_count"] == 0

    cleared = client.put(
        PREFERENCES,
        params={"academic_period_id": str(periods["active"])},
        json=[],
        headers=lecturer_headers,
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"] == []
    _assert_empty_meta(cleared.json())


def test_invalid_ranges_and_overlaps_do_not_replace_preferences(
    client, db_session, lecturer_headers
):
    periods = _periods(client, db_session)
    params = {"academic_period_id": str(periods["active"])}
    saved = client.put(
        PREFERENCES, params=params, json=[SLOT], headers=lecturer_headers
    )
    assert saved.status_code == 200, saved.text

    invalid_slots = [
        _slot(day_of_week=0),
        _slot(day_of_week=6),
        _slot(start_time="06:00:00"),
        _slot(end_time="18:00:00"),
        _slot(start_time="08:30:00", end_time="10:30:00"),
        _slot(start_time="10:00:00", end_time="10:00:00"),
        _slot(start_time="11:00:00", end_time="10:00:00"),
        _slot(start_time="08:00:00+00:00", end_time="10:00:00+00:00"),
        _slot(kind="blocked"),
        {**SLOT, "user_id": str(uuid.uuid4())},
    ]
    for invalid in invalid_slots:
        response = client.put(
            PREFERENCES, params=params, json=[invalid], headers=lecturer_headers
        )
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "validation_error"

    foreign_identity = client.put(
        PREFERENCES,
        params=params,
        json={"slots": [SLOT], "user_id": str(uuid.uuid4())},
        headers=lecturer_headers,
    )
    assert foreign_identity.status_code == 422
    assert foreign_identity.json()["error"]["code"] == "validation_error"

    mismatch = client.put(
        PREFERENCES,
        params={"academic_period_id": str(periods["active"])},
        json={
            "academic_period_id": str(periods["following"]),
            "slots": [SLOT],
        },
        headers=lecturer_headers,
    )
    assert mismatch.status_code == 422, mismatch.text
    assert mismatch.json()["error"]["code"] == "period_mismatch"
    assert client.get(
        PREFERENCES,
        params={"academic_period_id": str(periods["active"])},
        headers=lecturer_headers,
    ).json() == saved.json()

    overlaps = [
        [SLOT, _slot(kind="preferred", start_time="09:00:00", end_time="11:00:00")],
        [SLOT, _slot(kind="unavailable", start_time="09:00:00", end_time="11:00:00")],
    ]
    for slots in overlaps:
        response = client.put(
            PREFERENCES, params=params, json=slots, headers=lecturer_headers
        )
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "overlapping_preference"
        assert response.json()["error"]["details"][0]["day_of_week"] == 1

    assert client.get(PREFERENCES, params=params, headers=lecturer_headers).json() == saved.json()

    adjacent = client.put(
        PREFERENCES,
        params=params,
        json=[SLOT, _slot(kind="unavailable", start_time="10:00:00", end_time="12:00:00")],
        headers=lecturer_headers,
    )
    assert adjacent.status_code == 200, adjacent.text
    assert adjacent.json()["meta"]["count"] == 2


def test_period_selector_is_authenticated_deterministic_and_marks_current(
    client, db_session, lecturer_headers, student_headers
):
    periods = _periods(client, db_session)
    canonical = client.get(PERIODS, headers=lecturer_headers)
    legacy = client.get(f"{LEGACY}/scheduling/preferences/periods", headers=lecturer_headers)
    assert canonical.status_code == legacy.status_code == 200
    assert canonical.json() == legacy.json()
    body = canonical.json()
    assert body["meta"]["total"] == len(body["data"])
    assert body["meta"]["current_academic_period_id"] == str(periods["active"])
    assert body["data"][0]["academic_period_id"] == str(periods["active"])
    assert body["data"][0]["is_active"] is True
    assert body["data"][0]["is_current"] is True
    assert body["data"][0]["label"]
    period_ids = [item["academic_period_id"] for item in body["data"]]
    assert period_ids.index(str(periods["following"])) < period_ids.index(
        str(periods["previous"])
    )
    assert all(item["is_current"] is False for item in body["data"][1:])
    assert client.get(PERIODS, headers=lecturer_headers).json() == body
    assert client.get(PERIODS, headers=student_headers).status_code == 200


def test_preference_edits_are_isolated_by_period(client, db_session, lecturer_headers):
    periods = _periods(client, db_session)
    active_slot = _slot()
    following_slot = _slot(
        day_of_week=4,
        kind="unavailable",
        start_time="10:00:00",
        end_time="12:00:00",
    )
    active = client.put(
        PREFERENCES,
        params={"academic_period_id": str(periods["active"])},
        json=[active_slot],
        headers=lecturer_headers,
    )
    following = client.put(
        PREFERENCES,
        params={"academic_period_id": str(periods["following"])},
        json=[following_slot],
        headers=lecturer_headers,
    )
    assert active.status_code == following.status_code == 200
    assert active.json()["data"][0]["kind"] == "preferred"
    assert following.json()["data"][0]["kind"] == "unavailable"

    cleared = client.put(
        PREFERENCES,
        params={"academic_period_id": str(periods["active"])},
        json=[],
        headers=lecturer_headers,
    )
    assert cleared.status_code == 200, cleared.text
    _assert_empty_meta(cleared.json())
    remaining = client.get(
        PREFERENCES,
        params={"academic_period_id": str(periods["following"])},
        headers=lecturer_headers,
    )
    assert remaining.status_code == 200, remaining.text
    assert remaining.json() == following.json()


def test_copy_previous_period_is_idempotent_and_self_scoped(
    client, db_session, lecturer_headers
):
    periods = _periods(client, db_session)
    _clear_lecturer_preferences(client, db_session)
    lecturer_id = _user_id(client, db_session, SEEDED_LECTURER[0])
    other_id = _user_id(client, db_session, SEEDED_STUDENT[0])
    source_slots = [
        SLOT,
        _slot(day_of_week=2, kind="unavailable", start_time="14:00:00", end_time="16:00:00"),
    ]

    async def seed_other_user():
        db_session.add(
            LecturerSchedulePreference(
                user_id=other_id,
                academic_period_id=periods["previous"],
                day_of_week=4,
                start_time=time(9),
                end_time=time(11),
                kind="preferred",
            )
        )
        await db_session.commit()

    client.portal.call(seed_other_user)
    source = client.put(
        PREFERENCES,
        params={"academic_period_id": str(periods["previous"])},
        json=source_slots,
        headers=lecturer_headers,
    )
    assert source.status_code == 200, source.text

    payload = _copy_payload(periods["previous"], periods["active"])
    copied = client.post(COPY, json=payload, headers=lecturer_headers)
    assert copied.status_code == 200, copied.text
    assert copied.json()["academic_period_id"] == str(periods["active"])
    assert copied.json()["user_id"] == str(lecturer_id)
    assert copied.json()["data"] == source.json()["data"]
    assert copied.json()["meta"]["status"] == "filled"

    repeated = client.post(COPY, json=payload, headers=lecturer_headers)
    assert repeated.status_code == 200, repeated.text
    assert repeated.json() == copied.json()

    async def assert_rows():
        own = list(
            (
                await db_session.execute(
                    select(LecturerSchedulePreference).where(
                        LecturerSchedulePreference.user_id == lecturer_id,
                        LecturerSchedulePreference.academic_period_id
                        == periods["active"],
                    )
                )
            ).scalars().all()
        )
        other = (
            await db_session.execute(
                select(LecturerSchedulePreference).where(
                    LecturerSchedulePreference.user_id == other_id,
                    LecturerSchedulePreference.academic_period_id
                    == periods["previous"],
                )
            )
        ).scalar_one()
        assert len(own) == 2
        assert other.day_of_week == 4

    client.portal.call(assert_rows)


def test_copy_protects_nonempty_target_and_allows_explicit_overwrite(
    client, db_session, lecturer_headers
):
    periods = _periods(client, db_session)
    source_slots = [SLOT]
    target_slots = [
        _slot(day_of_week=5, kind="unavailable", start_time="15:00:00", end_time="17:00:00")
    ]
    assert client.put(
        PREFERENCES,
        params={"academic_period_id": str(periods["previous"])},
        json=source_slots,
        headers=lecturer_headers,
    ).status_code == 200
    target = client.put(
        PREFERENCES,
        params={"academic_period_id": str(periods["active"])},
        json=target_slots,
        headers=lecturer_headers,
    )
    assert target.status_code == 200, target.text

    blocked = client.post(
        COPY,
        json=_copy_payload(periods["previous"], periods["active"]),
        headers=lecturer_headers,
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["error"]["code"] == "preferences_exist"
    assert blocked.json()["error"]["details"][0]["existing_count"] == 1
    assert client.get(PREFERENCES, headers=lecturer_headers).json() == target.json()

    overwritten = client.post(
        COPY,
        json=_copy_payload(periods["previous"], periods["active"], overwrite=True),
        headers=lecturer_headers,
    )
    assert overwritten.status_code == 200, overwritten.text
    assert overwritten.json()["data"] == [
        {
            "day_of_week": 1,
            "day_name": "Senin",
            "start_time": "08:00:00",
            "end_time": "10:00:00",
            "kind": "preferred",
        }
    ]

    assert client.put(
        PREFERENCES,
        params={"academic_period_id": str(periods["previous"])},
        json=[],
        headers=lecturer_headers,
    ).status_code == 200
    cleared = client.post(
        COPY,
        json=_copy_payload(periods["previous"], periods["active"], overwrite=True),
        headers=lecturer_headers,
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"] == []
    _assert_empty_meta(cleared.json())


def test_copy_rejects_same_unknown_and_foreign_identity_periods(
    client, db_session, lecturer_headers
):
    periods = _periods(client, db_session)
    same = client.post(
        COPY,
        json=_copy_payload(periods["active"], periods["active"]),
        headers=lecturer_headers,
    )
    assert same.status_code == 422, same.text
    assert same.json()["error"]["code"] == "same_period"

    for source, target in (
        (uuid.uuid4(), periods["active"]),
        (periods["previous"], uuid.uuid4()),
    ):
        missing = client.post(
            COPY,
            json=_copy_payload(source, target),
            headers=lecturer_headers,
        )
        assert missing.status_code == 404, missing.text
        assert missing.json()["error"]["code"] == "period_not_found"

    foreign_identity = client.post(
        COPY,
        json={
            **_copy_payload(periods["previous"], periods["active"]),
            "user_id": str(uuid.uuid4()),
        },
        headers=lecturer_headers,
    )
    assert foreign_identity.status_code == 422
    assert foreign_identity.json()["error"]["code"] == "validation_error"

    for method, path, kwargs in (
        ("get", PREFERENCES, {"params": {"academic_period_id": str(uuid.uuid4())}}),
        (
            "put",
            PREFERENCES,
            {
                "params": {"academic_period_id": str(uuid.uuid4())},
                "json": [SLOT],
            },
        ),
    ):
        response = getattr(client, method)(path, headers=lecturer_headers, **kwargs)
        assert response.status_code == 404, response.text
        assert response.json()["error"]["code"] == "period_not_found"


def test_preferences_are_self_only_for_all_roles(
    client, db_session, lecturer_headers, student_headers, admin_headers
):
    periods = _periods(client, db_session)
    lecturer_id = _user_id(client, db_session, SEEDED_LECTURER[0])

    async def create_lecturers():
        program = (
            await db_session.execute(
                select(StudyProgram).where(StudyProgram.program_code == "TSD")
            )
        ).scalars().one()
        suffix = uuid.uuid4().hex[:8]
        profileless = User(
            email=f"preference.no-profile.{suffix}@ftmm.unair.ac.id",
            full_name="Dosen Tanpa Profil",
            role="lecturer",
            is_active=True,
            password_hash=get_password_hash(PASSWORD),
        )
        ordinary = User(
            email=f"preference.ordinary.{suffix}@ftmm.unair.ac.id",
            full_name="Dosen Biasa",
            role="lecturer",
            is_active=True,
            password_hash=get_password_hash(PASSWORD),
        )
        db_session.add_all([profileless, ordinary])
        await db_session.flush()
        db_session.add(
            LecturerProfile(
                user_id=ordinary.user_id,
                study_program_id=program.study_program_id,
                is_program_coordinator=False,
            )
        )
        await db_session.commit()
        return profileless.email, ordinary.email, ordinary.user_id

    profileless_email, ordinary_email, ordinary_id = client.portal.call(create_lecturers)
    profileless_headers = _login_headers(client, profileless_email)
    ordinary_headers = _login_headers(client, ordinary_email)
    payload = _copy_payload(periods["previous"], periods["active"])
    for headers in (student_headers, admin_headers, profileless_headers):
        assert client.put(
            PREFERENCES, json=[SLOT], headers=headers
        ).status_code == 403
        assert client.post(COPY, json=payload, headers=headers).status_code == 403

    ordinary_slot = _slot(
        day_of_week=2,
        kind="unavailable",
        start_time="15:00:00",
        end_time="17:00:00",
    )
    ordinary_saved = client.put(
        PREFERENCES,
        params={"academic_period_id": str(periods["active"])},
        json=[ordinary_slot],
        headers=ordinary_headers,
    )
    assert ordinary_saved.status_code == 200, ordinary_saved.text
    assert ordinary_saved.json()["user_id"] == str(ordinary_id)
    foreign_identity = client.put(
        PREFERENCES,
        params={"academic_period_id": str(periods["active"])},
        json={"slots": [SLOT], "user_id": str(uuid.uuid4())},
        headers=ordinary_headers,
    )
    assert foreign_identity.status_code == 422
    assert foreign_identity.json()["error"]["code"] == "validation_error"
    assert client.get(
        PREFERENCES,
        params={"academic_period_id": str(periods["active"])},
        headers=ordinary_headers,
    ).json() == ordinary_saved.json()

    assert client.put(
        PREFERENCES, json=[SLOT], headers=lecturer_headers
    ).status_code == 200
    assert client.put(
        f"{PREFERENCES}/{uuid.uuid4()}", json=[SLOT], headers=lecturer_headers
    ).status_code == 404
    foreign_query = client.get(
        PREFERENCES,
        params={"user_id": str(uuid.uuid4())},
        headers=lecturer_headers,
    )
    assert foreign_query.status_code == 200, foreign_query.text
    assert foreign_query.json()["user_id"] == str(lecturer_id)


@mark.parametrize("prefix", (V1, LEGACY))
def test_preference_canonical_and_legacy_payloads_and_errors_match(
    client, db_session, lecturer_headers, prefix
):
    periods = _periods(client, db_session)
    _clear_lecturer_preferences(client, db_session)
    canonical = client.put(
        PREFERENCES,
        params={"academic_period_id": str(periods["previous"])},
        json=[SLOT],
        headers=lecturer_headers,
    )
    legacy = client.put(
        f"{prefix}/scheduling/preferences/me",
        json={
            "academic_period_id": str(periods["previous"]),
            "slots": [SLOT],
        },
        headers=lecturer_headers,
    )
    assert canonical.status_code == legacy.status_code == 200
    assert canonical.json() == legacy.json()
    assert client.get(
        f"{prefix}/scheduling/preferences/me",
        params={"academic_period_id": str(periods["previous"])},
        headers=lecturer_headers,
    ).json() == canonical.json()

    copied = client.post(
        f"{prefix}/scheduling/preferences/me/copy",
        json=_copy_payload(periods["previous"], periods["active"]),
        headers=lecturer_headers,
    )
    assert copied.status_code == 200, copied.text
    assert copied.json()["data"] == canonical.json()["data"]

    overlap = [SLOT, _slot(kind="unavailable", start_time="09:00:00", end_time="11:00:00")]
    canonical_error = client.put(
        PREFERENCES, json=overlap, headers=lecturer_headers
    )
    legacy_error = client.put(
        f"{prefix}/scheduling/preferences/me", json=overlap, headers=lecturer_headers
    )
    assert canonical_error.status_code == legacy_error.status_code == 422
    assert canonical_error.json() == legacy_error.json()


def _assigned_class_case(
    client, db_session, lecturer_id: uuid.UUID, other_period_id: uuid.UUID
) -> dict[str, Any]:
    async def setup():
        suffix = uuid.uuid4().hex[:8]
        active = (
            await db_session.execute(
                select(AcademicPeriod)
                .where(AcademicPeriod.is_active.is_(True))
                .order_by(
                    AcademicPeriod.academic_year_start.desc(),
                    AcademicPeriod.created_at.desc(),
                    AcademicPeriod.academic_period_id,
                )
                .limit(1)
            )
        ).scalars().one()
        program = (
            await db_session.execute(
                select(StudyProgram).where(StudyProgram.program_code == "TSD")
            )
        ).scalars().one()
        other_lecturer_id = (
            await db_session.execute(
                select(User.user_id)
                .join(LecturerProfile, LecturerProfile.user_id == User.user_id)
                .where(
                    User.role == "lecturer",
                    User.is_active.is_(True),
                    User.user_id != lecturer_id,
                )
                .order_by(User.user_id)
                .limit(1)
            )
        ).scalar_one()
        curriculum = Curriculum(
            study_program_id=program.study_program_id,
            curriculum_name=f"Kurikulum Preferensi {suffix}",
            curriculum_year=active.academic_year_start,
            is_active=True,
        )
        db_session.add(curriculum)
        await db_session.flush()
        course_code = f"PR{uuid.uuid4().int % 10_000:04d}"
        while (
            await db_session.execute(
                select(Course.course_id).where(Course.course_code == course_code)
            )
        ).first() is not None:
            course_code = f"PR{uuid.uuid4().int % 10_000:04d}"
        course = Course(
            course_code=course_code,
            course_name=f"Mata Kuliah Preferensi {suffix}",
            is_active=True,
        )
        db_session.add(course)
        await db_session.flush()
        curriculum_course = CurriculumCourse(
            curriculum_id=curriculum.curriculum_id,
            course_id=course.course_id,
            credits_total=2,
            recommended_semester=1,
            term=active.term,
            course_type="wajib",
            course_scope="program_studi",
            is_active=True,
        )
        db_session.add(curriculum_course)
        await db_session.flush()
        offering = CourseOffering(
            academic_period_id=active.academic_period_id,
            course_id=course.course_id,
            offering_code=f"PREF-{suffix}",
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
        section_a = ClassSection(
            offering_component_id=component.offering_component_id,
            section_code="A",
            capacity=40,
            enrollment_status="open",
        )
        section_b = ClassSection(
            offering_component_id=component.offering_component_id,
            section_code="B",
            capacity=40,
            enrollment_status="open",
        )
        db_session.add_all([section_a, section_b])
        await db_session.flush()
        db_session.add_all(
            [
                ClassSchedule(
                    class_section_id=section_a.class_section_id,
                    day_of_week=1,
                    start_time=time(8),
                    end_time=time(10),
                    room_name=f"PREF-A-{suffix}",
                ),
                ClassSchedule(
                    class_section_id=section_b.class_section_id,
                    day_of_week=1,
                    start_time=time(13),
                    end_time=time(15),
                    room_name=f"PREF-B-{suffix}",
                ),
            ]
        )
        db_session.add(
            CourseInstructorReference(
                curriculum_course_id=curriculum_course.curriculum_course_id,
                instructor_name="Dosen Tim Pengajar",
                instructor_role="teaching_team",
                user_id=lecturer_id,
            )
        )
        db_session.add_all(
            [
                ClassInstructorAssignment(
                    class_section_id=section_a.class_section_id,
                    academic_period_id=active.academic_period_id,
                    user_id=lecturer_id,
                    source="manual",
                    is_pinned=False,
                    is_active=True,
                    assigned_by=lecturer_id,
                ),
                ClassInstructorAssignment(
                    class_section_id=section_b.class_section_id,
                    academic_period_id=other_period_id,
                    user_id=lecturer_id,
                    source="manual",
                    is_pinned=False,
                    is_active=True,
                    assigned_by=lecturer_id,
                ),
            ]
        )
        await db_session.commit()
        return {
            "active": active.academic_period_id,
            "class_a": section_a.class_section_id,
            "class_b": section_b.class_section_id,
            "course_code": course.course_code,
            "course_name": course.course_name,
            "other_lecturer_id": other_lecturer_id,
        }

    return client.portal.call(setup)


def test_unavailable_assigned_class_overlap_warns_without_rejecting_save(
    client, db_session, lecturer_headers
):
    periods = _periods(client, db_session)
    lecturer_id = _user_id(client, db_session, SEEDED_LECTURER[0])
    case = _assigned_class_case(client, db_session, lecturer_id, periods["following"])
    other_id = case["other_lecturer_id"]
    slots = [
        _slot(kind="unavailable", start_time="08:00:00", end_time="11:00:00"),
        _slot(kind="unavailable", start_time="13:00:00", end_time="14:00:00"),
    ]
    saved = client.put(
        PREFERENCES,
        params={"academic_period_id": str(case["active"])},
        json=slots,
        headers=lecturer_headers,
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["meta"]["unavailable_count"] == 2
    warnings = body["meta"]["warnings"]
    assert warnings
    for candidate in warnings:
        _assert_valid_overlap_warning(candidate)
    warning = next(
        item
        for item in warnings
        if item["class_section_id"] == str(case["class_a"])
    )
    assert warning["code"] == "assigned_class_overlap"
    assert warning["class_section_id"] == str(case["class_a"])
    assert warning["course_code"] == case["course_code"]
    assert warning["course_name"] == case["course_name"]
    assert warning["section_code"] == "A"
    assert warning["day_of_week"] == 1
    assert warning["day_name"] == "Senin"
    assert warning["unavailable_start_time"] == "08:00:00"
    assert warning["unavailable_end_time"] == "11:00:00"
    assert warning["class_start_time"] == "08:00:00"
    assert warning["class_end_time"] == "10:00:00"
    assert warning["overlap_start_time"] == "08:00:00"
    assert warning["overlap_end_time"] == "10:00:00"
    assert client.get(
        PREFERENCES,
        params={"academic_period_id": str(case["active"])},
        headers=lecturer_headers,
    ).json() == body

    async def deactivate_assignment():
        await db_session.execute(
            update(ClassInstructorAssignment)
            .where(ClassInstructorAssignment.class_section_id == case["class_a"])
            .values(is_active=False)
        )
        await db_session.execute(
            update(ClassInstructorAssignment)
            .where(ClassInstructorAssignment.class_section_id == case["class_b"])
            .values(
                academic_period_id=case["active"],
                user_id=other_id,
                is_active=True,
            )
        )
        await db_session.commit()

    client.portal.call(deactivate_assignment)
    without_active_assignment = client.put(
        PREFERENCES,
        params={"academic_period_id": str(case["active"])},
        json=slots,
        headers=lecturer_headers,
    )
    assert without_active_assignment.status_code == 200, without_active_assignment.text
    remaining_warnings = without_active_assignment.json()["meta"]["warnings"]
    for candidate in remaining_warnings:
        _assert_valid_overlap_warning(candidate)
    assert all(
        item["class_section_id"]
        not in {str(case["class_a"]), str(case["class_b"])}
        for item in remaining_warnings
    )
    assert len(without_active_assignment.json()["data"]) == 2


def test_class_assignment_rejects_global_only_reference_on_canonical_and_legacy(
    client, db_session, admin_headers
):
    periods = _periods(client, db_session)
    lecturer_id = _user_id(client, db_session, SEEDED_LECTURER[0])
    case = _assigned_class_case(client, db_session, lecturer_id, periods["following"])
    for prefix in (V1, LEGACY):
        response = client.put(
            f"{prefix}/scheduling/classes/{case['class_a']}/assignment",
            headers=admin_headers,
            json={
                "academic_period_id": str(case["active"]),
                "user_id": str(case["other_lecturer_id"]),
                "source": "manual",
                "is_pinned": False,
            },
        )
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "lecturer_not_in_pool"

    async def assignments_for_class():
        return (
            await db_session.execute(
                select(ClassInstructorAssignment.user_id).where(
                    ClassInstructorAssignment.class_section_id == case["class_a"]
                )
            )
        ).scalars().all()

    assert client.portal.call(assignments_for_class) == [lecturer_id]
