import uuid
from datetime import datetime, timezone

import jwt
from sqlalchemy import or_, select

from auth import get_password_hash
from models import LecturerProfile, StudyProgram, User
from rate_limit import limiter
from tests.conftest import SEEDED_STUDENT

_LECTURER_PASSWORD = "DosenUji2026!"


def _create_study_program(client, db_session):
    """Buat prodi baru di transaksi uji; semua prodi seed sudah punya PJ."""
    async def insert():
        while True:
            suffix = uuid.uuid4().hex[:10].upper()
            program_code = f"UJI{suffix}"
            program_name = f"Program Uji {suffix}"
            taken = (
                await db_session.execute(
                    select(StudyProgram).where(
                        or_(
                            StudyProgram.program_code == program_code,
                            StudyProgram.program_name == program_name,
                        )
                    )
                )
            ).scalars().first()
            if taken is None:
                break
        program = StudyProgram(
            program_code=program_code,
            program_name=program_name,
            degree_level="sarjana",
            is_active=True,
        )
        db_session.add(program)
        await db_session.flush()
        return program.program_code, program.program_name

    return client.portal.call(insert)


def _create_lecturer(
    client,
    db_session,
    email: str,
    *,
    program_code: str | None = None,
    employee_number: str | None = None,
    is_program_coordinator: bool = False,
) -> None:
    async def insert():
        user = User(
            email=email,
            full_name="Dosen Uji Identitas",
            password_hash=get_password_hash(_LECTURER_PASSWORD),
            role="lecturer",
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()
        if program_code is not None:
            program = (
                await db_session.execute(
                    select(StudyProgram).where(StudyProgram.program_code == program_code)
                )
            ).scalars().one()
            db_session.add(
                LecturerProfile(
                    user_id=user.user_id,
                    study_program_id=program.study_program_id,
                    employee_number=employee_number,
                    is_program_coordinator=is_program_coordinator,
                )
            )
        await db_session.commit()
        return str(user.user_id)

    return client.portal.call(insert)


def _login_lecturer(client, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": _LECTURER_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_me_lecturer_identity_comes_from_profile(client, db_session):
    limiter.reset()
    program_code, program_name = _create_study_program(client, db_session)
    email = "dosen.profil@ftmm.unair.ac.id"
    employee_number = "198803152015049999"
    _create_lecturer(
        client,
        db_session,
        email,
        program_code=program_code,
        employee_number=employee_number,
        is_program_coordinator=True,
    )

    login = _login_lecturer(client, email)
    assert login["user"]["unit_name"] == program_name
    assert login["user"]["academic_identifier"] == employee_number
    assert login["user"]["is_program_coordinator"] is True

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login['access_token']}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["unit_name"] == program_name
    assert body["academic_identifier"] == employee_number
    assert body["is_program_coordinator"] is True
    assert body["student_profile"] is None


def test_me_lecturer_without_profile_has_no_fabricated_unit(client, db_session):
    limiter.reset()
    email = "dosen.tanpa.profil@ftmm.unair.ac.id"
    _create_lecturer(client, db_session, email)

    login = _login_lecturer(client, email)
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login['access_token']}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["unit_name"] in (None, "")
    assert body["academic_identifier"] in (None, "")
    assert body["is_program_coordinator"] is False


