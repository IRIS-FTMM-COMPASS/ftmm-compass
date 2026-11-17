"""Regresi cache katalog: cache hit, invalidasi admin, dan fallback lokal."""

import random

import pytest

import catalog
from catalog import invalidate_catalog_cache

CREATE_PAYLOAD = {
    "program_name": "Teknologi Sains Data",
    "credits": 3,
    "recommended_semester": 5,
    "term": "ganjil",
    "course_type": "Pilihan",
    "description": "Data uji cache katalog",
    "prerequisites": [],
}


@pytest.fixture(autouse=True)
def isolated_catalog_cache():
    invalidate_catalog_cache()
    yield
    invalidate_catalog_cache()


def _unique_code() -> str:
    return f"CC{random.randint(1000, 9999)}"


def _count_builder(monkeypatch, counter: dict) -> None:
    original = catalog.build_catalog_from_db

    async def counted(db):
        counter["calls"] += 1
        return await original(db)

    monkeypatch.setattr(catalog, "build_catalog_from_db", counted)


def test_identical_filtered_requests_hit_cache(client, monkeypatch):
    counter = {"calls": 0}
    _count_builder(monkeypatch, counter)
    params = {
        "prodi": "Teknologi Sains Data",
        "semester": 5,
        "page": 1,
        "per_page": 5,
    }

    first = client.get("/api/v1/courses", params=params)
    second = client.get("/api/v1/courses", params=params)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.content == first.content
    assert second.json()["source"] == "database"
    assert counter["calls"] == 1


def test_distinct_filter_uses_distinct_cache_entry(client, monkeypatch):
    counter = {"calls": 0}
    _count_builder(monkeypatch, counter)

    first = client.get("/api/v1/courses", params={"page": 1, "per_page": 5})
    second = client.get("/api/v1/courses", params={"page": 2, "per_page": 5})

    assert first.status_code == 200
    assert second.status_code == 200
    assert counter["calls"] == 2


def test_admin_create_invalidates_catalog_cache(client, admin_headers, monkeypatch):
    counter = {"calls": 0}
    _count_builder(monkeypatch, counter)
    code = _unique_code()
    params = {"q": code}

    before = client.get("/api/v1/courses", params=params)
    assert before.status_code == 200
    assert before.json()["courses"] == []
    assert counter["calls"] == 1

    created = client.post(
        "/api/v1/admin/courses",
        headers=admin_headers,
        json={
            **CREATE_PAYLOAD,
            "course_code": code,
            "course_name": "Mata Kuliah Cache Baru",
        },
    )
    assert created.status_code == 201, created.text

    calls_before_request = counter["calls"]
    after = client.get("/api/v1/courses", params=params)
    assert after.status_code == 200
    assert counter["calls"] == calls_before_request + 1
    assert any(course["code"] == code for course in after.json()["courses"])


def test_admin_update_invalidates_catalog_cache(client, admin_headers, monkeypatch):
    counter = {"calls": 0}
    _count_builder(monkeypatch, counter)
    code = _unique_code()

    created = client.post(
        "/api/v1/admin/courses",
        headers=admin_headers,
        json={
            **CREATE_PAYLOAD,
            "course_code": code,
            "course_name": "Nama Awal Cache",
        },
    )
    assert created.status_code == 201, created.text

    params = {"q": code}
    before = client.get("/api/v1/courses", params=params)
    assert before.status_code == 200
    assert before.json()["courses"][0]["name"] == "Nama Awal Cache"
    calls_before_update = counter["calls"]

    updated = client.put(
        f"/api/v1/admin/courses/{code}",
        headers=admin_headers,
        json={"course_name": "Nama Ubah Cache"},
    )
    assert updated.status_code == 200, updated.text

    after = client.get("/api/v1/courses", params=params)
    assert after.status_code == 200
    assert counter["calls"] > calls_before_update
    assert after.json()["courses"][0]["name"] == "Nama Ubah Cache"


def test_fallback_response_is_not_cached(client, monkeypatch):
    counter = {"calls": 0}

    async def unavailable(db):
        counter["calls"] += 1
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(catalog, "build_catalog_from_db", unavailable)
    params = {
        "page": 1,
        "per_page": 5,
        "q": f"Fallback {random.randint(10000, 99999)}",
    }

    first = client.get("/api/v1/courses", params=params)
    second = client.get("/api/v1/courses", params=params)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["source"] == "local_fallback"
    assert second.json()["source"] == "local_fallback"
    assert counter["calls"] == 2


def test_cache_serialization_failure_does_not_fail_request(client, monkeypatch):
    params = {"q": f"Cache Gagal {random.randint(10000, 99999)}"}
    first = client.get("/api/v1/courses", params=params)
    assert first.status_code == 200
    assert first.json()["source"] == "database"

    def broken_clone(value):
        raise TypeError("gagal menyalin payload cache")

    monkeypatch.setattr(catalog, "_clone_cached", broken_clone)
    second = client.get("/api/v1/courses", params=params)

    assert second.status_code == 200
    assert second.content == first.content


def test_cached_database_response_falls_back_when_db_dies(client, monkeypatch):
    params = {
        "page": 1,
        "per_page": 5,
        "q": f"DB Mati {random.randint(10000, 99999)}",
    }
    primed = client.get("/api/v1/courses", params=params)
    assert primed.status_code == 200
    assert primed.json()["source"] == "database"

    state = {"probes": 0}

    async def probe_fails(db):
        state["probes"] += 1
        raise RuntimeError("database probe unavailable")

    async def build_fails(db):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(catalog, "catalog_db_is_available", probe_fails)
    monkeypatch.setattr(catalog, "build_catalog_from_db", build_fails)

    after = client.get("/api/v1/courses", params=params)

    assert state["probes"] == 1
    assert after.status_code == 200
    assert after.json()["source"] == "local_fallback"
