import random

import pytest

from catalog import get_course

PAYLOAD = {
    "course_name": "Mata Kuliah Uji",
    "program_name": "Teknologi Sains Data",
    "credits": 3,
    "recommended_semester": 5,
    "term": "ganjil",
    "course_type": "Pilihan",
    "description": "Data uji",
}


def _create_course(
    client, admin_headers, name=PAYLOAD["course_name"], prerequisites=None
) -> str:
    for _ in range(30):
        code = f"TST{random.randint(100, 999)}"
        payload = {**PAYLOAD, "course_code": code, "course_name": name}
        if prerequisites is not None:
            payload["prerequisites"] = prerequisites
        response = client.post(
            "/api/v1/admin/courses",
            headers=admin_headers,
            json=payload,
        )
        if response.status_code == 201:
            return code
        assert response.status_code == 409, response.text
    raise AssertionError("tidak mendapat kode mata kuliah unik untuk pengujian")


def _delete_course(client, admin_headers, code):
    client.delete(f"/api/v1/admin/courses/{code}", headers=admin_headers)


@pytest.fixture
def temp_course(client, admin_headers):
    code = _create_course(client, admin_headers)
    yield code
    client.delete(f"/api/v1/admin/courses/{code}", headers=admin_headers)


def test_admin_create_appears_in_catalog(client, admin_headers, temp_course):
    body = client.get("/api/v1/courses", params={"q": "Mata Kuliah Uji"}, headers=admin_headers).json()
    assert any(course["code"] == temp_course for course in body["courses"])


def test_admin_update_changes_catalog_entry(client, admin_headers, temp_course):
    response = client.put(
        f"/api/v1/admin/courses/{temp_course}",
        headers=admin_headers,
        json={"course_name": "Mata Kuliah Uji Diperbarui"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Mata Kuliah Uji Diperbarui"
    assert get_course(temp_course).name == "Mata Kuliah Uji Diperbarui"


def test_admin_delete_removes_from_catalog(client, admin_headers):
    code = _create_course(client, admin_headers, name="Mata Kuliah Hapus")
    assert get_course(code) is not None

    deleted = client.delete(f"/api/v1/admin/courses/{code}", headers=admin_headers)
    assert deleted.status_code == 200
    assert get_course(code) is None


def test_admin_write_requires_admin_role(client, student_headers):
    response = client.post(
        "/api/v1/admin/courses",
        headers=student_headers,
        json={
            "course_code": "TST000",
            "course_name": "Tidak Boleh",
            "program_name": "Teknologi Sains Data",
        },
    )
    assert response.status_code == 403


def test_admin_create_persists_prerequisites_read_via_detail(client, admin_headers):
    code = _create_course(client, admin_headers, prerequisites=["SID206"])
    try:
        response = client.get(f"/api/v1/courses/{code}", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["prerequisites"] == ["Pengantar Basis Data"]
    finally:
        _delete_course(client, admin_headers, code)


def test_admin_update_persists_prerequisites_and_refreshes_catalog(
    client, admin_headers
):
    code = _create_course(client, admin_headers, prerequisites=["SID206"])
    try:
        response = client.put(
            f"/api/v1/admin/courses/{code}",
            headers=admin_headers,
            json={
                "course_name": "Mata Kuliah Uji Revisi",
                "credits": 4,
                "prerequisites": ["SID205", "AGI101"],
            },
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Mata Kuliah Uji Revisi"

        detail = client.get(f"/api/v1/courses/{code}", headers=admin_headers).json()
        assert detail["credits"] == 4
        assert set(detail["prerequisites"]) == {
            "Eksplorasi dan Visualisasi Data",
            "Agama Islam 1",
        }

        listing = client.get(
            "/api/v1/courses", params={"q": "Mata Kuliah Uji Revisi"}, headers=admin_headers
        ).json()
        assert any(
            course["code"] == code and course["credits"] == 4
            for course in listing["courses"]
        )
    finally:
        _delete_course(client, admin_headers, code)


def test_admin_duplicate_code_returns_canonical_conflict(
    client, admin_headers, temp_course
):
    response = client.post(
        "/api/v1/admin/courses",
        headers=admin_headers,
        json={**PAYLOAD, "course_code": temp_course},
    )
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "duplicate_course_code"
    assert error["message"]


def test_admin_invalid_payload_returns_canonical_validation_error(
    client, admin_headers
):
    response = client.post(
        "/api/v1/admin/courses",
        headers=admin_headers,
        json={
            **PAYLOAD,
            "course_code": "TST901",
            "credits": 99,
            "recommended_semester": 0,
        },
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    fields = {item["field"] for item in body["error"]["details"]}
    assert "body.credits" in fields
    assert "body.recommended_semester" in fields
