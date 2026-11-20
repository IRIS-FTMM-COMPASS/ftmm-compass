"""Regresi scope prodi: katalog harus difilter server-side, bukan di UI."""

import uuid

import pytest
from sqlalchemy import select, text

from auth import get_password_hash
from catalog import invalidate_catalog_cache, normalize_prodi
from models import LecturerProfile, StudyProgram, StudentProfile, User
from rate_limit import limiter
from tests.conftest import SEEDED_ADMIN, SEEDED_PJ, SEEDED_STUDENT

V1 = "/api/v1"
STUDENT_PASSWORD = "Mahasiswa2026!"
CREATED_PASSWORD = "ScopeUji2026!"
TSD_DEMO_STUDENT = ("mahasiswa.tsd@ftmm.unair.ac.id", STUDENT_PASSWORD)

ALL_PRODI = {
    "TSD": "Teknologi Sains Data",
    "TRKB": "Teknik Robotika dan Kecerdasan Buatan",
    "RN": "Rekayasa Nanoteknologi",
    "TI": "Teknik Industri",
    "TE": "Teknik Elektro",
}

DEMO_STUDENTS = [
    pytest.param("TSD", *TSD_DEMO_STUDENT, ALL_PRODI["TSD"], id="tsd"),
    pytest.param(
        "TRKB",
        "mahasiswa.trkb@ftmm.unair.ac.id",
        STUDENT_PASSWORD,
        ALL_PRODI["TRKB"],
        id="trkb",
    ),
    pytest.param(
        "RN",
        "mahasiswa.rn@ftmm.unair.ac.id",
        STUDENT_PASSWORD,
        ALL_PRODI["RN"],
        id="rn",
    ),
    pytest.param(
        "TI",
        "mahasiswa.ti@ftmm.unair.ac.id",
        STUDENT_PASSWORD,
        ALL_PRODI["TI"],
        id="ti",
    ),
    pytest.param(
        "TE",
        "mahasiswa.te@ftmm.unair.ac.id",
        STUDENT_PASSWORD,
        ALL_PRODI["TE"],
        id="te",
    ),
]


@pytest.fixture(autouse=True)
def isolated_catalog_cache():
    invalidate_catalog_cache()
    yield
    invalidate_catalog_cache()


