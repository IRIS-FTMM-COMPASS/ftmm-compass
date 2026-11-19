from sqlalchemy import select

from database import engine
from models import AcademicPeriod

PATH = "/api/v1/class-sections"


def _period_ids(client):
    async def read():
        async with engine.connect() as connection:
            rows = (
                await connection.execute(
                    select(AcademicPeriod.academic_period_id, AcademicPeriod.is_active)
                )
            ).all()
        active = next((row for row in rows if row.is_active), None)
        inactive = next((row for row in rows if not row.is_active), None)
        return str(active.academic_period_id), str(inactive.academic_period_id)

    return client.portal.call(read)


def test_sections_for_active_period(client, student_headers):
    response = client.get(
        PATH, params={"course_code": "TSD201"}, headers=student_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == len(body["data"])

    section = next((s for s in body["data"] if s["section_code"] == "A"), None)
    assert section is not None
    assert section["section_id"]
    assert section["schedules"]
    meeting = section["schedules"][0]
    assert meeting["day_of_week"] == 1
    assert meeting["day"] == "Senin"
    assert meeting["start_time"] == "08:00"
    assert meeting["end_time"] == "10:30"
    assert "Lab Komputasi A" in meeting["room"]


def test_legacy_alias_returns_same_collection(client, student_headers):
    response = client.get(
        "/api/class-sections", params={"course_code": "TSD201"}, headers=student_headers
    )

    assert response.status_code == 200
    assert response.json()["data"]


def test_unknown_course_returns_course_not_found(client, student_headers):
    response = client.get(
        PATH, params={"course_code": "XXX999"}, headers=student_headers
    )

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "course_not_found"
    assert error["message"]


def test_course_without_sections_returns_empty_collection(client, student_headers):
    response = client.get(
        PATH, params={"course_code": "KID101"}, headers=student_headers
    )

    assert response.status_code == 200
    assert response.json()["data"] == []
    assert response.json()["meta"]["total"] == 0


def test_invalid_parameters_use_validation_envelope(client, student_headers):
    invalid = (
        {},
        {"course_code": ""},
        {"course_code": "TSD201", "academic_period_id": "bukan-uuid"},
    )

    for params in invalid:
        response = client.get(PATH, params=params, headers=student_headers)
        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "validation_error"
        assert error["details"]


def test_sections_follow_requested_period(client, student_headers):
    active_id, inactive_id = _period_ids(client)

    active = client.get(
        PATH,
        params={"course_code": "TSD201", "academic_period_id": active_id},
        headers=student_headers,
    )
    inactive = client.get(
        PATH,
        params={"course_code": "TSD201", "academic_period_id": inactive_id},
        headers=student_headers,
    )

    assert active.status_code == 200
    assert active.json()["data"]
    assert inactive.status_code == 200
    assert inactive.json()["data"] == []
