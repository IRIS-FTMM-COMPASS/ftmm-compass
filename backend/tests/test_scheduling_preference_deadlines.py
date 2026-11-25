"""HTTP contract for preference deadlines and PJ completeness summaries."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update

from auth import get_password_hash
from models import (
    AcademicPeriod,
    LecturerProfile,
    SchedulePeriodSettings,
    StudyProgram,
    User,
)
from rate_limit import limiter
from tests.conftest import SEEDED_PJ

V1 = "/api/v1"
LEGACY = "/api"
SETTINGS = f"{V1}/scheduling/period-settings"
SUMMARY = f"{V1}/scheduling/preferences/summary"
PREFERENCES = f"{V1}/scheduling/preferences/me"
COPY = f"{V1}/scheduling/preferences/me/copy"
PASSWORD = "DeadlineUji2026!"
GLOBAL_DEADLINE = "2027-01-15T23:59:00Z"
PROGRAM_DEADLINE = "2027-01-10T12:00:00Z"
PAST_DEADLINE = "2020-01-01T00:00:00Z"
SLOT = {
    "day_of_week": 1,
    "start_time": "08:00:00",
    "end_time": "10:00:00",
    "kind": "preferred",
}


def _login_headers(client, email: str) -> dict[str, str]:
    limiter.reset()
    response = client.post(
        f"{V1}/auth/login",
        json={"identifier": email, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _case(client, db_session) -> dict[str, Any]:
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
        other_year = active.academic_year_start + 1
        while other_year in used_years:
            other_year += 1
        seed = f"ftmm-compass:deadline-period:{other_year}:ganjil"
        other_id = uuid.uuid5(uuid.NAMESPACE_URL, seed)
        suffix = 1
        while other_id in used_ids:
            other_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{seed}:{suffix}")
            suffix += 1
        other_period = AcademicPeriod(
            academic_period_id=other_id,
            academic_year_start=other_year,
            semester_number=1,
            term="ganjil",
            is_active=False,
        )
        db_session.add(other_period)
        await db_session.flush()

        pj_user_id = (
            await db_session.execute(
                select(User.user_id).where(User.email == SEEDED_PJ[0])
            )
        ).scalar_one()
        own_program_id = (
            await db_session.execute(
                select(LecturerProfile.study_program_id).where(
                    LecturerProfile.user_id == pj_user_id
                )
            )
        ).scalar_one()
        other_program = (
            await db_session.execute(
                select(StudyProgram)
                .where(StudyProgram.study_program_id != own_program_id)
                .order_by(StudyProgram.program_code)
                .limit(1)
            )
        ).scalars().one()

        suffix = uuid.uuid4().hex[:8]
        accounts = {}
        for label, program_id, is_active in (
            ("filled", own_program_id, True),
            ("empty", own_program_id, True),
            ("other", other_program.study_program_id, True),
            ("inactive", own_program_id, False),
        ):
            user = User(
                email=f"deadline.{label}.{suffix}@ftmm.unair.ac.id",
                full_name=f"Dosen Deadline {label}",
                role="lecturer",
                is_active=is_active,
                password_hash=get_password_hash(PASSWORD),
            )
            db_session.add(user)
            accounts[label] = (user, program_id)
        await db_session.flush()
        for user, program_id in accounts.values():
            db_session.add(
                LecturerProfile(
                    user_id=user.user_id,
                    study_program_id=program_id,
                    is_program_coordinator=False,
                )
            )
        await db_session.commit()
        return {
            "period": active.academic_period_id,
            "other_period": other_period.academic_period_id,
            "own_program": own_program_id,
            "other_program": other_program.study_program_id,
            "filled_id": accounts["filled"][0].user_id,
            "empty_id": accounts["empty"][0].user_id,
            "other_id": accounts["other"][0].user_id,
            "inactive_id": accounts["inactive"][0].user_id,
            "filled_email": accounts["filled"][0].email,
            "empty_email": accounts["empty"][0].email,
            "other_email": accounts["other"][0].email,
        }

    return client.portal.call(setup)


def _settings_payload(
    period_id: uuid.UUID,
    deadline: str | None,
    program_id: uuid.UUID | None = None,
    *,
    include_program: bool = True,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "academic_period_id": str(period_id),
        "preference_deadline": deadline,
    }
    if include_program:
        payload["study_program_id"] = str(program_id) if program_id else None
    return payload


def _put_setting(client, headers, period_id, deadline, program_id=None, **kwargs):
    return client.put(
        SETTINGS,
        json=_settings_payload(period_id, deadline, program_id, **kwargs),
        headers=headers,
    )


def test_deadline_endpoints_require_authentication(client):
    period_id = uuid.uuid4()
    assert client.get(SETTINGS, params={"academic_period_id": str(period_id)}).status_code == 401
    assert client.put(
        SETTINGS, json=_settings_payload(period_id, GLOBAL_DEADLINE)
    ).status_code == 401
    assert client.get(SUMMARY, params={"academic_period_id": str(period_id)}).status_code == 401


def test_admin_manages_global_and_program_settings(client, db_session, admin_headers):
    case = _case(client, db_session)
    default = client.get(
        SETTINGS,
        params={"academic_period_id": str(case["period"])},
        headers=admin_headers,
    )
    assert default.status_code == 200, default.text
    assert default.json()["study_program_id"] is None
    assert default.json()["preference_deadline"] is None
    assert default.json()["input_revision"] == 0

    global_settings = _put_setting(
        client, admin_headers, case["period"], GLOBAL_DEADLINE
    )
    assert global_settings.status_code == 200, global_settings.text
    assert global_settings.json()["study_program_id"] is None
    assert _instant(global_settings.json()["preference_deadline"]) == _instant(
        GLOBAL_DEADLINE
    )
    settings_id = global_settings.json()["input_revision"]

    repeated = _put_setting(client, admin_headers, case["period"], GLOBAL_DEADLINE)
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["preference_deadline"] == global_settings.json()["preference_deadline"]
    assert repeated.json()["input_revision"] == settings_id

    program_settings = _put_setting(
        client,
        admin_headers,
        case["period"],
        PROGRAM_DEADLINE,
        case["own_program"],
    )
    assert program_settings.status_code == 200, program_settings.text
    assert program_settings.json()["study_program_id"] == str(case["own_program"])
    assert program_settings.json()["study_program_code"]
    assert _instant(program_settings.json()["preference_deadline"]) == _instant(
        PROGRAM_DEADLINE
    )

    fetched = client.get(
        SETTINGS,
        params={
            "academic_period_id": str(case["period"]),
            "study_program_id": str(case["own_program"]),
        },
        headers=admin_headers,
    )
    assert fetched.status_code == 200, fetched.text
    assert fetched.json() == program_settings.json()
    assert client.get(
        SETTINGS,
        params={"academic_period_id": str(case["period"])},
        headers=admin_headers,
    ).json() == global_settings.json()

    missing_program = client.get(
        SETTINGS,
        params={
            "academic_period_id": str(case["period"]),
            "study_program_id": str(uuid.uuid4()),
        },
        headers=admin_headers,
    )
    assert missing_program.status_code == 404
    assert missing_program.json()["error"]["code"] == "study_program_not_found"
    missing_period = client.get(
        SETTINGS,
        params={"academic_period_id": str(uuid.uuid4())},
        headers=admin_headers,
    )
    assert missing_period.status_code == 404
    assert missing_period.json()["error"]["code"] == "period_not_found"
    missing_program_write = _put_setting(
        client,
        admin_headers,
        case["period"],
        GLOBAL_DEADLINE,
        uuid.uuid4(),
    )
    assert missing_program_write.status_code == 404
    assert missing_program_write.json()["error"]["code"] == "study_program_not_found"
    missing_period_write = _put_setting(
        client, admin_headers, uuid.uuid4(), GLOBAL_DEADLINE
    )
    assert missing_period_write.status_code == 404
    assert missing_period_write.json()["error"]["code"] == "period_not_found"
    invalid_deadline = client.put(
        SETTINGS,
        json=_settings_payload(case["period"], "bukan-tanggal"),
        headers=admin_headers,
    )
    assert invalid_deadline.status_code == 422
    assert invalid_deadline.json()["error"]["code"] == "validation_error"
    invalid = client.put(
        SETTINGS,
        json={
            **_settings_payload(case["period"], GLOBAL_DEADLINE),
            "input_revision": 99,
        },
        headers=admin_headers,
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"


def test_pj_settings_scope_is_own_program(
    client, db_session, pj_headers, student_headers
):
    case = _case(client, db_session)
    ordinary_headers = _login_headers(client, case["empty_email"])

    own = _put_setting(
        client,
        pj_headers,
        case["period"],
        PROGRAM_DEADLINE,
        include_program=False,
    )
    assert own.status_code == 200, own.text
    assert own.json()["study_program_id"] == str(case["own_program"])
    explicit_own = _put_setting(
        client,
        pj_headers,
        case["period"],
        PROGRAM_DEADLINE,
        case["own_program"],
    )
    assert explicit_own.status_code == 200, explicit_own.text

    for program_id in (None, case["other_program"]):
        denied = _put_setting(
            client, pj_headers, case["period"], GLOBAL_DEADLINE, program_id
        )
        assert denied.status_code == 403, denied.text
        assert denied.json()["error"]["code"] == "forbidden"

    fetched = client.get(
        SETTINGS,
        params={"academic_period_id": str(case["period"])},
        headers=pj_headers,
    )
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["study_program_id"] == str(case["own_program"])
    foreign = client.get(
        SETTINGS,
        params={
            "academic_period_id": str(case["period"]),
            "study_program_id": str(case["other_program"]),
        },
        headers=pj_headers,
    )
    assert foreign.status_code == 403
    assert foreign.json()["error"]["code"] == "forbidden"

    for headers in (student_headers, ordinary_headers):
        assert client.get(
            SETTINGS,
            params={"academic_period_id": str(case["period"])},
            headers=headers,
        ).status_code == 403
        assert _put_setting(
            client, headers, case["period"], GLOBAL_DEADLINE
        ).status_code == 403


def test_self_deadline_uses_program_override_then_global_fallback(
    client, db_session, admin_headers
):
    case = _case(client, db_session)
    own_headers = _login_headers(client, case["filled_email"])
    other_headers = _login_headers(client, case["other_email"])

    assert _put_setting(
        client, admin_headers, case["period"], GLOBAL_DEADLINE
    ).status_code == 200
    own = client.get(
        PREFERENCES,
        params={"academic_period_id": str(case["period"])},
        headers=own_headers,
    )
    other = client.get(
        PREFERENCES,
        params={"academic_period_id": str(case["period"])},
        headers=other_headers,
    )
    assert own.status_code == other.status_code == 200
    assert _instant(own.json()["meta"]["deadline"]) == _instant(GLOBAL_DEADLINE)
    assert _instant(other.json()["meta"]["deadline"]) == _instant(GLOBAL_DEADLINE)

    assert _put_setting(
        client,
        admin_headers,
        case["period"],
        PROGRAM_DEADLINE,
        case["own_program"],
    ).status_code == 200
    overridden = client.get(
        PREFERENCES,
        params={"academic_period_id": str(case["period"])},
        headers=own_headers,
    )
    assert _instant(overridden.json()["meta"]["deadline"]) == _instant(
        PROGRAM_DEADLINE
    )
    assert _instant(
        client.get(
            PREFERENCES,
            params={"academic_period_id": str(case["period"])},
            headers=other_headers,
        ).json()["meta"]["deadline"]
    ) == _instant(GLOBAL_DEADLINE)

    assert _put_setting(
        client,
        admin_headers,
        case["period"],
        None,
        case["own_program"],
    ).status_code == 200
    fallback = client.get(
        PREFERENCES,
        params={"academic_period_id": str(case["period"])},
        headers=own_headers,
    )
    assert _instant(fallback.json()["meta"]["deadline"]) == _instant(GLOBAL_DEADLINE)

    isolated = client.get(
        PREFERENCES,
        params={"academic_period_id": str(case["other_period"])},
        headers=own_headers,
    )
    assert isolated.status_code == 200, isolated.text
    assert isolated.json()["meta"]["deadline"] is None


def test_summary_scope_completeness_and_deadlines(
    client, db_session, admin_headers, pj_headers, student_headers
):
    case = _case(client, db_session)
    filled_headers = _login_headers(client, case["filled_email"])
    ordinary_headers = _login_headers(client, case["empty_email"])
    assert _put_setting(
        client, admin_headers, case["period"], GLOBAL_DEADLINE
    ).status_code == 200
    assert _put_setting(
        client,
        admin_headers,
        case["period"],
        PROGRAM_DEADLINE,
        case["own_program"],
    ).status_code == 200
    saved = client.put(
        PREFERENCES,
        params={"academic_period_id": str(case["period"])},
        json=[
            SLOT,
            {
                **SLOT,
                "day_of_week": 2,
                "start_time": "13:00:00",
                "end_time": "15:00:00",
                "kind": "unavailable",
            },
        ],
        headers=filled_headers,
    )
    assert saved.status_code == 200, saved.text

    own = client.get(
        SUMMARY,
        params={"academic_period_id": str(case["period"])},
        headers=pj_headers,
    )
    assert own.status_code == 200, own.text
    own_body = own.json()
    assert own_body["meta"]["total"] == len(own_body["data"])
    assert own_body["meta"]["filled"] == sum(
        item["status"] == "filled" for item in own_body["data"]
    )
    assert own_body["meta"]["empty"] == sum(
        item["status"] == "empty" for item in own_body["data"]
    )
    own_ids = {item["user_id"] for item in own_body["data"]}
    assert {str(case["filled_id"]), str(case["empty_id"])} <= own_ids
    assert str(case["other_id"]) not in own_ids
    assert str(case["inactive_id"]) not in own_ids
    filled = next(
        item for item in own_body["data"] if item["user_id"] == str(case["filled_id"])
    )
    empty = next(
        item for item in own_body["data"] if item["user_id"] == str(case["empty_id"])
    )
    assert filled["status"] == "filled"
    assert filled["preferred_count"] == 1
    assert filled["unavailable_count"] == 1
    assert empty["status"] == "empty"
    assert empty["preferred_count"] == empty["unavailable_count"] == 0
    assert _instant(filled["deadline"]) == _instant(PROGRAM_DEADLINE)
    assert _instant(empty["deadline"]) == _instant(PROGRAM_DEADLINE)

    foreign = client.get(
        SUMMARY,
        params={
            "academic_period_id": str(case["period"]),
            "study_program_id": str(case["other_program"]),
        },
        headers=pj_headers,
    )
    assert foreign.status_code == 403
    assert foreign.json()["error"]["code"] == "forbidden"

    other = client.get(
        SUMMARY,
        params={
            "academic_period_id": str(case["period"]),
            "study_program_id": str(case["other_program"]),
        },
        headers=admin_headers,
    )
    assert other.status_code == 200, other.text
    other_item = next(
        item
        for item in other.json()["data"]
        if item["user_id"] == str(case["other_id"])
    )
    assert other_item["status"] == "empty"
    assert _instant(other_item["deadline"]) == _instant(GLOBAL_DEADLINE)

    all_programs = client.get(
        SUMMARY,
        params={"academic_period_id": str(case["period"])},
        headers=admin_headers,
    )
    assert all_programs.status_code == 200, all_programs.text
    all_body = all_programs.json()
    assert all_body["meta"]["total"] == len(all_body["data"])
    assert all_body["meta"]["filled"] == sum(
        item["status"] == "filled" for item in all_body["data"]
    )
    assert all_body["meta"]["empty"] == sum(
        item["status"] == "empty" for item in all_body["data"]
    )
    all_ids = {item["user_id"] for item in all_body["data"]}
    assert {
        str(case["filled_id"]),
        str(case["empty_id"]),
        str(case["other_id"]),
    } <= all_ids
    assert str(case["inactive_id"]) not in all_ids

    for headers in (student_headers, ordinary_headers):
        denied = client.get(
            SUMMARY,
            params={"academic_period_id": str(case["period"])},
            headers=headers,
        )
        assert denied.status_code == 403
        assert denied.json()["error"]["code"] == "forbidden"


def test_summary_is_read_only_while_pj_retains_self_service(
    client, db_session, admin_headers, pj_headers
):
    case = _case(client, db_session)
    for method in ("put", "post", "patch", "delete"):
        if method == "delete":
            response = client.request(
                "DELETE",
                SUMMARY,
                params={"academic_period_id": str(case["period"])},
                headers=admin_headers,
            )
        else:
            response = getattr(client, method)(
                SUMMARY,
                params={"academic_period_id": str(case["period"])},
                headers=admin_headers,
                json={},
            )
        assert response.status_code == 405, response.text

    assert client.put(
        PREFERENCES,
        params={"academic_period_id": str(case["period"])},
        json=[SLOT],
        headers=admin_headers,
    ).status_code == 403
    assert client.put(
        PREFERENCES,
        params={"academic_period_id": str(case["period"])},
        json=[SLOT],
        headers=pj_headers,
    ).status_code == 200
    assert client.post(
        COPY,
        json={
            "from_academic_period_id": str(case["other_period"]),
            "academic_period_id": str(case["period"]),
            "overwrite": True,
        },
        headers=pj_headers,
    ).status_code == 200


def test_past_deadline_does_not_block_edit_or_copy(client, db_session, pj_headers):
    case = _case(client, db_session)
    headers = _login_headers(client, case["filled_email"])
    setting = _put_setting(
        client,
        pj_headers,
        case["period"],
        PAST_DEADLINE,
        include_program=False,
    )
    assert setting.status_code == 200, setting.text
    assert _instant(setting.json()["preference_deadline"]) < datetime.now(timezone.utc)

    edited = client.put(
        PREFERENCES,
        params={"academic_period_id": str(case["period"])},
        json=[SLOT],
        headers=headers,
    )
    assert edited.status_code == 200, edited.text
    assert _instant(edited.json()["meta"]["deadline"]) == _instant(PAST_DEADLINE)

    assert client.put(
        PREFERENCES,
        params={"academic_period_id": str(case["other_period"])},
        json=[SLOT],
        headers=headers,
    ).status_code == 200
    copied = client.post(
        COPY,
        json={
            "from_academic_period_id": str(case["other_period"]),
            "academic_period_id": str(case["period"]),
            "overwrite": True,
        },
        headers=headers,
    )
    assert copied.status_code == 200, copied.text
    assert _instant(copied.json()["meta"]["deadline"]) == _instant(PAST_DEADLINE)


def test_deadline_settings_and_summary_legacy_parity(
    client, db_session, admin_headers, pj_headers
):
    case = _case(client, db_session)
    canonical_setting = _put_setting(
        client, admin_headers, case["period"], GLOBAL_DEADLINE
    )
    legacy_setting = client.put(
        f"{LEGACY}/scheduling/period-settings",
        json=_settings_payload(case["period"], GLOBAL_DEADLINE),
        headers=admin_headers,
    )
    assert canonical_setting.status_code == legacy_setting.status_code == 200
    assert canonical_setting.json() == legacy_setting.json()
    assert client.get(
        SETTINGS,
        params={"academic_period_id": str(case["period"])},
        headers=admin_headers,
    ).json() == client.get(
        f"{LEGACY}/scheduling/period-settings",
        params={"academic_period_id": str(case["period"])},
        headers=admin_headers,
    ).json()

    canonical_summary = client.get(
        SUMMARY,
        params={"academic_period_id": str(case["period"])},
        headers=pj_headers,
    )
    legacy_summary = client.get(
        f"{LEGACY}/scheduling/preferences/summary",
        params={"academic_period_id": str(case["period"])},
        headers=pj_headers,
    )
    assert canonical_summary.status_code == legacy_summary.status_code == 200
    assert canonical_summary.json() == legacy_summary.json()

    headers = _login_headers(client, case["empty_email"])
    assert client.get(
        PREFERENCES,
        params={"academic_period_id": str(case["period"])},
        headers=headers,
    ).json() == client.get(
        f"{LEGACY}/scheduling/preferences/me",
        params={"academic_period_id": str(case["period"])},
        headers=headers,
    ).json()


def test_settings_update_preserves_input_revision(client, db_session, admin_headers):
    case = _case(client, db_session)
    first = _put_setting(client, admin_headers, case["period"], GLOBAL_DEADLINE)
    assert first.status_code == 200, first.text

    async def raise_revision():
        await db_session.execute(
            update(SchedulePeriodSettings)
            .where(
                SchedulePeriodSettings.academic_period_id == case["period"],
                SchedulePeriodSettings.study_program_id.is_(None),
            )
            .values(input_revision=7)
        )
        await db_session.commit()

    client.portal.call(raise_revision)
    changed = _put_setting(client, admin_headers, case["period"], PROGRAM_DEADLINE)
    assert changed.status_code == 200, changed.text
    assert changed.json()["input_revision"] == 7
