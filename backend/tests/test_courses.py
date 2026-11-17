"""Kontrak sumber katalog publik: database dengan fallback lokal."""

from unittest.mock import AsyncMock, patch

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
