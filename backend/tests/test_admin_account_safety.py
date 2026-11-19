"""Tes integrasi keamanan manajemen akun admin.

Semua tes memakai HTTP seam yang sama dengan klien produksi. Setiap tes dibungkus
transaksi `isolated_db` dari conftest yang di-rollback setelah tes, sehingga
akun, rencana, dan jejak wewenang yang dibuat di sini tidak pernah persisten.
Tidak ada pemanggilan fungsi internal untuk memvalidasi hasil: yang diperiksa
adalah status HTTP, envelope kanonik, dan state yang terbaca lewat API.
"""

import uuid

from sqlalchemy import text
from rate_limit import limiter
from tests.conftest import SEEDED_ADMIN

V1 = "/api/v1"
LEGACY = "/api"
REASON = "Koreksi keamanan akun FTMM Compass"


def _label() -> str:
    return uuid.uuid4().hex[:10]


def _nim() -> str:
    return f"17{uuid.uuid4().int % 10_000_000:07d}"


def _error(response):
    body = response.json()
    assert "error" in body, response.text
    return body["error"]


def _detail(response, key: str = "code"):
    details = _error(response)["details"]
    assert details, response.text
    return details[0][key]


def _create_staff(client, admin_headers, *, role="lecturer", password=None, email=None):
    email = email or f"uji.{_label()}@ftmm.unair.ac.id"
    payload = {
        "email": email,
        "full_name": f"Staf Uji {_label()}",
        "role": role,
    }
    if password is not None:
        payload["password"] = password
    response = client.post(f"{V1}/admin/accounts", headers=admin_headers, json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    return {
        "user_id": body["data"]["user_id"],
        "email": email,
        "password": password or body["temporary_password"],
    }


def _register_student(client, *, email=None, student_number=None, admission_year=2024):
    limiter.reset()
    email = email or f"mhs.{_label()}@ftmm.unair.ac.id"
    student_number = student_number or _nim()
    password = "MahasiswaUji2026!"
    response = client.post(
        f"{V1}/auth/register",
        json={
            "email": email,
            "full_name": "Mahasiswa Uji FTMM",
            "student_number": student_number,
            "admission_year": admission_year,
            "password": password,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return {
        "user_id": body["user"]["user_id"],
        "email": email,
        "student_number": student_number,
        "password": password,
        "headers": {"Authorization": f"Bearer {body['access_token']}"},
    }


def _login(client, email: str, password: str):
    limiter.reset()
    response = client.post(
        f"{V1}/auth/login", json={"identifier": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _current_user_id(client, headers: dict) -> str:
    response = client.get(f"{V1}/auth/me", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["user_id"]


def _find_account(client, admin_headers, search: str, user_id: str):
    response = client.get(
        f"{V1}/admin/accounts",
        headers=admin_headers,
        params={"search": search, "page": 1, "page_size": 100},
    )
    assert response.status_code == 200, response.text
    return next(
        (row for row in response.json()["data"] if row["user_id"] == user_id), None
    )


def _admin_profile(client, admin_headers, user_id: str) -> dict:
    response = client.get(
        f"{V1}/admin/accounts/{user_id}/profile", headers=admin_headers
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _query_one(client, db_session, sql: str, params: dict | None = None):
    async def run():
        result = await db_session.execute(text(sql), params or {})
        row = result.mappings().first()
        return dict(row) if row is not None else None

    return client.portal.call(run)


def _run_sql(client, db_session, sql: str, params: dict | None = None) -> None:
    async def run():
        await db_session.execute(text(sql), params or {})

    client.portal.call(run)


def _study_programs(client, db_session):
    async def run():
        rows = (
            await db_session.execute(
                text(
                    "SELECT study_program_id::text AS id, program_code "
                    "FROM study_programs WHERE is_active = true ORDER BY program_code"
                )
            )
        ).mappings().all()
        return [dict(row) for row in rows]

    return client.portal.call(run)


def _ensure_active_curriculum(client, db_session, program_id: str, year: int) -> str:
    row = _query_one(
        client,
        db_session,
        "SELECT curriculum_id::text AS id FROM curricula "
        "WHERE study_program_id = CAST(:pid AS uuid) AND is_active = true "
        "ORDER BY curriculum_year DESC LIMIT 1",
        {"pid": program_id},
    )
    if row is not None:
        return row["id"]
    row = _query_one(
        client,
        db_session,
        "SELECT curriculum_id::text AS id FROM curricula "
        "WHERE study_program_id = CAST(:pid AS uuid) AND curriculum_year = :year LIMIT 1",
        {"pid": program_id, "year": year},
    )
    if row is not None:
        _run_sql(
            client,
            db_session,
            "UPDATE curricula SET is_active = true WHERE curriculum_id = CAST(:cid AS uuid)",
            {"cid": row["id"]},
        )
        return row["id"]
    curriculum_id = str(uuid.uuid4())
    _run_sql(
        client,
        db_session,
        "INSERT INTO curricula (curriculum_id, study_program_id, curriculum_name, "
        "curriculum_year, is_active) VALUES (CAST(:cid AS uuid), CAST(:pid AS uuid), "
        ":name, :year, true)",
        {
            "cid": curriculum_id,
            "pid": program_id,
            "name": f"Kurikulum Uji {year}",
            "year": year,
        },
    )
    return curriculum_id


def _deactivate_other_admins(client, db_session) -> None:
    """Siapkan skenario admin aktif terakhir; dibatalkan bersama transaksi tes."""
    _run_sql(
        client,
        db_session,
        "UPDATE users SET is_active = false WHERE role = 'admin' AND email <> :email",
        {"email": SEEDED_ADMIN[0]},
    )


def _profile_payload(profile: dict, **overrides) -> dict:
    payload = {
        "study_program_id": profile["study_program_id"],
        "admission_year": profile["admission_year"],
        "student_number": profile["student_number"],
        "current_semester": profile["current_semester"],
        "reason": REASON,
    }
    payload.update(overrides)
    return payload


def _activate_plan(client, headers: dict, name: str) -> str:
    created = client.post(
        f"{V1}/degree-plans", headers=headers, json={"name": name, "items": []}
    )
    assert created.status_code == 201, created.text
    plan_id = created.json()["id"]
    activated = client.patch(
        f"{V1}/degree-plans/{plan_id}", headers=headers, json={"status": "active"}
    )
    assert activated.status_code == 200, activated.text
    assert activated.json()["status"] == "active"
    return plan_id


# ---------------------------------------------------------------------------
# 1. Status akun
# ---------------------------------------------------------------------------


def test_nonaktifkan_akun_menolak_alasan_kosong(client, admin_headers):
    staff = _create_staff(client, admin_headers)

    rejected = client.patch(
        f"{V1}/admin/accounts/{staff['user_id']}",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert rejected.status_code == 422
    assert _error(rejected)["code"] == "validation_error"
    assert _detail(rejected) == "required_reason"
    assert _find_account(client, admin_headers, staff["email"], staff["user_id"])[
        "is_active"
    ] is True

    accepted = client.patch(
        f"{V1}/admin/accounts/{staff['user_id']}",
        headers=admin_headers,
        json={"is_active": False, "reason": REASON},
    )
    assert accepted.status_code == 200
    assert accepted.json()["data"]["status"] == "inactive"


def test_admin_guard_menolak_nonaktifkan_akun_sendiri(client, admin_headers):
    # Admin lain masih aktif agar ini benar-benar kasus "akun sendiri".
    _create_staff(client, admin_headers, role="admin")
    own_id = _current_user_id(client, admin_headers)

    response = client.patch(
        f"{V1}/admin/accounts/{own_id}",
        headers=admin_headers,
        json={"is_active": False, "reason": REASON},
    )
    assert response.status_code == 409
    assert _error(response)["code"] == "admin_guard"
    assert _current_user_id(client, admin_headers) == own_id


def test_admin_guard_menolak_nonaktifkan_admin_aktif_terakhir(
    client, admin_headers, db_session
):
    _deactivate_other_admins(client, db_session)
    own_id = _current_user_id(client, admin_headers)

    response = client.patch(
        f"{V1}/admin/accounts/{own_id}",
        headers=admin_headers,
        json={"is_active": False, "reason": REASON},
    )
    assert response.status_code == 409
    assert _error(response)["code"] == "admin_guard"


def test_perubahan_status_menolak_pengguna_non_admin(
    client, student_headers, lecturer_headers
):
    target = str(uuid.uuid4())
    for headers in (student_headers, lecturer_headers):
        response = client.patch(
            f"{V1}/admin/accounts/{target}",
            headers=headers,
            json={"is_active": False, "reason": REASON},
        )
        assert response.status_code == 403
        assert _error(response)["code"] == "forbidden"


def test_status_change_mencabut_token_lama_setelah_reaktivasi(client, admin_headers):
    staff = _create_staff(client, admin_headers, password="StafUji2026!")
    old_headers = _login(client, staff["email"], staff["password"])
    assert client.get(f"{V1}/auth/me", headers=old_headers).status_code == 200

    deactivated = client.patch(
        f"{V1}/admin/accounts/{staff['user_id']}",
        headers=admin_headers,
        json={"is_active": False, "reason": REASON},
    )
    assert deactivated.status_code == 200
    reactivated = client.patch(
        f"{V1}/admin/accounts/{staff['user_id']}",
        headers=admin_headers,
        json={"is_active": True, "reason": REASON},
    )
    assert reactivated.status_code == 200

    assert client.get(f"{V1}/auth/me", headers=old_headers).status_code == 401
    new_headers = _login(client, staff["email"], staff["password"])
    assert client.get(f"{V1}/auth/me", headers=new_headers).status_code == 200


# ---------------------------------------------------------------------------
# 2. Jejak wewenang admin
# ---------------------------------------------------------------------------


def test_jejak_wewenang_admin_mencatat_perubahan_status(client, admin_headers):
    staff = _create_staff(client, admin_headers)
    actor_id = _current_user_id(client, admin_headers)

    changed = client.patch(
        f"{V1}/admin/accounts/{staff['user_id']}",
        headers=admin_headers,
        json={"is_active": False, "reason": REASON},
    )
    assert changed.status_code == 200

    response = client.get(
        f"{V1}/admin/authority-traces",
        headers=admin_headers,
        params={"page": 1, "page_size": 20},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["page"] == 1
    assert body["meta"]["page_size"] == 20
    entry = next(
        (
            row
            for row in body["data"]
            if row["target_user_id"] == staff["user_id"]
            and row["action"] == "status_change"
        ),
        None,
    )
    assert entry is not None
    assert entry["actor_user_id"] == actor_id
    assert SEEDED_ADMIN[0] in entry["actor_snapshot"]
    assert staff["email"] in entry["target_snapshot"]
    assert entry["field_name"] == "is_active"
    assert entry["old_value"].lower() == "true"
    assert entry["new_value"].lower() == "false"
    assert entry["reason"] == REASON
    assert entry["trace_id"]
    assert entry["created_at"]


def test_jejak_wewenang_admin_menolak_non_admin(
    client, student_headers, lecturer_headers
):
    for headers in (student_headers, lecturer_headers):
        response = client.get(f"{V1}/admin/authority-traces", headers=headers)
        assert response.status_code == 403
        assert _error(response)["code"] == "forbidden"


def test_jejak_wewenang_admin_mendukung_paginasi(client, admin_headers):
    for _ in range(2):
        staff = _create_staff(client, admin_headers)
        changed = client.patch(
            f"{V1}/admin/accounts/{staff['user_id']}",
            headers=admin_headers,
            json={"is_active": False, "reason": REASON},
        )
        assert changed.status_code == 200

    first = client.get(
        f"{V1}/admin/authority-traces",
        headers=admin_headers,
        params={"page": 1, "page_size": 1},
    )
    second = client.get(
        f"{V1}/admin/authority-traces",
        headers=admin_headers,
        params={"page": 2, "page_size": 1},
    )
    assert first.status_code == second.status_code == 200
    first_body, second_body = first.json(), second.json()
    assert first_body["meta"]["total"] >= 2
    assert first_body["meta"]["page"] == 1
    assert second_body["meta"]["page"] == 2
    assert first_body["meta"]["page_size"] == second_body["meta"]["page_size"] == 1
    assert len(first_body["data"]) == len(second_body["data"]) == 1
    assert (
        first_body["data"][0]["trace_id"] != second_body["data"][0]["trace_id"]
    )


# ---------------------------------------------------------------------------
# 3. Masuk (login)
# ---------------------------------------------------------------------------


def test_login_salah_kata_sandi_memakai_pesan_umum(client, admin_headers):
    staff = _create_staff(client, admin_headers, password="StafUji2026!")
    limiter.reset()
    wrong = client.post(
        f"{V1}/auth/login",
        json={"identifier": staff["email"], "password": "KataSandiSalah2026!"},
    )
    unknown = client.post(
        f"{V1}/auth/login",
        json={
            "identifier": f"tidak.ada.{_label()}@ftmm.unair.ac.id",
            "password": "KataSandiSalah2026!",
        },
    )
    assert wrong.status_code == unknown.status_code == 401
    assert _error(wrong)["code"] == _error(unknown)["code"] == "unauthorized"
    assert _error(wrong)["message"] == _error(unknown)["message"]


def test_login_akun_nonaktif_mengembalikan_account_inactive(client, admin_headers):
    password = "StafNonaktif2026!"
    staff = _create_staff(client, admin_headers, password=password)
    deactivated = client.patch(
        f"{V1}/admin/accounts/{staff['user_id']}",
        headers=admin_headers,
        json={"is_active": False, "reason": REASON},
    )
    assert deactivated.status_code == 200

    limiter.reset()
    response = client.post(
        f"{V1}/auth/login", json={"identifier": staff["email"], "password": password}
    )
    assert response.status_code == 401
    assert _error(response)["code"] == "account_inactive"
    assert _error(response)["message"] == "Akun Anda dinonaktifkan oleh admin"


# ---------------------------------------------------------------------------
# 4. Data identitas akademik terkunci
# ---------------------------------------------------------------------------


def test_koreksi_data_identitas_akademik_terkunci_menolak_field_tambahan(
    client, admin_headers
):
    student = _register_student(client)
    response = client.patch(
        f"{V1}/admin/accounts/{student['user_id']}/profile",
        headers=admin_headers,
        json={
            "study_program_id": str(uuid.uuid4()),
            "admission_year": 2024,
            "student_number": student["student_number"],
            "current_semester": 3,
            "reason": REASON,
            "role": "admin",
        },
    )
    assert response.status_code == 422
    assert _error(response)["code"] == "validation_error"
    details = _error(response)["details"]
    assert any("role" in detail["field"] for detail in details)


def test_profil_diri_menolak_field_akademik_tambahan(client, student_headers):
    before = client.get(f"{V1}/auth/me", headers=student_headers)
    assert before.status_code == 200

    response = client.patch(
        f"{V1}/auth/me/profile",
        headers=student_headers,
        json={"bio": "Perbaruan profil", "student_number": _nim()},
    )
    assert response.status_code == 422
    assert _error(response)["code"] == "validation_error"
    details = _error(response)["details"]
    assert any("student_number" in detail["field"] for detail in details)

    after = client.get(f"{V1}/auth/me", headers=student_headers)
    assert after.status_code == 200
    assert after.json()["student_profile"] == before.json()["student_profile"]


def test_koreksi_profil_nim_saja_menolak_alasan_kosong(client, admin_headers):
    student = _register_student(client)
    profile = _admin_profile(client, admin_headers, student["user_id"])

    response = client.patch(
        f"{V1}/admin/accounts/{student['user_id']}/profile",
        headers=admin_headers,
        json=_profile_payload(profile, student_number=_nim(), reason="   "),
    )
    assert response.status_code == 422
    assert _error(response)["code"] == "validation_error"
    assert _detail(response) == "reason_required"
    assert (
        _admin_profile(client, admin_headers, student["user_id"])["student_number"]
        == student["student_number"]
    )


def test_koreksi_profil_menolak_target_bukan_mahasiswa(client, admin_headers):
    staff = _create_staff(client, admin_headers)
    profile = {
        "study_program_id": str(uuid.uuid4()),
        "admission_year": 2024,
        "student_number": _nim(),
        "current_semester": 3,
        "reason": REASON,
    }
    response = client.patch(
        f"{V1}/admin/accounts/{staff['user_id']}/profile",
        headers=admin_headers,
        json=profile,
    )
    assert response.status_code == 422
    assert _error(response)["code"] == "validation_error"
    assert _detail(response) == "non_student_target"


def test_koreksi_profil_menolak_nim_duplikat(client, admin_headers):
    first = _register_student(client)
    second = _register_student(client)
    own_profile = _admin_profile(client, admin_headers, second["user_id"])

    response = client.patch(
        f"{V1}/admin/accounts/{second['user_id']}/profile",
        headers=admin_headers,
        json=_profile_payload(own_profile, student_number=first["student_number"]),
    )
    assert response.status_code == 422
    assert _error(response)["code"] == "validation_error"
    assert _detail(response) == "duplicate_student_number"
    assert (
        _admin_profile(client, admin_headers, second["user_id"])["student_number"]
        == second["student_number"]
    )


def test_koreksi_profil_program_angkatan_mengarsipkan_rencana_dan_menonaktifkan_jadwal(
    client, admin_headers, db_session, student_headers
):
    student_id = _current_user_id(client, student_headers)
    current = _admin_profile(client, admin_headers, student_id)
    options = _study_programs(client, db_session)
    target = next(
        (
            program
            for program in options
            if program["program_code"] != current["program_code"]
        ),
        None,
    )
    assert target is not None
    new_year = 2024
    _ensure_active_curriculum(client, db_session, target["id"], new_year)

    before = client.get(f"{V1}/dashboard/me", headers=student_headers)
    assert before.status_code == 200
    assert before.json()["schedule"], "seed mahasiswa harus punya jadwal aktif"
    plan_id = _activate_plan(client, student_headers, f"Uji {_label()}")

    response = client.patch(
        f"{V1}/admin/accounts/{student_id}/profile",
        headers=admin_headers,
        json=_profile_payload(
            current,
            study_program_id=target["id"],
            admission_year=new_year,
        ),
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["needs_revalidation"] is True

    me = client.get(f"{V1}/auth/me", headers=student_headers)
    assert me.status_code == 200
    assert me.json()["student_profile"]["program_code"] == target["program_code"]
    assert me.json()["student_profile"]["admission_year"] == new_year
    assert me.json()["needs_revalidation"] is True

    plans = client.get(f"{V1}/degree-plans", headers=student_headers)
    assert plans.status_code == 200
    archived = next(
        (row for row in plans.json()["data"] if row["id"] == plan_id), None
    )
    assert archived is not None
    assert archived["status"] == "archived"

    after = client.get(f"{V1}/dashboard/me", headers=student_headers)
    assert after.status_code == 200
    assert after.json()["schedule"] == []


def test_koreksi_profil_menolak_semester_melebihi_target_rencana(
    client, admin_headers, db_session
):
    student = _register_student(client)
    profile = _admin_profile(client, admin_headers, student["user_id"])
    plan_id = _activate_plan(client, student["headers"], f"Uji {_label()}")
    _run_sql(
        client,
        db_session,
        "UPDATE degree_plans SET target_graduation_semester = 7 "
        "WHERE degree_plan_id = CAST(:pid AS uuid)",
        {"pid": plan_id},
    )

    response = client.patch(
        f"{V1}/admin/accounts/{student['user_id']}/profile",
        headers=admin_headers,
        json=_profile_payload(profile, current_semester=9),
    )
    assert response.status_code == 422
    assert _error(response)["code"] == "validation_error"
    assert _detail(response) == "semester_exceeds_target"


# ---------------------------------------------------------------------------
# 5. Akun dianonimisasi
# ---------------------------------------------------------------------------


def test_anonimisasi_menolak_konfirmasi_salah(client, admin_headers):
    student = _register_student(client)

    response = client.post(
        f"{V1}/admin/accounts/{student['user_id']}/anonymize",
        headers=admin_headers,
        json={"confirmation": "bukan-nim", "reason": REASON},
    )
    assert response.status_code == 422
    assert _error(response)["code"] == "validation_error"
    assert _detail(response) == "confirmation_mismatch"
    assert (
        _find_account(client, admin_headers, student["email"], student["user_id"])
        is not None
    )


def test_anonimisasi_mahasiswa_tanpa_nim_menerima_konfirmasi_email(
    client, admin_headers, db_session
):
    student = _register_student(client)
    _run_sql(
        client,
        db_session,
        "UPDATE student_profiles SET student_number = NULL "
        "WHERE user_id = CAST(:uid AS uuid)",
        {"uid": student["user_id"]},
    )
    client.portal.call(db_session.expire_all)
    assert (
        _admin_profile(client, admin_headers, student["user_id"])["student_number"] is None
    )

    response = client.post(
        f"{V1}/admin/accounts/{student['user_id']}/anonymize",
        headers=admin_headers,
        json={"confirmation": student["email"], "reason": REASON},
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["email"].startswith("anon+")
    assert data["email"].endswith("@invalid.local")
    assert data["full_name"] == "Akun Anonim"
    assert data["student_number"] is None
    assert data["is_active"] is False
    assert client.get(f"{V1}/auth/me", headers=student["headers"]).status_code == 401


def test_anonimisasi_akun_mahasiswa_menjaga_baris_dan_jejak_wewenang(
    client, admin_headers
):
    student = _register_student(client)

    response = client.post(
        f"{V1}/admin/accounts/{student['user_id']}/anonymize",
        headers=admin_headers,
        json={"confirmation": student["student_number"], "reason": REASON},
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["email"].startswith("anon+")
    assert data["email"].endswith("@invalid.local")
    assert data["full_name"] == "Akun Anonim"
    assert data["student_number"] is None
    assert data["is_active"] is False
    assert data["anonymized_at"]
    assert client.get(f"{V1}/auth/me", headers=student["headers"]).status_code == 401

    kept = _find_account(client, admin_headers, "anon", student["user_id"])
    assert kept is not None
    assert kept["email"] == data["email"]
    assert kept["full_name"] == "Akun Anonim"
    assert kept["status"] == "inactive"

    traces = client.get(
        f"{V1}/admin/authority-traces",
        headers=admin_headers,
        params={"page": 1, "page_size": 100},
    )
    assert traces.status_code == 200
    entry = next(
        (
            row
            for row in traces.json()["data"]
            if row["target_user_id"] == student["user_id"]
            and row["action"] == "anonymize"
        ),
        None,
    )
    assert entry is not None
    assert student["email"] in entry["target_snapshot"]
    assert entry["reason"] == REASON


def test_anonimisasi_menolak_admin_aktif_terakhir(client, admin_headers, db_session):
    _deactivate_other_admins(client, db_session)
    admin_id = _current_user_id(client, admin_headers)

    response = client.post(
        f"{V1}/admin/accounts/{admin_id}/anonymize",
        headers=admin_headers,
        json={"confirmation": SEEDED_ADMIN[0], "reason": REASON},
    )
    assert response.status_code == 409
    assert _error(response)["code"] == "admin_guard"
    assert _current_user_id(client, admin_headers) == admin_id


def test_pendaftaran_ulang_email_akun_dianonimisasi_menghasilkan_user_id_baru(
    client, admin_headers
):
    student = _register_student(client)
    anonymized = client.post(
        f"{V1}/admin/accounts/{student['user_id']}/anonymize",
        headers=admin_headers,
        json={"confirmation": student["student_number"], "reason": REASON},
    )
    assert anonymized.status_code == 200

    again = _register_student(client, email=student["email"])
    assert again["user_id"] != student["user_id"]
    headers = _login(client, again["email"], again["password"])
    assert client.get(f"{V1}/auth/me", headers=headers).status_code == 200


# ---------------------------------------------------------------------------
# 6. Paritas kanonik/legacy
# ---------------------------------------------------------------------------


def test_paritas_tier_v1_dan_legacy_untuk_endpoint_baru(client, admin_headers):
    v1_traces = client.get(f"{V1}/admin/authority-traces", headers=admin_headers)
    legacy_traces = client.get(
        f"{LEGACY}/admin/authority-traces", headers=admin_headers
    )
    assert v1_traces.status_code == legacy_traces.status_code == 200
    assert v1_traces.json()["meta"]["page"] == legacy_traces.json()["meta"]["page"]

    staff_v1 = _create_staff(client, admin_headers)
    staff_legacy = _create_staff(client, admin_headers)
    changed_v1 = client.patch(
        f"{V1}/admin/accounts/{staff_v1['user_id']}",
        headers=admin_headers,
        json={"is_active": False, "reason": REASON},
    )
    changed_legacy = client.patch(
        f"{LEGACY}/admin/accounts/{staff_legacy['user_id']}",
        headers=admin_headers,
        json={"is_active": False, "reason": REASON},
    )
    assert changed_v1.status_code == changed_legacy.status_code == 200
    assert (
        changed_v1.json()["data"]["status"]
        == changed_legacy.json()["data"]["status"]
        == "inactive"
    )

    reset = client.post(
        f"{LEGACY}/admin/accounts/{staff_v1['user_id']}/reset-password",
        headers=admin_headers,
        json={"reason": REASON},
    )
    assert reset.status_code == 200
    assert reset.json()["temporary_password"]

    student = _register_student(client)
    profile = _admin_profile(client, admin_headers, student["user_id"])
    corrected = client.patch(
        f"{LEGACY}/admin/accounts/{student['user_id']}/profile",
        headers=admin_headers,
        json=_profile_payload(profile),
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["data"]["student_number"] == student["student_number"]

    lecturer = _create_staff(client, admin_headers)
    anonymized = client.post(
        f"{LEGACY}/admin/accounts/{lecturer['user_id']}/anonymize",
        headers=admin_headers,
        json={"confirmation": lecturer["email"], "reason": REASON},
    )
    assert anonymized.status_code == 200, anonymized.text
    assert anonymized.json()["data"]["full_name"] == "Akun Anonim"


def test_endpoint_akun_menolak_pengenal_tanpa_token(client):
    target = str(uuid.uuid4())
    assert client.get(f"{V1}/admin/authority-traces").status_code == 401
    assert (
        client.patch(
            f"{V1}/admin/accounts/{target}",
            json={"is_active": False, "reason": REASON},
        ).status_code
        == 401
    )
    assert (
        client.post(
            f"{V1}/admin/accounts/{target}/anonymize",
            json={"confirmation": "x", "reason": REASON},
        ).status_code
        == 401
    )
