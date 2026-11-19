"""Integrasi seeder: rencana studi aktif mahasiswa demo TI/TE/TRKB/TSD/RN."""

import pytest
from sqlalchemy import text

from rate_limit import limiter

DEMO_EMAILS = {
    code: f"mahasiswa.{code.lower()}@ftmm.unair.ac.id"
    for code in ("TSD", "TRKB", "RN", "TI", "TE")
}
STUDENT_PASSWORD = "Mahasiswa2026!"
MIN_ITEM_COUNTS = {"TRKB": 4, "TI": 4, "TE": 4}
CATALOG_PATH = "/api/v1/degree-plans/catalog"


def _rows(client, db_session, sql: str, params: dict | None = None) -> list[dict]:
    async def run():
        result = await db_session.execute(text(sql), params or {})
        return [dict(row) for row in result.mappings().all()]

    return client.portal.call(run)


def _demo_email_params() -> dict[str, str]:
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


def test_demo_students_have_one_active_plan_with_items(client, db_session):
    rows = _rows(
        client,
        db_session,
        """
        SELECT u.email,
               COUNT(DISTINCT dp.degree_plan_id) AS active_plans,
               COUNT(dpi.degree_plan_item_id) AS item_count
        FROM users u
        LEFT JOIN degree_plans dp
               ON dp.user_id = u.user_id AND dp.status = 'active'
        LEFT JOIN degree_plan_items dpi ON dpi.degree_plan_id = dp.degree_plan_id
        WHERE u.email IN (:tsd, :trkb, :rn, :ti, :te)
        GROUP BY u.email
        """,
        _demo_email_params(),
    )
    by_email = {row["email"]: row for row in rows}
    assert set(by_email) == set(DEMO_EMAILS.values())

    for code, email in DEMO_EMAILS.items():
        row = by_email[email]
        assert row["active_plans"] == 1, email
        assert row["item_count"] >= 1, email
        if code in MIN_ITEM_COUNTS:
            assert row["item_count"] >= MIN_ITEM_COUNTS[code], email


def test_demo_plan_items_follow_current_curriculum_and_active_period(
    client, db_session
):
    period = _active_period(client, db_session)
    rows = _rows(
        client,
        db_session,
        """
        SELECT u.email,
               c.course_code,
               dpi.planned_semester,
               cc.term AS course_term,
               cc.curriculum_id::text AS item_curriculum_id,
               sca.curriculum_id::text AS assigned_curriculum_id,
               sca.is_current
        FROM degree_plan_items dpi
        JOIN degree_plans dp ON dp.degree_plan_id = dpi.degree_plan_id
        JOIN users u ON u.user_id = dp.user_id
        JOIN curriculum_courses cc
             ON cc.curriculum_course_id = dpi.curriculum_course_id
        JOIN courses c ON c.course_id = cc.course_id
        JOIN student_curriculum_assignments sca
             ON sca.student_curriculum_assignment_id
                = dp.student_curriculum_assignment_id
        WHERE dp.status = 'active'
          AND u.email IN (:tsd, :trkb, :rn, :ti, :te)
        """,
        _demo_email_params(),
    )
    assert rows

    seeded_by_us = {
        DEMO_EMAILS[code] for code in ("TRKB", "TI", "TE")
    }
    for row in rows:
        assert row["is_current"] is True, row
        assert row["item_curriculum_id"] == row["assigned_curriculum_id"], row
        if row["email"] not in seeded_by_us:
            continue
        assert row["course_term"] == period["term"], row
        expected_term = "ganjil" if row["planned_semester"] % 2 else "genap"
        assert expected_term == period["term"], row


def test_demo_plan_courses_have_class_sections_in_active_period(client, db_session):
    period = _active_period(client, db_session)
    rows = _rows(
        client,
        db_session,
        """
        SELECT u.email, c.course_code, COUNT(cs.class_section_id) AS section_count
        FROM degree_plan_items dpi
        JOIN degree_plans dp ON dp.degree_plan_id = dpi.degree_plan_id
        JOIN users u ON u.user_id = dp.user_id
        JOIN curriculum_courses cc
             ON cc.curriculum_course_id = dpi.curriculum_course_id
        JOIN courses c ON c.course_id = cc.course_id
        LEFT JOIN course_offerings co
               ON co.course_id = c.course_id
              AND co.academic_period_id = CAST(:period_id AS uuid)
        LEFT JOIN offering_components oc
               ON oc.course_offering_id = co.course_offering_id
        LEFT JOIN class_sections cs
               ON cs.offering_component_id = oc.offering_component_id
        WHERE dp.status = 'active'
          AND u.email IN (:tsd, :trkb, :rn, :ti, :te)
        GROUP BY u.email, c.course_code
        """,
        {**_demo_email_params(), "period_id": period["id"]},
    )
    assert rows
    for row in rows:
        assert row["section_count"] > 0, row


@pytest.mark.parametrize("code", ["TI", "TE"])
def test_demo_student_can_open_planner_catalog(client, code):
    limiter.reset()
    login = client.post(
        "/api/v1/auth/login",
        json={"identifier": DEMO_EMAILS[code], "password": STUDENT_PASSWORD},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.get(CATALOG_PATH, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["data"]
