import random


VALID_PLAN = {
    "1": [
        {
            "name": "Matematika I",
            "code": "MA1101",
            "credits": 4,
            "semester": 1,
            "type": "Wajib",
            "parity": "odd",
        }
    ]
}

PARITY_VIOLATION = {
    "2": [
        {
            "name": "Matematika I",
            "code": "MA1101",
            "credits": 4,
            "semester": 2,
            "type": "Wajib",
            "parity": "odd",
        }
    ]
}


def _validate(client, plan, **extra):
    payload = {
        "program_studi": "Teknologi Sains Data",
        "semester_saat_ini": 1,
        "plan": {int(key): value for key, value in plan.items()},
        "riwayat_matkul_lulus": [],
        "maks_sks_per_semester": 24,
        **extra,
    }
    return client.post("/api/v1/plans/validations", json=payload)


def _create_course_with_database_prerequisite(client, admin_headers):
    for _ in range(30):
        code = f"VAL{random.randint(100, 999)}"
        response = client.post(
            "/api/v1/admin/courses",
            headers=admin_headers,
            json={
                "course_code": code,
                "course_name": f"Mata Kuliah Validasi {code}",
                "program_name": "Teknologi Sains Data",
                "credits": 3,
                "recommended_semester": 5,
                "term": "ganjil",
                "course_type": "Pilihan",
                "prerequisites": ["SID206"],
            },
        )
        if response.status_code == 201:
            return response.json()
        assert response.status_code == 409, response.text
    raise AssertionError("tidak mendapat kode mata kuliah unik untuk pengujian")


def test_validate_rejects_database_prerequisite_when_client_sends_empty_array(
    client, admin_headers
):
    created = _create_course_with_database_prerequisite(client, admin_headers)
    try:
        assert created["prerequisites"] == ["Pengantar Basis Data"]
        plan = {
            "1": [
                {
                    "id": created["id"],
                    "code": created["code"],
                    "name": created["name"],
                    "credits": 3,
                    "semester": 1,
                    "type": "Pilihan",
                    "parity": "odd",
                    "prerequisites": [],
                }
            ]
        }
        response = _validate(client, plan)
        assert response.status_code == 200
        body = response.json()
        assert body["is_valid"] is False
        assert any(
            "Prasyarat tidak terpenuhi" in error
            and "Pengantar Basis Data" in error
            for error in body["errors"]
        )
    finally:
        client.delete(
            f"/api/v1/admin/courses/{created['code']}", headers=admin_headers
        )


def test_validate_uses_database_prerequisites_instead_of_client_array(client):
    plan = {
        "1": [{**VALID_PLAN["1"][0], "prerequisites": ["Mata Kuliah Fiktif"]}]
    }
    response = _validate(client, plan)
    assert response.status_code == 200
    assert response.json()["is_valid"] is True


def test_validate_ignores_non_course_requirement_labels(client):
    plan = {
        "7": [
            {
                "name": "Kuliah Kerja Nyata",
                "code": "KNJ401",
                "credits": 3,
                "semester": 7,
                "type": "Wajib",
                "parity": "odd",
                "prerequisites": [],
            }
        ]
    }
    response = _validate(client, plan)
    assert response.status_code == 200
    assert response.json()["is_valid"] is True


def test_validate_accepts_consistent_plan(client, student_headers):
    response = _validate(client, VALID_PLAN)
    assert response.status_code == 200
    assert response.json()["is_valid"] is True


def test_validate_rejects_parity_violation(client):
    response = _validate(client, PARITY_VIOLATION)
    assert response.status_code == 200
    body = response.json()
    assert body["is_valid"] is False
    assert body["errors"]


def test_validate_rejects_sks_overload(client):
    plan = {
        "1": [
            {
                "name": f"Mata Kuliah {index}",
                "code": f"MK{index}",
                "credits": 8,
                "semester": 1,
                "type": "Wajib",
                "parity": "odd",
            }
            for index in range(4)
        ]
    }
    response = _validate(client, plan)
    assert response.status_code == 200
    assert response.json()["is_valid"] is False


def test_generate_plan_returns_degree_plan(client):
    response = client.post(
        "/api/v1/plans",
        json={
            "program_studi": "Teknologi Sains Data",
            "semester_saat_ini": 3,
            "target_kelulusan_semester": 8,
            "maks_sks_per_semester": 24,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "APPLY_DEGREE_PLAN"
    assert body["summary"]["total_credits"] > 0
    assert body["plan"]


def test_legacy_plan_aliases(client):
    assert client.post("/api/plan/validate", json={
        "program_studi": "Teknologi Sains Data",
        "semester_saat_ini": 1,
        "plan": VALID_PLAN,
        "riwayat_matkul_lulus": [],
        "maks_sks_per_semester": 24,
    }).status_code == 200
    assert client.post("/api/plan/generate", json={
        "program_studi": "Teknologi Sains Data",
        "semester_saat_ini": 3,
        "target_kelulusan_semester": 8,
    }).status_code == 200
