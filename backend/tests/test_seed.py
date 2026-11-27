"""Integrasi seeder #33: PJ Prodi, voter per prodi, dan idempotensi."""

import json
from collections import Counter, defaultdict
from pathlib import Path
from unittest.mock import AsyncMock, patch

from sqlalchemy import text

from scripts import seed as seed_module
from catalog import get_all_courses, prodi_code
import app as app_module
import settings

EXPECTED_PJ = {
    "TSD": "dwi.rantini@ftmm.unair.ac.id",
    "TRKB": "asif.ali@ftmm.unair.ac.id",
    "RN": "mirza.ardella@ftmm.unair.ac.id",
    "TI": "chandrawati.p.w@ftmm.unair.ac.id",
    "TE": "agus.mukhlisin@ftmm.unair.ac.id",
}
EXPECTED_PJ_NAMES = {
    "TSD": "Dr. Dwi Rantini, S.Si.",
    "TRKB": "Asif Ali Zamzami",
    "RN": "Mirza Ardella Saputra, S.Si., M.Sc., Ph.D",
    "TI": "Chandrawati Putri Wulandari, S.T., M.T., MBA., Ph.D.",
    "TE": "Dr. Agus Mukhlisin, S.T., M.T.",
}
PJ_PASSWORD = "PjProdi2026!"
LEGACY_LECTURER_EMAIL = "dosen.testing@ftmm.unair.ac.id"
MHS_EMAIL = "mahasiswa.testing@ftmm.unair.ac.id"


def _rows(client, db_session, sql: str, params: dict | None = None) -> list[dict]:
    async def run():
        result = await db_session.execute(text(sql), params or {})
        return [dict(row) for row in result.mappings().all()]

    return client.portal.call(run)


def _one(client, db_session, sql: str, params: dict | None = None) -> dict | None:
    rows = _rows(client, db_session, sql, params)
    return rows[0] if rows else None


def _active_period(client, db_session) -> dict:
    period = _one(
        client,
        db_session,
        "SELECT polling_period_id::text AS id, target_term, max_votes_per_student "
        "FROM elective_polling_periods WHERE status = 'open' "
        "ORDER BY created_at DESC LIMIT 1",
    )
    assert period is not None
    return period


def _catalog_by_id() -> dict:
    return {course.id: course for course in get_all_courses()}


def _assert_voters_and_votes_are_scoped(client, db_session) -> None:
    period = _active_period(client, db_session)
    voters = _rows(
        client,
        db_session,
        "SELECT u.user_id::text AS id, u.email, sp.program_name, "
        "spp.current_semester "
        "FROM users u "
        "JOIN student_profiles spp ON spp.user_id = u.user_id "
        "JOIN study_programs sp ON sp.study_program_id = spp.study_program_id "
        "WHERE u.email LIKE 'student.voter%' ORDER BY u.email",
    )
    assert len(voters) == 45
    assert Counter(prodi_code(voter["program_name"]) for voter in voters) == Counter(
        {code: 9 for code in EXPECTED_PJ}
    )

    target_parity = "odd" if period["target_term"] == "ganjil" else "even"
    expected_parity = "odd" if target_parity == "even" else "even"
    for voter in voters:
        actual = "odd" if voter["current_semester"] % 2 == 1 else "even"
        assert actual == expected_parity, voter["email"]

    votes = _rows(
        client,
        db_session,
        "SELECT user_id::text AS uid, course_id, priority "
        "FROM elective_course_votes WHERE polling_period_id = CAST(:pid AS uuid)",
        {"pid": period["id"]},
    )
    by_user: dict[str, list[dict]] = defaultdict(list)
    for vote in votes:
        by_user[vote["uid"]].append(vote)

    catalog = _catalog_by_id()
    max_votes = int(period["max_votes_per_student"] or 3)
    for voter in voters:
        own = by_user[voter["id"]]
        assert len(own) <= max_votes
        assert sorted(vote["priority"] for vote in own) == list(range(1, len(own) + 1))
        for vote in own:
            course = catalog.get(vote["course_id"])
            assert course is not None, vote
            assert course.type == "Pilihan", vote
            assert prodi_code(course.program) == prodi_code(voter["program_name"]), vote

    mhs = _one(
        client,
        db_session,
        "SELECT user_id::text AS id FROM users WHERE email = :email",
        {"email": MHS_EMAIL},
    )
    assert mhs is not None
    mhs_votes = by_user[mhs["id"]]
    assert 0 < len(mhs_votes) <= max_votes
    assert sorted(vote["priority"] for vote in mhs_votes) == list(
        range(1, len(mhs_votes) + 1)
    )
    for vote in mhs_votes:
        course = catalog.get(vote["course_id"])
        assert course is not None and course.type == "Pilihan", vote
        assert prodi_code(course.program) == "TSD", vote


