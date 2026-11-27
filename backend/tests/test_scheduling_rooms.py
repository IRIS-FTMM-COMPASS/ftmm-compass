"""Kontrak HTTP master ruang: pembuatan, pembaruan, dan scope PJ Prodi."""

import uuid

from sqlalchemy import select

from auth import get_password_hash
from models import LecturerProfile, StudyProgram, User

V1 = "/api/v1"
PATH = f"{V1}/scheduling/rooms"


def _code() -> str:
    return f"R{uuid.uuid4().hex[:10].upper()}"


def _program_id(client, db_session, program_code: str) -> str:
    async def run():
        value = (
            await db_session.execute(
                select(StudyProgram.study_program_id).where(
                    StudyProgram.program_code == program_code
                )
            )
        ).scalar_one()
        return str(value)

    return client.portal.call(run)


def _non_coordinator_headers(client, db_session) -> dict[str, str]:
    async def run():
        label = uuid.uuid4().hex[:8]
        program = (
            await db_session.execute(
                select(StudyProgram).where(StudyProgram.program_code == "TSD")
            )
        ).scalars().one()
        email = f"ruang.dosen.{label}@ftmm.unair.ac.id"
        user = User(
            email=email,
            full_name=f"Dosen Non-PJ {label}",
            role="lecturer",
            password_hash=get_password_hash("RuangUji2026!"),
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
        return email

    email = client.portal.call(run)
    response = client.post(
        f"{V1}/auth/login",
        json={"identifier": email, "password": "RuangUji2026!"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_room(client, admin_headers, db_session, **overrides) -> dict:
    payload = {
        "room_code": _code(),
        "building": "NANO",
        "capacity": 40,
        "is_active": True,
        "owner_study_program_id": _program_id(client, db_session, "TSD"),
        **overrides,
    }
    response = client.post(PATH, headers=admin_headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _by_id(body: dict, room_id: str) -> dict:
    return next(item for item in body["data"] if item["room_id"] == room_id)


def test_admin_create_update_and_list_room(client, admin_headers, db_session):
    tsd = _program_id(client, db_session, "TSD")
    other = _program_id(client, db_session, "TRKB")
    code = _code()

    created = _create_room(
        client,
        admin_headers,
        db_session,
        room_code=code,
        capacity=36,
        owner_study_program_id=tsd,
    )
    assert created["room_code"] == code
    assert created["capacity"] == 36
    assert created["owner_study_program_id"] == tsd
    assert created["is_active"] is True
    assert created["room_id"]

    updated = client.patch(
        f"{PATH}/{created['room_id']}",
        headers=admin_headers,
        json={
            "capacity": 60,
            "owner_study_program_id": other,
            "is_active": False,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json() == {
        **created,
        "capacity": 60,
        "owner_study_program_id": other,
        "is_active": False,
    }

    listing = client.get(PATH, headers=admin_headers)
    assert listing.status_code == 200, listing.text
    body = listing.json()
    assert body["meta"]["total"] == len(body["data"])
    assert _by_id(body, created["room_id"]) == updated.json()

    legacy = client.get("/api/scheduling/rooms", headers=admin_headers)
    assert legacy.status_code == 200, legacy.text
    assert legacy.json() == body


def test_duplicate_code_conflicts_on_create_and_update(
    client, admin_headers, db_session
):
    code = _code()
    first = _create_room(client, admin_headers, db_session, room_code=code)
    second = client.post(
        PATH,
        headers=admin_headers,
        json={"room_code": code, "capacity": 20, "building": "NANO"},
    )
    assert second.status_code == 409, second.text
    assert second.json()["error"]["code"] == "room_code_exists"

    other = _create_room(client, admin_headers, db_session)
    conflict = client.patch(
        f"{PATH}/{other['room_id']}",
        headers=admin_headers,
        json={"room_code": code},
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["error"]["code"] == "room_code_exists"
    assert first["room_code"] == code


def test_capacity_below_one_is_rejected(client, admin_headers, db_session):
    tsd = _program_id(client, db_session, "TSD")
    for capacity in (0, -1):
        response = client.post(
            PATH,
            headers=admin_headers,
            json={
                "room_code": _code(),
                "capacity": capacity,
                "building": "NANO",
                "owner_study_program_id": tsd,
            },
        )
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "validation_error"


def test_pj_prodi_sees_owned_and_shared_rooms_but_cannot_manage(
    client, admin_headers, pj_headers, student_headers, db_session
):
    tsd = _program_id(client, db_session, "TSD")
    other = _program_id(client, db_session, "TRKB")
    own = _create_room(client, admin_headers, db_session, owner_study_program_id=tsd)
    foreign = _create_room(
        client, admin_headers, db_session, owner_study_program_id=other
    )
    shared = _create_room(client, admin_headers, db_session, owner_study_program_id=None)

    admin_body = client.get(PATH, headers=admin_headers).json()
    assert _by_id(admin_body, own["room_id"])["room_code"] == own["room_code"]
    assert _by_id(admin_body, foreign["room_id"])["room_code"] == foreign["room_code"]

    pj_response = client.get(PATH, headers=pj_headers)
    assert pj_response.status_code == 200, pj_response.text
    pj_body = pj_response.json()
    pj_ids = {item["room_id"] for item in pj_body["data"]}
    assert own["room_id"] in pj_ids
    assert foreign["room_id"] not in pj_ids
    assert shared["room_id"] in pj_ids
    assert all(item["owner_study_program_id"] in (tsd, None) for item in pj_body["data"])

    student = client.get(PATH, headers=student_headers)
    assert student.status_code == 403, student.text
    assert student.json()["error"]["code"] == "forbidden"
    lecturer = client.get(PATH, headers=_non_coordinator_headers(client, db_session))
    assert lecturer.status_code == 403, lecturer.text

    payload = {
        "room_code": _code(),
        "capacity": 20,
        "building": "NANO",
        "owner_study_program_id": tsd,
    }
    for tier in (V1, "/api"):
        write = client.post(f"{tier}/scheduling/rooms", headers=pj_headers, json=payload)
        assert write.status_code == 403, write.text
        assert write.json()["error"]["code"] == "forbidden"
        patch = client.patch(
            f"{tier}/scheduling/rooms/{own['room_id']}",
            headers=pj_headers,
            json={"capacity": 99},
        )
        assert patch.status_code == 403, patch.text
        assert patch.json()["error"]["code"] == "forbidden"

    after = client.get(PATH, headers=admin_headers).json()["data"]
    assert after == admin_body["data"]


def test_unknown_room_and_unknown_owner_are_rejected(
    client, admin_headers, db_session
):
    missing = client.patch(
        f"{PATH}/{uuid.uuid4()}",
        headers=admin_headers,
        json={"capacity": 10},
    )
    assert missing.status_code == 404, missing.text
    assert missing.json()["error"]["code"] == "room_not_found"

    unknown_owner = client.post(
        PATH,
        headers=admin_headers,
        json={
            "building": "NANO",
            "room_code": _code(),
            "capacity": 10,
            "owner_study_program_id": str(uuid.uuid4()),
        },
    )
    assert unknown_owner.status_code == 422, unknown_owner.text
    assert unknown_owner.json()["error"]["code"] == "validation_error"

    room = _create_room(client, admin_headers, db_session)
    unknown_owner_patch = client.patch(
        f"{PATH}/{room['room_id']}",
        headers=admin_headers,
        json={"owner_study_program_id": str(uuid.uuid4())},
    )
    assert unknown_owner_patch.status_code == 422, unknown_owner_patch.text
    assert unknown_owner_patch.json()["error"]["code"] == "validation_error"


def test_owner_can_be_omitted_or_cleared_for_shared_rooms(client, admin_headers, db_session):
    tsd = _program_id(client, db_session, "TSD")
    room = _create_room(client, admin_headers, db_session, owner_study_program_id=tsd)

    for owner in (None, "", "  "):
        response = client.post(
            PATH,
            headers=admin_headers,
            json={
                "room_code": _code(),
                "building": "NANO",
                "capacity": 20,
                "owner_study_program_id": owner,
            },
        )
        assert response.status_code == 201, response.text
        assert response.json()["owner_study_program_id"] is None

    cleared = client.patch(
        f"{PATH}/{room['room_id']}",
        headers=admin_headers,
        json={"owner_study_program_id": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["owner_study_program_id"] is None


def test_pj_cannot_create_rooms(client, admin_headers, pj_headers, db_session):
    tsd = _program_id(client, db_session, "TSD")
    other = _program_id(client, db_session, "TRKB")
    before = client.get(PATH, headers=admin_headers).json()["data"]

    for owner in (None, "", "  ", tsd, other):
        payload = {
            "room_code": _code(),
            "building": "NANO",
            "capacity": 24,
        }
        if owner is not None:
            payload["owner_study_program_id"] = owner
        for tier in (V1, "/api"):
            denied = client.post(
                f"{tier}/scheduling/rooms", headers=pj_headers, json=payload
            )
            assert denied.status_code == 403, denied.text
            assert denied.json()["error"]["code"] == "forbidden"

    admin_foreign = client.post(
        PATH,
        headers=admin_headers,
        json={
            "room_code": _code(),
            "building": "NANO",
            "capacity": 24,
            "owner_study_program_id": other,
        },
    )
    assert admin_foreign.status_code == 201, admin_foreign.text
    assert admin_foreign.json()["owner_study_program_id"] == other
    after = client.get(PATH, headers=admin_headers).json()["data"]
    assert len(after) == len(before) + 1


def test_pj_cannot_update_any_room(client, admin_headers, pj_headers, db_session):
    tsd = _program_id(client, db_session, "TSD")
    other = _program_id(client, db_session, "TRKB")
    own = _create_room(client, admin_headers, db_session, owner_study_program_id=tsd)
    shared = _create_room(client, admin_headers, db_session, owner_study_program_id=None)
    foreign = _create_room(
        client, admin_headers, db_session, owner_study_program_id=other
    )

    for room in (own, shared, foreign):
        for tier in (V1, "/api"):
            denied = client.patch(
                f"{tier}/scheduling/rooms/{room['room_id']}",
                headers=pj_headers,
                json={"capacity": 55},
            )
            assert denied.status_code == 403, denied.text
            assert denied.json()["error"]["code"] == "forbidden"

    listed = client.get(PATH, headers=admin_headers).json()
    for room in (own, shared, foreign):
        assert _by_id(listed, room["room_id"])["capacity"] == room["capacity"]


def test_pj_cannot_update_own_room_fields(client, admin_headers, pj_headers, db_session):
    tsd = _program_id(client, db_session, "TSD")
    other = _program_id(client, db_session, "TRKB")
    room = _create_room(client, admin_headers, db_session, owner_study_program_id=tsd)
    before = _by_id(client.get(PATH, headers=admin_headers).json(), room["room_id"])

    for payload in (
        {"capacity": 72, "is_active": False, "building": "NANO-B"},
        {"owner_study_program_id": tsd, "floor": "2"},
        {"capacity": 99, "owner_study_program_id": other},
        {"capacity": 99, "owner_study_program_id": None},
    ):
        for tier in (V1, "/api"):
            denied = client.patch(
                f"{tier}/scheduling/rooms/{room['room_id']}",
                headers=pj_headers,
                json=payload,
            )
            assert denied.status_code == 403, denied.text
            assert denied.json()["error"]["code"] == "forbidden"

    after = _by_id(client.get(PATH, headers=admin_headers).json(), room["room_id"])
    assert after == before


def test_non_pj_lecturer_cannot_write_rooms(client, db_session):
    headers = _non_coordinator_headers(client, db_session)

    created = client.post(
        PATH,
        headers=headers,
        json={"room_code": _code(), "building": "NANO", "capacity": 20},
    )
    assert created.status_code == 403, created.text
    assert created.json()["error"]["code"] == "forbidden"

