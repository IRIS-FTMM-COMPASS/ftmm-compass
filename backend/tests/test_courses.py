"""Kontrak sumber katalog publik: database dengan fallback lokal."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from catalog import authoritative_curriculum_id, invalidate_catalog_cache
from models import Course, CurriculumCourse


@pytest.fixture(autouse=True)
def isolated_catalog_cache():
    invalidate_catalog_cache()
    yield
    invalidate_catalog_cache()


def _new_code() -> str:
    return f"UJI{int(uuid.uuid4().hex[:4], 16) % 10000:04d}"


def _add_course_row(
    client, db_session, *, course_is_active=None, cc_is_active=None, course_scope=None
):
    """Insert a course into the authoritative curriculum inside the test transaction."""

    async def insert():
        code = _new_code()
        course_fields = {"course_code": code, "course_name": f"MK Uji {code}"}
        if course_is_active is not None:
            course_fields["is_active"] = course_is_active
        course = Course(**course_fields)
        db_session.add(course)
        await db_session.flush()

        curriculum_id = await authoritative_curriculum_id(
            db_session, "Teknologi Sains Data"
        )
        assert curriculum_id is not None
        cc_fields = {
            "curriculum_id": curriculum_id,
            "course_id": course.course_id,
            "credits_total": 3,
            "recommended_semester": 7,
            "term": "ganjil",
            "course_type": "pilihan",
        }
        if cc_is_active is not None:
            cc_fields["is_active"] = cc_is_active
        if course_scope is not None:
            cc_fields["course_scope"] = course_scope
        db_session.add(CurriculumCourse(**cc_fields))
        await db_session.flush()
        return code

    return client.portal.call(insert)


def test_catalog_lists_all_programs(client):
    response = client.get("/api/v1/courses")
    assert response.status_code == 200
    body = response.json()
    assert body["total_courses"] >= 50
    assert len({course["program"] for course in body["courses"]}) == 5


def test_catalog_reports_database_source(client):
    response = client.get(
        "/api/v1/courses",
        params={"prodi": "Teknologi Sains Data", "page": 1, "per_page": 5},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "database"
    assert {"data", "meta", "links", "program_studi"} <= set(body)


def test_catalog_falls_back_to_local_source(client):
    with patch("catalog.build_catalog_from_db", new_callable=AsyncMock) as builder:
        builder.side_effect = RuntimeError("database unavailable")
        response = client.get("/api/v1/courses", params={"page": 1, "per_page": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "local_fallback"
    assert {"data", "meta", "links", "program_studi"} <= set(body)
    assert body["meta"]["total"] > 0


def test_public_catalog_excludes_demo_only_codes(client):
    response = client.get("/api/v1/courses")
    assert response.status_code == 200
    codes = {course["code"] for course in response.json()["courses"]}
    assert "KIK101" not in codes


def test_course_detail_returns_canonical_course(client):
    response = client.get("/api/v1/courses/AGI101")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "AGI101"
    assert body["name"]
    assert isinstance(body["prerequisites"], list)


def test_course_detail_legacy_alias_matches_canonical(client):
    response = client.get("/api/courses/AGI101")
    assert response.status_code == 200
    assert response.json()["code"] == "AGI101"


def test_course_detail_unknown_code_returns_canonical_not_found(client):
    response = client.get("/api/v1/courses/ZZZ999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "course_not_found"


def test_catalog_out_of_range_parameter_returns_canonical_validation_error(client):
    response = client.get("/api/v1/courses", params={"per_page": 0})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert any(item["field"] == "query.per_page" for item in body["error"]["details"])


def test_catalog_filters_by_program(client):
    response = client.get(
        "/api/v1/courses", params={"prodi": "Teknologi Sains Data"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_courses"] > 0
    assert {course["program"] for course in body["courses"]} == {
        "Teknologi Sains Data"
    }


def test_catalog_pagination_meta(client):
    response = client.get(
        "/api/v1/courses", params={"page": 2, "per_page": 5}
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) <= 5
    assert body["meta"]["page"] == 2
    assert body["meta"]["per_page"] == 5


def test_course_search_matches_code(client):
    response = client.get("/api/v1/courses/search", params={"q": "AGI101"})
    assert response.status_code == 200
    body = response.json()
    assert body["total_hits"] >= 1
    assert any("AGI101" in (item.get("code") or "") for item in body["results"])


def test_legacy_courses_alias(client):
    assert client.get("/api/courses").status_code == 200
    assert client.get("/api/courses/search", params={"q": "kalkulus"}).status_code == 200


def test_pj_deactivated_course_stays_visible_with_status_and_scope(client, db_session):
    code = _add_course_row(
        client, db_session, course_is_active=True, cc_is_active=False,
        course_scope="fakultas",
    )

    response = client.get("/api/v1/courses")
    assert response.status_code == 200
    course = next(
        (item for item in response.json()["courses"] if item["code"] == code), None
    )
    assert course is not None
    assert course["is_active"] is False
    assert course["course_scope"] == "fakultas"

    detail = client.get(f"/api/v1/courses/{code}")
    assert detail.status_code == 200
    assert detail.json()["is_active"] is False
    assert detail.json()["course_scope"] == "fakultas"


def test_globally_deactivated_course_is_hidden(client, db_session):
    code = _add_course_row(
        client, db_session, course_is_active=False, cc_is_active=True,
        course_scope="fakultas",
    )

    response = client.get("/api/v1/courses")
    assert response.status_code == 200
    assert code not in {item["code"] for item in response.json()["courses"]}


def test_catalog_rows_use_default_status_and_scope(client, db_session):
    code = _add_course_row(client, db_session)

    response = client.get("/api/v1/courses")
    assert response.status_code == 200
    course = next(
        (item for item in response.json()["courses"] if item["code"] == code), None
    )
    assert course is not None
    assert course["is_active"] is True
    assert course["course_scope"] == "program_studi"
