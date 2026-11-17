"""Regresi kontrak API dua tier antara jalur kanonik dan jalur lawas."""

import uuid
from contextlib import contextmanager
from unittest.mock import patch

import app as app_module
import settings
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from pytest import fixture, mark
from rate_limit import limiter

OFFLINE_CHATBOT_URL = "http://127.0.0.1:59999"
INTERNAL_SECRET = "kontrak-rahasia-9f3a"

ADMIN_COURSE_PAYLOAD = {
    "course_code": "ZZ409",
    "course_name": "Mata Kuliah Probe Kontrak",
    "program_name": "Teknologi Sains Data",
    "credits": 3,
    "recommended_semester": 1,
    "term": "ganjil",
    "course_type": "Pilihan",
}

# Kegagalan aturan bisnis: HTTP 200 dengan is_valid false, tanpa amplop error.
VALIDATION_FAILURE_PAYLOAD = {
    "program_studi": "Teknologi Sains Data",
    "semester_saat_ini": 1,
    "riwayat_matkul_lulus": [],
    "maks_sks_per_semester": 24,
    "plan": {
        1: [
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
    },
}

# Kegagalan skema permintaan: HTTP 422 dengan amplop validation_error.
SEMESTER_BOUNDARY_PAYLOAD = {
    "program_studi": "Teknologi Sains Data",
    "semester_saat_ini": "semester-9",
    "plan": {},
}

PARITY_MISMATCH_PAYLOAD = {
    "program_studi": "Teknologi Sains Data",
    "semester_saat_ini": 1,
    "plan": {
        1: [
            {
                "name": "Matematika I",
                "code": "MA1101",
                "credits": 4,
                "semester": 1,
                "type": "Wajib",
                "parity": "ganjil",
            }
        ]
    },
}

SKS_LIMIT_PAYLOAD = {
    "program_studi": "Teknologi Sains Data",
    "semester_saat_ini": 1,
    "maks_sks_per_semester": "dua puluh empat",
    "plan": {},
}

SUCCESS_PAIRS = (
    ("health", "/health", "/health", "GET", {}),
    ("courses", "/courses", "/courses", "GET", {}),
    (
        "courses/search",
        "/courses/search",
        "/courses/search",
        "GET",
        {"params": {"q": "kalkulus"}},
    ),
    ("courses/AGI101", "/courses/AGI101", "/courses/AGI101", "GET", {}),
    (
        "dashboard/me",
        "/dashboard/me",
        "/dashboard/me",
        "GET",
        {"authenticated": True},
    ),
    (
        "plan/validate",
        "/plans/validations",
        "/plan/validate",
        "POST",
        {"json": VALIDATION_FAILURE_PAYLOAD},
    ),
    (
        "notifications/me",
        "/notifications/me",
        "/notifications/me",
        "GET",
        {"authenticated": True},
    ),
)

SCHEMA_FAILURE_CASES = (
    ("batas semester", SEMESTER_BOUNDARY_PAYLOAD, "semester_saat_ini"),
    ("paritas semester", PARITY_MISMATCH_PAYLOAD, "parity"),
    ("batas SKS", SKS_LIMIT_PAYLOAD, "maks_sks_per_semester"),
)

EXPECTED_ERROR_CODES = {
    400: "http_error",
    401: "unauthorized",
    403: "forbidden",
    404: "course_not_found",
    409: "duplicate_course_code",
    422: "validation_error",
    429: "rate_limit_exceeded",
    500: "internal_server_error",
}


@fixture(autouse=True)
def deterministic_surface():
    """Membuat health, pencarian, dan waktu notifikasi deterministik."""
    original = settings.CHATBOT_SERVICE_URL
    settings.CHATBOT_SERVICE_URL = OFFLINE_CHATBOT_URL
    try:
        with patch("api.auth._format_relative_time", return_value="Baru saja"):
            yield
    finally:
        settings.CHATBOT_SERVICE_URL = original


@contextmanager
def temporary_route(path, endpoint, methods=("GET",)):
    """Memasang rute probe lalu memulihkan daftar rute setelahnya."""
    original_routes = list(app_module.app.router.routes)
    app_module.app.add_api_route(
        path, endpoint, methods=list(methods), include_in_schema=False
    )
    try:
        yield
    finally:
        app_module.app.router.routes[:] = original_routes


def bad_request_probe():
    raise HTTPException(status_code=400, detail="Permintaan probe tidak valid.")


@limiter.limit("1/minute")
def rate_limited_probe(request: Request):
    return {"ok": True}


def exploding_probe():
    raise RuntimeError(f"rincian internal bocor: {INTERNAL_SECRET}")


def assert_envelope(response, expected_status):
    assert response.status_code == expected_status
    content_type = response.headers.get("content-type", "")
    assert content_type.startswith("application/json")
    assert "text/plain" not in content_type

    body = response.json()
    assert "error" in body
    error = body["error"]
    assert isinstance(error["code"], str) and error["code"]
    assert isinstance(error["message"], str) and error["message"]
    assert isinstance(error["details"], list)
    assert "Traceback" not in response.text
    assert INTERNAL_SECRET not in response.text


def assert_sprint9_parity(canonical, legacy, expected_status):
    """Bandingkan status, struktur payload, dan kode error antar dua tier."""
    assert canonical.status_code == legacy.status_code == expected_status

    def shape(response):
        body = response.json()
        result = {"keys": sorted(body)}
        error = body.get("error")
        if isinstance(error, dict):
            result["error_code"] = error.get("code")
            result["error_keys"] = sorted(error)
            result["details"] = [
                (item.get("field"), item.get("code"))
                if isinstance(item, dict)
                else item
                for item in error.get("details", [])
            ]
        return result

    assert shape(canonical) == shape(legacy)


@mark.parametrize(
    "label, canonical_path, legacy_path, method, options",
    SUCCESS_PAIRS,
    ids=[item[0] for item in SUCCESS_PAIRS],
)
def test_pasangan_kanonik_dan_lawas_setara(
    client, student_headers, label, canonical_path, legacy_path, method, options
):
    request_options = dict(options)
    if request_options.pop("authenticated", False):
        request_options["headers"] = student_headers

    canonical = client.request(method, f"/api/v1{canonical_path}", **request_options)
    legacy = client.request(method, f"/api{legacy_path}", **request_options)

    assert canonical.status_code == legacy.status_code == 200, label
    assert canonical.json() == legacy.json(), label


@mark.parametrize("path", ("/api/v1/plans/validations", "/api/plan/validate"))
@mark.parametrize(
    "case, payload, field",
    SCHEMA_FAILURE_CASES,
    ids=[item[0] for item in SCHEMA_FAILURE_CASES],
)
def test_kegagalan_skema_memakai_kode_validasi_yang_sama(
    client, path, case, payload, field
):
    response = client.post(path, json=payload)

    assert_envelope(response, 422)
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert any(field in item["field"] for item in body["error"]["details"]), case


@mark.parametrize("status_code", tuple(EXPECTED_ERROR_CODES))
def test_amplop_error_konsisten(client, admin_headers, student_headers, status_code):
    if status_code == 400:
        with temporary_route("/__contract_probe/bad_request", bad_request_probe):
            response = client.get("/__contract_probe/bad_request")
    elif status_code == 429:
        with temporary_route("/__contract_probe/rate_limited", rate_limited_probe):
            client.get("/__contract_probe/rate_limited")
            response = client.get("/__contract_probe/rate_limited")
    elif status_code == 500:
        with TestClient(app_module.app, raise_server_exceptions=False) as probe_client:
            with temporary_route("/__contract_probe/unhandled", exploding_probe):
                response = probe_client.get("/__contract_probe/unhandled")
    elif status_code == 401:
        response = client.get("/api/v1/dashboard/me")
    elif status_code == 403:
        response = client.post(
            "/api/v1/admin/courses", headers=student_headers, json=ADMIN_COURSE_PAYLOAD
        )
    elif status_code == 404:
        response = client.get("/api/v1/courses/ZZZ999")
    elif status_code == 409:
        response = client.post(
            "/api/v1/admin/courses",
            headers=admin_headers,
            json={**ADMIN_COURSE_PAYLOAD, "course_code": "AGI101"},
        )
    else:
        response = client.get("/api/v1/courses", params={"per_page": 0})

    assert_envelope(response, status_code)
    assert response.json()["error"]["code"] == EXPECTED_ERROR_CODES[status_code]


def test_respons_error_tidak_pernah_teks_biasa(client):
    responses = (
        client.get("/api/v1/courses/ZZZ999"),
        client.get("/api/v1/courses", params={"per_page": 0}),
        client.get("/api/v1/dashboard/me"),
    )
    for response in responses:
        assert response.status_code >= 400
        assert response.headers.get("content-type", "").startswith("application/json")


def test_parity_register(client):
    unique = uuid.uuid4().hex[:8]
    payload = {
        "email": f"parity.{unique}@gmail.com",
        "full_name": "Mahasiswa Parity",
        "student_number": f"99{unique}",
        "admission_year": 2026,
        "password": "ParityRegister2026!",
    }
    limiter.reset()
    canonical = client.post("/api/v1/auth/register", json=payload)
    legacy = client.post("/api/auth/register", json=payload)

    assert_sprint9_parity(canonical, legacy, 422)
    assert canonical.json()["error"]["details"][0]["code"] == "invalid_email_domain"


def test_parity_recover(client):
    unique = uuid.uuid4().hex[:8].upper()
    payload = {
        "recovery_code": f"FTMM-{unique}-PARI-TY00",
        "new_password": "ParityRecover2026!",
    }
    limiter.reset()
    canonical = client.post("/api/v1/auth/recover", json=payload)
    legacy = client.post("/api/auth/recover", json=payload)

    assert_sprint9_parity(canonical, legacy, 400)
    assert canonical.json()["error"]["code"] == "invalid_recovery_code"


def test_parity_change_password(client, student_headers):
    payload = {
        "current_password": f"salah-{uuid.uuid4().hex[:8]}",
        "new_password": "ParityChange2026!",
    }
    canonical = client.post(
        "/api/v1/auth/change-password", headers=student_headers, json=payload
    )
    legacy = client.post(
        "/api/auth/change-password", headers=student_headers, json=payload
    )

    assert_sprint9_parity(canonical, legacy, 400)
    assert canonical.json()["error"]["code"] == "invalid_current_password"


def test_parity_admin_accounts(client, admin_headers, student_headers):
    params = {"search": f"parity-{uuid.uuid4().hex[:8]}", "page": 1, "page_size": 5}

    canonical = client.get(
        "/api/v1/admin/accounts", headers=admin_headers, params=params
    )
    legacy = client.get("/api/admin/accounts", headers=admin_headers, params=params)

    assert_sprint9_parity(canonical, legacy, 200)
    body = canonical.json()
    assert {"data", "meta"} <= set(body)
    assert {"page", "page_size", "total"} <= set(body["meta"])

    denied_canonical = client.get("/api/v1/admin/accounts", headers=student_headers)
    denied_legacy = client.get("/api/admin/accounts", headers=student_headers)

    assert_sprint9_parity(denied_canonical, denied_legacy, 403)
    assert denied_canonical.json()["error"]["code"] == "forbidden"


def test_parity_chat_stream_unauthenticated(client):
    payload = {"message": f"parity-{uuid.uuid4().hex[:8]}"}

    canonical = client.post("/api/v1/chat/stream", json=payload)
    legacy = client.post("/api/chat/stream", json=payload)

    assert_sprint9_parity(canonical, legacy, 401)
    assert canonical.json()["error"]["code"] == "unauthorized"