def test_update_profile_lecturer_keeps_profile_identity(client, db_session):
    limiter.reset()
    program_code, program_name = _create_study_program(client, db_session)
    email = "dosen.profil.update@ftmm.unair.ac.id"
    employee_number = "198803152015048888"
    _create_lecturer(
        client,
        db_session,
        email,
        program_code=program_code,
        employee_number=employee_number,
        is_program_coordinator=True,
    )

    login = _login_lecturer(client, email)
    response = client.patch(
        "/api/v1/auth/me/profile",
        headers={"Authorization": f"Bearer {login['access_token']}"},
        json={"bio": "Dosen uji profil"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["bio"] == "Dosen uji profil"
    assert body["unit_name"] == program_name
    assert body["academic_identifier"] == employee_number
    assert body["is_program_coordinator"] is True


def test_me_non_lecturer_identity_is_unchanged(client, student_headers, admin_headers):
    student = client.get("/api/v1/auth/me", headers=student_headers)
    assert student.status_code == 200
    body = student.json()
    assert body["role"] == "student"
    assert body["academic_identifier"] == body["student_profile"]["student_number"]
    assert body["student_profile"]["study_program"]
    assert body["is_program_coordinator"] is False

    admin = client.get("/api/v1/auth/me", headers=admin_headers)
    assert admin.status_code == 200
    body = admin.json()
    assert body["role"] == "admin"
    assert body["unit_name"] == "Sub-Bagian Akademik & Kemahasiswaan FTMM"
    assert body["academic_identifier"] == "198504122010121003"
    assert body["is_program_coordinator"] is False


def test_login_rejects_wrong_password(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"identifier": SEEDED_STUDENT[0], "password": "salah"},
    )
    assert response.status_code == 401
    assert "error" in response.json()


def test_login_returns_token_and_user(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"identifier": SEEDED_STUDENT[0], "password": SEEDED_STUDENT[1]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["user"]["role"] == "student"
    assert body["user"]["student_profile"]["student_number"]
    assert body["expires_in"] == 28800


def test_me_requires_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_returns_current_user(client, student_headers):
    response = client.get("/api/v1/auth/me", headers=student_headers)
    assert response.status_code == 200
    assert response.json()["email"] == SEEDED_STUDENT[0]


def test_legacy_me_alias(client, student_headers):
    assert client.get("/api/auth/me", headers=student_headers).status_code == 200


def test_profile_update_roundtrip(client, student_headers):
    response = client.patch(
        "/api/v1/auth/me/profile",
        headers=student_headers,
        json={"bio": "Fokus rekayasa data"},
    )
    assert response.status_code == 200
    assert response.json()["bio"] == "Fokus rekayasa data"

    restored = client.patch(
        "/api/v1/auth/me/profile",
        headers=student_headers,
        json={"bio": ""},
    )
    assert restored.status_code == 200


def _registration_payload(index: int = 1) -> dict:
    return {
        "email": f"mhs.baru{index}@ftmm.unair.ac.id",
        "full_name": "Mahasiswa Baru",
        "student_number": f"1642990{index:02d}",
        "admission_year": 2026,
        "password": "MahasiswaBaru2026!",
    }


def test_register_creates_account_profile_and_session(client):
    limiter.reset()
    response = client.post("/api/v1/auth/register", json=_registration_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["recovery_code"].startswith("FTMM-")
    assert body["user"]["role"] == "student"
    profile = body["user"]["student_profile"]
    assert profile["student_number"] == "164299001"
    assert 1 <= profile["current_semester"] <= 14

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me.status_code == 200


def test_register_legacy_alias(client):
    limiter.reset()
    response = client.post("/api/auth/register", json=_registration_payload(2))
    assert response.status_code == 201
    assert client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {response.json()['access_token']}"},
    ).status_code == 200


def test_register_rejects_bad_domain_with_field_detail(client):
    limiter.reset()
    payload = _registration_payload(3)
    payload["email"] = "mahasiswa@gmail.com"
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422
    detail = response.json()["error"]["details"][0]
    assert detail["field"] == "email"


def test_register_rejects_out_of_range_year_with_field_detail(client):
    limiter.reset()
    payload = _registration_payload(4)
    payload["admission_year"] = 1990
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422
    detail = response.json()["error"]["details"][0]
    assert detail["field"] == "admission_year"


def test_register_rejects_duplicate_email_and_nim(client):
    limiter.reset()
    duplicate_email = _registration_payload(5)
    duplicate_email["email"] = SEEDED_STUDENT[0]
    email_response = client.post("/api/v1/auth/register", json=duplicate_email)
    assert email_response.status_code == 422
    assert email_response.json()["error"]["details"][0]["field"] == "email"

    duplicate_nim = _registration_payload(6)
    duplicate_nim["student_number"] = "164231001"
    nim_response = client.post("/api/v1/auth/register", json=duplicate_nim)
    assert nim_response.status_code == 422
    assert nim_response.json()["error"]["details"][0]["field"] == "student_number"


def test_recover_rotates_code_and_revokes_previous_session(client):
    limiter.reset()
    registered = client.post("/api/v1/auth/register", json=_registration_payload(7))
    assert registered.status_code == 201
    registered_body = registered.json()
    old_headers = {
        "Authorization": f"Bearer {registered_body['access_token']}"
    }

    response = client.post(
        "/api/v1/auth/recover",
        json={
            "recovery_code": registered_body["recovery_code"],
            "new_password": "PemulihanAman2026!",
        },
    )
    assert response.status_code == 200
    assert response.json()["recovery_code"] != registered_body["recovery_code"]
    assert client.get("/api/v1/auth/me", headers=old_headers).status_code == 401

    assert client.post(
        "/api/v1/auth/login",
        json={"identifier": _registration_payload(7)["email"], "password": "MahasiswaBaru2026!"},
    ).status_code == 401
    new_login = client.post(
        "/api/v1/auth/login",
        json={
            "identifier": _registration_payload(7)["email"],
            "password": "PemulihanAman2026!",
        },
    )
    assert new_login.status_code == 200
    limiter.reset()


def test_recover_rejects_wrong_code_without_mutation(client):
    limiter.reset()
    registered = client.post("/api/v1/auth/register", json=_registration_payload(8))
    assert registered.status_code == 201
    payload = {
        "recovery_code": "FTMM-ZZZZ-ZZZZ-ZZZZ",
        "new_password": "PemulihanSalah2026!",
    }
    response = client.post("/api/v1/auth/recover", json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_recovery_code"

    still_valid = client.post(
        "/api/v1/auth/login",
        json={
            "identifier": _registration_payload(8)["email"],
            "password": "MahasiswaBaru2026!",
        },
    )
    assert still_valid.status_code == 200
    limiter.reset()


def test_change_password_revokes_old_token_and_keeps_new_session(client, student_headers):
    response = client.post(
        "/api/v1/auth/change-password",
        headers=student_headers,
        json={
            "current_password": SEEDED_STUDENT[1],
            "new_password": "KataSandiBaru2026!",
        },
    )
    assert response.status_code == 200
    new_headers = {
        "Authorization": f"Bearer {response.json()['access_token']}"
    }
    assert client.get("/api/v1/auth/me", headers=new_headers).status_code == 200
    assert client.get("/api/v1/auth/me", headers=student_headers).status_code == 401


def test_change_password_rejects_wrong_current_password(client, student_headers):
    response = client.post(
        "/api/v1/auth/change-password",
        headers=student_headers,
        json={
            "current_password": "bukan-kata-sandi",
            "new_password": "KataSandiBaru2026!",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_current_password"


def test_admin_account_list_search_filter_and_pagination(client, admin_headers):
    response = client.get(
        "/api/v1/admin/accounts?search=mahasiswa&role=student&status=active"
        "&page=1&page_size=5",
        headers=admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["page"] == 1
    assert body["meta"]["page_size"] == 5
    assert body["meta"]["total"] >= 1
    assert all(item["role"] == "student" for item in body["data"])
    assert all(item["status"] == "active" for item in body["data"])


def test_admin_update_and_reset_account(client, admin_headers, db_session):
    user_id = _create_lecturer(client, db_session, "staf.baru@ftmm.unair.ac.id")
    listed = client.get(
        "/api/v1/admin/accounts",
        params={"search": "staf.baru@ftmm.unair.ac.id"},
        headers=admin_headers,
    )
    assert listed.status_code == 200
    assert any(
        item["user_id"] == user_id and item["role"] == "lecturer"
        for item in listed.json()["data"]
    )

    deactivated = client.patch(
        f"/api/v1/admin/accounts/{user_id}",
        headers=admin_headers,
        json={"is_active": False, "reason": "QA kontrak status akun"},
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["data"]["status"] == "inactive"

    reactivated = client.patch(
        f"/api/v1/admin/accounts/{user_id}",
        headers=admin_headers,
        json={"is_active": True},
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["data"]["is_active"] is True

    reset = client.post(
        f"/api/v1/admin/accounts/{user_id}/reset-password",
        headers=admin_headers,
    )
    assert reset.status_code == 200
    assert reset.json()["temporary_password"]


def test_admin_reset_password_revokes_target_session(
    client, admin_headers, db_session
):
    limiter.reset()
    email = "staf.reset@ftmm.unair.ac.id"
    user_id = _create_lecturer(client, db_session, email)

    login = client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": _LECTURER_PASSWORD},
    )
    assert login.status_code == 200, login.text
    old_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    reset = client.post(
        f"/api/v1/admin/accounts/{user_id}/reset-password",
        headers=admin_headers,
    )
    assert reset.status_code == 200
    assert client.get("/api/v1/auth/me", headers=old_headers).status_code == 401

    new_login = client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": reset.json()["temporary_password"]},
    )
    assert new_login.status_code == 200
    limiter.reset()


def test_admin_account_create_endpoint_removed(client, admin_headers):
    payload = {
        "email": "staf.dihapus@ftmm.unair.ac.id",
        "full_name": "Staf Dihapus",
        "role": "lecturer",
    }
    for path in ("/api/v1/admin/accounts", "/api/admin/accounts"):
        response = client.post(path, headers=admin_headers, json=payload)
        assert response.status_code == 404, response.text
        body = response.json()
        assert body["error"]["code"] == "not_found"
        assert isinstance(body["error"]["message"], str)
        assert "details" in body["error"]


def test_admin_account_endpoints_reject_non_admin(
    client, student_headers, lecturer_headers
):
    unknown_id = str(uuid.uuid4())
    for headers in (student_headers, lecturer_headers):
        assert client.get("/api/v1/admin/accounts", headers=headers).status_code == 403
        removed = client.post(
            "/api/v1/admin/accounts",
            headers=headers,
            json={
                "email": "tidak.boleh@ftmm.unair.ac.id",
                "full_name": "Staf Tanpa Izin",
                "role": "lecturer",
            },
        )
        assert removed.status_code == 404
        assert client.patch(
            f"/api/v1/admin/accounts/{unknown_id}",
            headers=headers,
            json={"is_active": False},
        ).status_code == 403
        assert client.post(
            f"/api/v1/admin/accounts/{unknown_id}/reset-password",
            headers=headers,
        ).status_code == 403

    forbidden = client.get("/api/v1/admin/accounts", headers=student_headers)
    assert forbidden.json()["error"]["code"] == "forbidden"


def test_login_rate_limit_returns_rate_limited_envelope(client):
    limiter.reset()
    payload = {"identifier": SEEDED_STUDENT[0], "password": "salah"}
    responses = [
        client.post("/api/v1/auth/login", json=payload) for _ in range(6)
    ]
    assert [item.status_code for item in responses] == [401] * 5 + [429]
    limited = responses[-1]
    body = limited.json()
    assert body["error"]["code"] == "rate_limited"
    assert body["error"]["retry_after"] == int(limited.headers["Retry-After"])
    assert body["retry_after"] == int(limited.headers["Retry-After"])
    limiter.reset()


def test_register_rate_limit_returns_rate_limited_envelope(client):
    limiter.reset()
    responses = []
    for index in range(10, 14):
        responses.append(
            client.post("/api/v1/auth/register", json=_registration_payload(index))
        )
    assert [item.status_code for item in responses] == [201] * 3 + [429]
    limited = responses[-1]
    assert limited.json()["error"]["code"] == "rate_limited"
    assert limited.json()["error"]["retry_after"] == int(
        limited.headers["Retry-After"]
    )
    limiter.reset()


def test_recover_rate_limit_returns_rate_limited_envelope(client):
    limiter.reset()
    payload = {
        "recovery_code": "FTMM-ZZZZ-ZZZZ-ZZZZ",
        "new_password": "PemulihanSalah2026!",
    }
    responses = [client.post("/api/v1/auth/recover", json=payload) for _ in range(4)]
    assert [item.status_code for item in responses] == [400] * 3 + [429]
    assert responses[-1].json()["error"]["code"] == "rate_limited"
    assert int(responses[-1].headers["Retry-After"]) > 0
    limiter.reset()


def test_non_auth_endpoints_are_not_rate_limited_by_auth_decorators(client):
    limiter.reset()
    statuses = [client.get("/api/v1/health").status_code for _ in range(8)]
    assert statuses == [200] * 8
    limiter.reset()


def test_login_accepts_uppercase_email(client):
    limiter.reset()
    payload = _registration_payload(21)
    registered = client.post("/api/v1/auth/register", json=payload)
    assert registered.status_code == 201

    response = client.post(
        "/api/v1/auth/login",
        json={"identifier": payload["email"].upper(), "password": payload["password"]},
    )
    assert response.status_code == 200
    limiter.reset()


def test_register_rejects_short_password(client):
    limiter.reset()
    payload = _registration_payload(22)
    payload["password"] = "pendek"
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    limiter.reset()


def test_recover_rejects_short_new_password(client):
    limiter.reset()
    response = client.post(
        "/api/v1/auth/recover",
        json={"recovery_code": "FTMM-ZZZZ-ZZZZ-ZZZZ", "new_password": "pendek"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    limiter.reset()


def test_change_password_rejects_short_new_password(client, student_headers):
    response = client.post(
        "/api/v1/auth/change-password",
        headers=student_headers,
        json={"current_password": "salah", "new_password": "pendek"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_login_token_lifetime_matches_expires_in(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"identifier": SEEDED_STUDENT[0], "password": SEEDED_STUDENT[1]},
    )
    assert response.status_code == 200
    body = response.json()
    claims = jwt.decode(body["access_token"], options={"verify_signature": False})
    remaining = claims["exp"] - datetime.now(timezone.utc).timestamp()
    assert body["expires_in"] == 28800
    assert 28790 <= remaining <= 28800