def test_seed_creates_exactly_five_active_pj_accounts(client, admin_headers, db_session):
    pjs = _rows(
        client,
        db_session,
        "SELECT u.email, u.full_name, u.role FROM users u "
        "JOIN lecturer_profiles lp ON lp.user_id = u.user_id "
        "WHERE lp.is_program_coordinator = true AND u.is_active = true "
        "ORDER BY u.email",
    )
    assert {pj["email"] for pj in pjs} == set(EXPECTED_PJ.values())
    assert len(pjs) == 5
    for pj in pjs:
        code = next(code for code, email in EXPECTED_PJ.items() if email == pj["email"])
        assert pj["full_name"] == EXPECTED_PJ_NAMES[code]
        assert pj["role"] == "lecturer"

    response = client.get(
        "/api/v1/admin/accounts",
        params={"search": "dwi.rantini@", "role": "lecturer", "status": "active"},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    assert any(
        row["email"] == EXPECTED_PJ["TSD"] for row in response.json()["data"]
    )


def test_seed_has_one_active_coordinator_per_prodi(client, db_session):
    coordinators = _rows(
        client,
        db_session,
        "SELECT sp.program_code, u.email, lp.employee_number "
        "FROM lecturer_profiles lp "
        "JOIN users u ON u.user_id = lp.user_id "
        "JOIN study_programs sp ON sp.study_program_id = lp.study_program_id "
        "WHERE lp.is_program_coordinator = true AND u.is_active = true "
        "ORDER BY sp.program_code",
    )
    assert len(coordinators) == 5
    assert {row["program_code"]: row["email"] for row in coordinators} == EXPECTED_PJ
    assert all(row["employee_number"] is not None for row in coordinators)


def test_seed_rooms_match_inventory_floor_plan(client, db_session):
    rooms = _rows(
        client,
        db_session,
        "SELECT room_code, building, floor, capacity, is_active FROM rooms",
    )
    assert len(rooms) == 26
    assert len({room["room_code"] for room in rooms}) == 26
    assert all(room["is_active"] for room in rooms)
    assert all(room["capacity"] == 60 for room in rooms)

    by_code = {room["room_code"]: room for room in rooms}
    assert "L1" not in by_code
    for code in ("LAB-TRKB", "LAB-TI"):
        assert (by_code[code]["building"], by_code[code]["floor"]) == ("NANO", "1")
    assert (by_code["10.RN"]["building"], by_code["10.RN"]["floor"]) == ("NANI", "10")


def test_seed_creates_52_active_lecturers_from_curated_roster(client, db_session):
    lecturers = _rows(
        client,
        db_session,
        "SELECT u.email, u.full_name, lp.employee_number "
        "FROM users u JOIN lecturer_profiles lp ON lp.user_id = u.user_id "
        "WHERE u.is_active = true AND u.role = 'lecturer'",
    )
    assert len(lecturers) == 52
    assert len({row["email"] for row in lecturers}) == 52
    assert all(row["employee_number"] is not None for row in lecturers)
    assert LEGACY_LECTURER_EMAIL not in {row["email"] for row in lecturers}

    roster_path = Path(__file__).resolve().parents[2] / "database" / "seed" / "lecturers.json"
    with roster_path.open(encoding="utf-8") as handle:
        roster = json.load(handle)["lecturers"]
    expected = {
        item["email"]: (item["name"], item["employee_number"])
        for item in roster
    }
    assert {row["email"] for row in lecturers} == set(expected)
    for row in lecturers:
        name, employee_number = expected[row["email"]]
        assert row["full_name"] == name, row["email"]
        assert row["employee_number"] == employee_number, row["email"]


def test_legacy_testing_lecturer_is_not_active(client, admin_headers, db_session):
    active = _one(
        client,
        db_session,
        "SELECT email FROM users WHERE email = :email AND is_active = true",
        {"email": LEGACY_LECTURER_EMAIL},
    )
    assert active is None

    response = client.get(
        "/api/v1/admin/accounts",
        params={"search": "dosen.testing@", "status": "active"},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    assert all(
        row["email"] != LEGACY_LECTURER_EMAIL for row in response.json()["data"]
    )


def test_seed_gives_voters_profiles_and_own_prodi_votes(client, student_headers, db_session):
    _assert_voters_and_votes_are_scoped(client, db_session)

    response = client.get("/api/v1/polling/my-votes", headers=student_headers)
    assert response.status_code == 200, response.text
    votes = response.json()
    assert len(votes) <= 3
    assert len({vote["priority"] for vote in votes}) == len(votes)


def test_reseed_is_idempotent(client, db_session, monkeypatch):
    class _BoundSession:
        async def __aenter__(self):
            return db_session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(seed_module, "AsyncSessionLocal", lambda: _BoundSession())
    monkeypatch.setattr(seed_module, "get_password_hash", lambda _: "seeded-hash")

    def _counts() -> dict:
        period = _active_period(client, db_session)
        return {
            "pj": _one(
                client,
                db_session,
                "SELECT count(*) AS n FROM users u JOIN lecturer_profiles lp "
                "ON lp.user_id = u.user_id WHERE u.is_active = true "
                "AND lp.is_program_coordinator = true",
            )["n"],
            "coordinators": _one(
                client,
                db_session,
                "SELECT count(*) AS n FROM lecturer_profiles "
                "WHERE is_program_coordinator = true",
            )["n"],
            "voters": _one(
                client,
                db_session,
                "SELECT count(*) AS n FROM users WHERE email LIKE 'student.voter%'",
            )["n"],
            "profiles": _one(
                client,
                db_session,
                "SELECT count(*) AS n FROM student_profiles sp "
                "JOIN users u ON u.user_id = sp.user_id "
                "WHERE u.email LIKE 'student.voter%'",
            )["n"],
            "demo_votes": _one(
                client,
                db_session,
                "SELECT count(*) AS n FROM elective_course_votes v "
                "JOIN users u ON u.user_id = v.user_id "
                "WHERE v.polling_period_id = CAST(:pid AS uuid) "
                "AND (u.email LIKE 'student.voter%' OR u.email = :mhs)",
                {"pid": period["id"], "mhs": MHS_EMAIL},
            )["n"],
            "duplicate_priorities": _one(
                client,
                db_session,
                "SELECT count(*) AS n FROM ("
                "SELECT user_id, priority FROM elective_course_votes "
                "WHERE polling_period_id = CAST(:pid AS uuid) "
                "GROUP BY user_id, priority HAVING count(*) > 1) duplicates",
                {"pid": period["id"]},
            )["n"],
            "preferences": _one(
                client,
                db_session,
                "SELECT count(*) AS n FROM lecturer_schedule_preferences "
                "WHERE academic_period_id = CAST(:pid AS uuid)",
                {"pid": period["id"]},
            )["n"],
            "mappings": _one(
                client,
                db_session,
                "SELECT count(*) AS n FROM course_instructor_references "
                "WHERE academic_period_id = CAST(:pid AS uuid)",
                {"pid": period["id"]},
            )["n"],
            "assignments": _one(
                client,
                db_session,
                "SELECT count(*) AS n FROM class_instructor_assignments "
                "WHERE academic_period_id = CAST(:pid AS uuid)",
                {"pid": period["id"]},
            )["n"],
            "schedule_runs": _one(
                client,
                db_session,
                "SELECT count(*) AS n FROM schedule_runs "
                "WHERE academic_period_id = CAST(:pid AS uuid)",
                {"pid": period["id"]},
            )["n"],
        }

    before = _counts()
    client.portal.call(seed_module.seed_data)
    after_first = _counts()
    client.portal.call(seed_module.seed_data)
    after_second = _counts()

    assert before == after_first == after_second
    assert after_second["pj"] == 5
    assert after_second["coordinators"] == 5
    assert after_second["voters"] == 45
    assert after_second["profiles"] == 45
    assert after_second["duplicate_priorities"] == 0
    _assert_voters_and_votes_are_scoped(client, db_session)


def test_startup_does_not_seed_when_auto_seed_is_disabled(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTO_SEED", False)

    async def run_startup():
        with (
            patch("alembic.command.upgrade"),
            patch("scripts.seed.seed_data", new_callable=AsyncMock) as seeded,
            patch("catalog.refresh_from_db", new_callable=AsyncMock),
        ):
            async with app_module.lifespan(app_module.app):
                pass
        seeded.assert_not_awaited()

    client.portal.call(run_startup)
