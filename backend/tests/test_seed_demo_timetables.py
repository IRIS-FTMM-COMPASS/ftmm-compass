"""Regresi seeder: jadwal demo mengikuti item rencana studi aktif yang eligible."""

import pytest
from sqlalchemy import text

from rate_limit import limiter

DEMO_CODES = ("TSD", "TRKB", "RN", "TI", "TE")
DEMO_EMAILS = {
    code: f"mahasiswa.{code.lower()}@ftmm.unair.ac.id" for code in DEMO_CODES
}
STUDENT_PASSWORD = "Mahasiswa2026!"
DASHBOARD_PATH = "/api/v1/dashboard/me"
TIMETABLE_PATH = "/api/v1/me/timetable"


def _rows(client, db_session, sql: str, params: dict | None = None) -> list[dict]:
    async def run():
        result = await db_session.execute(text(sql), params or {})
        return [dict(row) for row in result.mappings().all()]

    return client.portal.call(run)


def _email_params() -> dict[str, str]:
    return {code.lower(): email for code, email in DEMO_EMAILS.items()}


def _active_period(client, db_session) -> dict:
    periods = _rows(
        client,
        db_session,
        "SELECT academic_period_id::text AS id, term "
        "FROM academic_periods WHERE is_active = true",
    )
    assert len(periods) == 1, periods
    return periods[0]


def _plan_terms_by_email(client, db_session) -> dict[str, dict[str, str]]:
    """Semua kode MK pada rencana aktif tiap mahasiswa beserta term-nya."""
    rows = _rows(
        client,
        db_session,
        """
        SELECT u.email, c.course_code, cc.term AS course_term
        FROM degree_plans dp
        JOIN users u ON u.user_id = dp.user_id
        JOIN degree_plan_items dpi ON dpi.degree_plan_id = dp.degree_plan_id
        JOIN curriculum_courses cc
             ON cc.curriculum_course_id = dpi.curriculum_course_id
        JOIN courses c ON c.course_id = cc.course_id
        WHERE dp.status = 'active'
          AND u.email IN (:tsd, :trkb, :rn, :ti, :te)
        """,
        _email_params(),
    )
    plans: dict[str, dict[str, str]] = {
        email: {} for email in DEMO_EMAILS.values()
    }
    for row in rows:
        plans[row["email"]][row["course_code"]] = row["course_term"]
    return plans


def _schedulable_codes_by_email(
    client, db_session, period_id: str
) -> dict[str, set[str]]:
    """MK rencana yang punya seksi eligible pada kurikulum dan periode aktif."""
    rows = _rows(
        client,
        db_session,
        """
        SELECT DISTINCT u.email, c.course_code
        FROM degree_plans dp
        JOIN users u ON u.user_id = dp.user_id
        JOIN degree_plan_items dpi ON dpi.degree_plan_id = dp.degree_plan_id
        JOIN curriculum_courses cc
             ON cc.curriculum_course_id = dpi.curriculum_course_id
        JOIN courses c ON c.course_id = cc.course_id
        JOIN student_curriculum_assignments sca
             ON sca.student_curriculum_assignment_id
                = dp.student_curriculum_assignment_id
        JOIN course_offering_eligibilities coe
             ON coe.curriculum_course_id = cc.curriculum_course_id
        JOIN course_offerings co
             ON co.course_offering_id = coe.course_offering_id
            AND co.course_id = c.course_id
            AND co.academic_period_id = CAST(:period_id AS uuid)
        JOIN offering_components oc
             ON oc.course_offering_id = co.course_offering_id
        JOIN class_sections cs
             ON cs.offering_component_id = oc.offering_component_id
        WHERE dp.status = 'active'
          AND cc.curriculum_id = sca.curriculum_id
          AND u.email IN (:tsd, :trkb, :rn, :ti, :te)
        """,
        {**_email_params(), "period_id": period_id},
    )
    codes: dict[str, set[str]] = {email: set() for email in DEMO_EMAILS.values()}
    for row in rows:
        codes[row["email"]].add(row["course_code"])
    return codes


def _login_headers(client, email: str) -> dict[str, str]:
    limiter.reset()
    response = client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": STUDENT_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _dashboard_codes(client, headers: dict[str, str]) -> set[str]:
    response = client.get(DASHBOARD_PATH, headers=headers)
    assert response.status_code == 200, response.text
    return {item["course_code"] for item in response.json()["schedule"]}


def _timetable_codes(client, headers: dict[str, str]) -> set[str]:
    response = client.get(TIMETABLE_PATH, headers=headers)
    assert response.status_code == 200, response.text
    return {item["course_code"] for item in response.json()["selections"]}


@pytest.mark.parametrize("code", DEMO_CODES)
def test_demo_student_schedule_matches_active_plan_sections(client, db_session, code):
    email = DEMO_EMAILS[code]
    period = _active_period(client, db_session)
    plan_terms = _plan_terms_by_email(client, db_session)[email]
    expected = _schedulable_codes_by_email(client, db_session, period["id"])[email]

    assert plan_terms, email
    assert expected, email

    headers = _login_headers(client, email)
    dashboard_codes = _dashboard_codes(client, headers)
    timetable_codes = _timetable_codes(client, headers)

    assert dashboard_codes == expected, (email, dashboard_codes, expected)
    assert timetable_codes == expected, (email, timetable_codes, expected)


@pytest.mark.parametrize("code", DEMO_CODES)
def test_demo_timetable_follows_active_period_term(client, db_session, code):
    email = DEMO_EMAILS[code]
    period = _active_period(client, db_session)
    plan_terms = _plan_terms_by_email(client, db_session)[email]
    selected_codes = _timetable_codes(client, _login_headers(client, email))

    assert selected_codes, email
    assert selected_codes <= set(plan_terms), (email, selected_codes, plan_terms)
    assert all(plan_terms[course] == period["term"] for course in selected_codes), (
        email,
        selected_codes,
        period["term"],
    )


def test_rn_timetable_includes_all_plan_courses(client, db_session):
    email = DEMO_EMAILS["RN"]
    period = _active_period(client, db_session)
    plan_terms = _plan_terms_by_email(client, db_session)[email]
    expected = _schedulable_codes_by_email(client, db_session, period["id"])[email]

    assert len(plan_terms) == 6, plan_terms
    assert set(plan_terms) == expected, (plan_terms, expected)

    headers = _login_headers(client, email)
    assert _dashboard_codes(client, headers) == set(plan_terms)
    assert _timetable_codes(client, headers) == set(plan_terms)