def _login_headers(client, credentials: tuple[str, str]) -> dict[str, str]:
    limiter.reset()
    response = client.post(
        f"{V1}/auth/login",
        json={"identifier": credentials[0], "password": credentials[1]},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _list_body(client, headers: dict[str, str], prodi: str) -> dict:
    response = client.get(f"{V1}/courses", params={"prodi": prodi}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _other_code(code: str) -> str:
    return next(candidate for candidate in ALL_PRODI if candidate != code)


def _assert_scoped_list(body: dict, own_prodi: str) -> None:
    assert body["program_studi"] == own_prodi
    assert body["programs"] == [own_prodi]
    assert body["courses"], "Katalog prodi seharusnya berisi mata kuliah."
    assert {normalize_prodi(c["program"]) for c in body["courses"]} == {own_prodi}


def _assert_unrestricted_list(body: dict) -> None:
    assert body["program_studi"] == "Semua Program Studi"
    assert set(body["programs"]) == set(ALL_PRODI.values())
    assert {normalize_prodi(c["program"]) for c in body["courses"]} == set(
        ALL_PRODI.values()
    )


def _foreign_only_code(
    client, admin_headers: dict[str, str], own_prodi: str, other_prodi: str
) -> str:
    own_codes = {
        course["code"] for course in _list_body(client, admin_headers, own_prodi)["courses"]
    }
    other_codes = {
        course["code"]
        for course in _list_body(client, admin_headers, other_prodi)["courses"]
    }
    candidates = sorted(code for code in other_codes - own_codes if code)
    assert candidates, f"Tidak ada kode unik di {other_prodi} untuk uji batas akses."
    return candidates[0]


@pytest.mark.parametrize(("code", "email", "password", "own_prodi"), DEMO_STUDENTS)
def test_demo_student_catalog_and_search_are_scoped(
    client, code: str, email: str, password: str, own_prodi: str
):
    headers = _login_headers(client, (email, password))

    own_body = _list_body(client, headers, "all")
    _assert_scoped_list(own_body, own_prodi)
    own_code = own_body["courses"][0]["code"]

    other_prodi = ALL_PRODI[_other_code(code)]
    response = client.get(
        f"{V1}/courses/search",
        params={"q": own_code, "prodi": other_prodi},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["program_studi"] == own_prodi
    assert body["results"], "Pencarian kode mata kuliah sendiri seharusnya menemukan mata kuliah."
    assert {normalize_prodi(item["program"]) for item in body["results"]} == {own_prodi}


@pytest.mark.parametrize(("code", "email", "password", "own_prodi"), DEMO_STUDENTS)
def test_scoped_student_cannot_read_foreign_course_detail(
    client, code: str, email: str, password: str, own_prodi: str
):
    admin_headers = _login_headers(client, SEEDED_ADMIN)
    other_prodi = ALL_PRODI[_other_code(code)]
    foreign_code = _foreign_only_code(client, admin_headers, own_prodi, other_prodi)
    assert client.get(f"{V1}/courses/{foreign_code}", headers=admin_headers).status_code == 200

    headers = _login_headers(client, (email, password))
    response = client.get(f"{V1}/courses/{foreign_code}", headers=headers)
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "course_not_found"


def test_admin_catalog_population_does_not_leak_to_student(client):
    admin_headers = _login_headers(client, SEEDED_ADMIN)
    _assert_unrestricted_list(_list_body(client, admin_headers, "all"))

    tsd_headers = _login_headers(client, TSD_DEMO_STUDENT)
    _assert_scoped_list(_list_body(client, tsd_headers, "all"), ALL_PRODI["TSD"])


def test_seeded_student_is_scoped_to_tsd(client):
    headers = _login_headers(client, SEEDED_STUDENT)
    _assert_scoped_list(_list_body(client, headers, "all"), ALL_PRODI["TSD"])


def test_pj_tsd_sees_only_own_prodi(client):
    headers = _login_headers(client, SEEDED_PJ)
    _assert_scoped_list(_list_body(client, headers, "all"), ALL_PRODI["TSD"])


def test_admin_with_all_still_sees_every_prodi(client):
    headers = _login_headers(client, SEEDED_ADMIN)
    _assert_unrestricted_list(_list_body(client, headers, "all"))


def _create_unrestricted_user(client, db_session, role: str) -> str:
    email = f"scope.{role}.{uuid.uuid4().hex[:8]}@ftmm.unair.ac.id"

    async def insert():
        user = User(
            email=email,
            full_name=f"Uji {role}",
            password_hash=get_password_hash(CREATED_PASSWORD),
            is_active=True,
            role=role,
        )
        db_session.add(user)
        await db_session.flush()
        if role == "lecturer":
            program = (
                await db_session.execute(
                    select(StudyProgram).where(StudyProgram.program_code == "TSD")
                )
            ).scalars().one()
            db_session.add(
                LecturerProfile(
                    user_id=user.user_id,
                    study_program_id=program.study_program_id,
                    is_program_coordinator=False,
                )
            )
        await db_session.commit()
        return email

    return client.portal.call(insert)


@pytest.mark.parametrize(
    "role",
    [
        pytest.param("faculty_staff", id="faculty_staff"),
        pytest.param("lecturer", id="non_coordinator_lecturer"),
    ],
)
def test_unrestricted_roles_see_every_prodi(client, db_session, role: str):
    """Seed tidak punya akun unrestricted; akun uji dibuat di transaksi ini."""
    email = _create_unrestricted_user(client, db_session, role)
    headers = _login_headers(client, (email, CREATED_PASSWORD))
    _assert_unrestricted_list(_list_body(client, headers, "all"))


def _create_student_without_study_program(client, db_session, profile_state: str) -> str:
    email = f"scope.tanpaprodi.{uuid.uuid4().hex[:8]}@ftmm.unair.ac.id"

    async def insert():
        user = User(
            email=email,
            full_name="Mahasiswa Tanpa Prodi",
            role="student",
            password_hash=get_password_hash(CREATED_PASSWORD),
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()
        if profile_state == "null_study_program":
            # Kolom NOT NULL dilonggarkan hanya di transaksi uji ini.
            await db_session.execute(
                text("ALTER TABLE student_profiles ALTER COLUMN study_program_id DROP NOT NULL")
            )
            db_session.add(
                StudentProfile(
                    user_id=user.user_id,
                    study_program_id=None,
                    student_number=f"T{uuid.uuid4().hex[:9]}",
                    admission_year=2023,
                    current_semester=3,
                )
            )
        await db_session.commit()
        return email

    return client.portal.call(insert)


@pytest.mark.parametrize(
    "profile_state",
    [
        pytest.param("missing_profile", id="tanpa_profil"),
        pytest.param("null_study_program", id="profil_tanpa_prodi"),
    ],
)
def test_student_without_study_program_is_denied(
    client, db_session, profile_state: str
):
    email = _create_student_without_study_program(client, db_session, profile_state)
    headers = _login_headers(client, (email, CREATED_PASSWORD))

    requests = (
        (f"{V1}/courses", {"prodi": "all"}),
        (f"{V1}/courses/search", {"q": "AGI", "prodi": "all"}),
        (f"{V1}/courses/AGI101", None),
    )
    for path, params in requests:
        response = client.get(path, params=params, headers=headers)
        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == "prodi_belum_ditetapkan"
