"""Deterministic, insert-only demo scheduling inputs and one scheduler run."""

import json
from pathlib import Path

import pytest
from sqlalchemy import text

from scheduling_assignment_rules import snake_candidate_index, snake_order
from scripts import seed as seed_module

DEMO_CODES = ("TSD", "TRKB", "RN", "TI", "TE")
DEMO_ROSTER_PATH = Path(__file__).resolve().parents[2] / "database" / "seed" / "lecturers.json"
DEMO_ROSTER = json.loads(DEMO_ROSTER_PATH.read_text(encoding="utf-8"))["lecturers"]
DEMO_EMAILS = tuple(item["email"] for item in DEMO_ROSTER)


def _rows(client, db_session, sql: str, params: dict | None = None) -> list[dict]:
    async def run():
        result = await db_session.execute(text(sql), params or {})
        return [dict(row) for row in result.mappings().all()]

    return client.portal.call(run)


def _period(client, db_session) -> dict:
    return _rows(
        client,
        db_session,
        "SELECT academic_period_id AS id FROM academic_periods WHERE is_active",
    )[0]


def _reseed(client, db_session, monkeypatch) -> None:
    class _BoundSession:
        async def __aenter__(self):
            return db_session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(seed_module, "AsyncSessionLocal", lambda: _BoundSession())
    client.portal.call(seed_module.seed_data)


@pytest.mark.parametrize(
    ("pool_size", "expected"),
    [
        (0, []),
        (1, [0, 0, 0, 0]),
        (2, [0, 1, 1, 0]),
        (4, [0, 1, 2, 3, 3, 2, 1, 0]),
        (5, [0, 1, 2, 3, 4, 4, 3, 2, 1, 0]),
    ],
)
def test_snake_candidate_index_is_deterministic(pool_size, expected):
    assert [snake_candidate_index(pool_size, index) for index in range(len(expected))] == expected
    assert snake_candidate_index(pool_size, -1) is None


def test_snake_class_order_matches_assignment_preview():
    assert snake_order(["A", "B", "C", "D"]) == ["A", "D", "C", "B"]
    assert snake_order([]) == []


def test_demo_preferences_cover_all_lecturers_in_five_programs(client, db_session):
    period = _period(client, db_session)
    email_placeholders = ", ".join(f":email{index}" for index in range(len(DEMO_EMAILS)))
    params = {
        "period": period["id"],
        **{f"email{index}": email for index, email in enumerate(DEMO_EMAILS)},
    }
    coverage = _rows(
        client,
        db_session,
        f"""
        SELECT sp.program_code,
               count(DISTINCT u.user_id) AS lecturers,
               count(DISTINCT p.user_id) AS preferred_lecturers
        FROM users u
        JOIN lecturer_profiles lp ON lp.user_id = u.user_id
        JOIN study_programs sp ON sp.study_program_id = lp.study_program_id
        LEFT JOIN lecturer_schedule_preferences p
          ON p.user_id = u.user_id
         AND p.academic_period_id = CAST(:period AS uuid)
         AND p.kind = 'preferred'
        WHERE u.role = 'lecturer' AND u.is_active
          AND u.email IN ({email_placeholders})
          AND sp.program_code IN ('TSD', 'TRKB', 'RN', 'TI', 'TE')
        GROUP BY sp.program_code
        """,
        params,
    )
    assert {row["program_code"] for row in coverage} == set(DEMO_CODES)
    assert all(
        row["lecturers"] > 0 and row["preferred_lecturers"] == row["lecturers"]
        for row in coverage
    )


def test_demo_period_mappings_have_one_account_backed_pjmk_per_course(client, db_session):
    period = _period(client, db_session)
    coverage = _rows(
        client,
        db_session,
        """
        SELECT sp.program_code,
               count(DISTINCT cc.curriculum_course_id) AS courses,
               count(*) FILTER (WHERE r.instructor_role = 'pjmk') AS pjmk
        FROM course_instructor_references r
        JOIN curriculum_courses cc ON cc.curriculum_course_id = r.curriculum_course_id
        JOIN curricula c ON c.curriculum_id = cc.curriculum_id
        JOIN study_programs sp ON sp.study_program_id = c.study_program_id
        WHERE r.academic_period_id = CAST(:period AS uuid)
          AND c.is_active AND cc.is_active
          AND sp.program_code IN ('TSD', 'TRKB', 'RN', 'TI', 'TE')
        GROUP BY sp.program_code
        """,
        {"period": period["id"]},
    )
    assert "TSD" in {row["program_code"] for row in coverage}
    assert all(row["courses"] > 0 and row["pjmk"] == row["courses"] for row in coverage)
    invalid = _rows(
        client,
        db_session,
        """
        SELECT count(*) AS n
        FROM course_instructor_references r
        JOIN users u ON u.user_id = r.user_id
        WHERE r.academic_period_id = CAST(:period AS uuid)
          AND r.instructor_role IN ('pjmk', 'teaching_team')
          AND (u.role != 'lecturer' OR NOT u.is_active)
        """,
        {"period": period["id"]},
    )
    assert invalid[0]["n"] == 0



def test_reseed_rebuilds_missing_demo_inputs_after_offerings_exist(
    client, db_session, monkeypatch
):
    period = _period(client, db_session)

    async def clear_demo_inputs():
        await db_session.execute(
            text(
                "DELETE FROM class_instructor_assignments "
                "WHERE academic_period_id = :period"
            ),
            {"period": period["id"]},
        )
        await db_session.execute(
            text(
                "DELETE FROM course_instructor_references "
                "WHERE academic_period_id = :period"
            ),
            {"period": period["id"]},
        )
        await db_session.execute(
            text(
                "DELETE FROM lecturer_schedule_preferences "
                "WHERE academic_period_id = :period"
            ),
            {"period": period["id"]},
        )

    client.portal.call(clear_demo_inputs)
    _reseed(client, db_session, monkeypatch)
    counts = _rows(
        client,
        db_session,
        """
        SELECT
          (SELECT count(*) FROM lecturer_schedule_preferences
           WHERE academic_period_id = CAST(:period AS uuid)) AS preferences,
          (SELECT count(*) FROM course_instructor_references
           WHERE academic_period_id = CAST(:period AS uuid)) AS mappings,
          (SELECT count(*) FROM class_instructor_assignments
           WHERE academic_period_id = CAST(:period AS uuid)) AS assignments
        """,
        {"period": period["id"]},
    )[0]
    assert all(counts[name] > 0 for name in ("preferences", "mappings", "assignments"))


def test_demo_assignments_use_snake_order_for_parallel_classes(
    client, db_session, monkeypatch
):
    period = _period(client, db_session)
    target = _rows(
        client,
        db_session,
        """
        SELECT oc.offering_component_id, cc.curriculum_course_id
        FROM offering_components oc
        JOIN course_offerings o ON o.course_offering_id = oc.course_offering_id
        JOIN course_offering_eligibilities e ON e.course_offering_id = o.course_offering_id
        JOIN curriculum_courses cc ON cc.curriculum_course_id = e.curriculum_course_id
        JOIN course_instructor_references r ON r.curriculum_course_id = cc.curriculum_course_id
        WHERE o.academic_period_id = CAST(:period AS uuid)
          AND r.academic_period_id = CAST(:period AS uuid)
          AND r.instructor_role IN ('pjmk', 'teaching_team')
          AND r.user_id IS NOT NULL
        GROUP BY oc.offering_component_id, cc.curriculum_course_id
        HAVING count(DISTINCT r.user_id) >= 3
           AND count(DISTINCT cc.curriculum_course_id) = 1
        ORDER BY oc.offering_component_id
        LIMIT 1
        """,
        {"period": period["id"]},
    )[0]

    async def add_parallel_classes():
        existing = set(
            (
                await db_session.execute(
                    text(
                        "SELECT section_code FROM class_sections "
                        "WHERE offering_component_id = :component"
                    ),
                    {"component": target["offering_component_id"]},
                )
            ).scalars()
        )
        for code in ("A", "B", "C"):
            if code not in existing:
                await db_session.execute(
                    text(
                        "INSERT INTO class_sections "
                        "(offering_component_id, section_code, capacity, enrollment_status) "
                        "VALUES (:component, :code, 40, 'open')"
                    ),
                    {"component": target["offering_component_id"], "code": code},
                )
        await db_session.execute(
            text(
                "DELETE FROM class_instructor_assignments WHERE class_section_id IN "
                "(SELECT class_section_id FROM class_sections "
                " WHERE offering_component_id = :component)"
            ),
            {"component": target["offering_component_id"]},
        )

    client.portal.call(add_parallel_classes)
    _reseed(client, db_session, monkeypatch)
    sections = _rows(
        client,
        db_session,
        """
        SELECT class_section_id,
               row_number() OVER (
                   ORDER BY section_code, class_section_id
               ) AS pos
        FROM class_sections
        WHERE offering_component_id = CAST(:component AS uuid)
        """,
        {"component": target["offering_component_id"]},
    )
    total_sections = len(sections)
    position_by_class = {row["class_section_id"]: row["pos"] for row in sections}

    def snake_index(pos):
        k = 0 if pos == 1 else total_sections - pos + 1
        return snake_candidate_index(len(pool), k)

    classes = _rows(
        client,
        db_session,
        """
        WITH ordered AS (
            SELECT cs.class_section_id, cs.section_code,
                   row_number() OVER (ORDER BY cs.section_code, cs.class_section_id) AS pos
            FROM class_sections cs
            WHERE cs.offering_component_id = CAST(:component AS uuid)
        )
        SELECT cs.class_section_id, a.user_id
        FROM ordered cs
        LEFT JOIN class_instructor_assignments a ON a.class_section_id = cs.class_section_id
        WHERE pos <= 3
        ORDER BY CASE pos WHEN 1 THEN 1 WHEN 2 THEN 3 ELSE 2 END
        """,
        {"component": target["offering_component_id"]},
    )
    pool = _rows(
        client,
        db_session,
        """
        WITH eligible_courses AS (
            SELECT DISTINCT cc.curriculum_course_id
            FROM offering_components oc
            JOIN course_offerings o ON o.course_offering_id = oc.course_offering_id
            JOIN course_offering_eligibilities e ON e.course_offering_id = o.course_offering_id
            JOIN curriculum_courses cc ON cc.curriculum_course_id = e.curriculum_course_id
            JOIN curricula cur ON cur.curriculum_id = cc.curriculum_id
            JOIN study_programs sp ON sp.study_program_id = cur.study_program_id
            JOIN courses c ON c.course_id = cc.course_id
            WHERE oc.offering_component_id = CAST(:component AS uuid)
              AND o.academic_period_id = CAST(:period AS uuid)
              AND c.is_active
        ),
        ranked AS (
            SELECT DISTINCT ON (r.user_id)
                   r.user_id,
                   (r.instructor_role <> 'pjmk') AS not_pjmk,
                   COALESCE(r.position, 10000) AS position_rank,
                   u.email
            FROM course_instructor_references r
            JOIN eligible_courses ec ON ec.curriculum_course_id = r.curriculum_course_id
            JOIN users u ON u.user_id = r.user_id
            JOIN lecturer_profiles lp ON lp.user_id = u.user_id
            WHERE r.academic_period_id = CAST(:period AS uuid)
              AND r.instructor_role IN ('pjmk', 'teaching_team')
              AND u.role = 'lecturer' AND u.is_active
            ORDER BY r.user_id, (r.instructor_role <> 'pjmk'),
                     COALESCE(r.position, 10000), u.email
        )
        SELECT user_id
        FROM ranked
        ORDER BY not_pjmk, position_rank, email, user_id
        """,
        {"component": target["offering_component_id"], "period": period["id"]},
    )
    assert [row["user_id"] for row in classes] == [
        pool[snake_index(position_by_class[row["class_section_id"]])]["user_id"]
        for row in classes
    ]


def test_reseed_preserves_user_preferences_mappings_and_assignments(
    client, db_session, monkeypatch
):
    period = _period(client, db_session)

    async def edit_user_inputs():
        await db_session.execute(
            text(
                "UPDATE lecturer_schedule_preferences SET start_time = TIME '09:00', "
                "end_time = TIME '11:00' WHERE preference_id = ("
                " SELECT preference_id FROM lecturer_schedule_preferences "
                " WHERE academic_period_id = :period LIMIT 1)"
            ),
            {"period": period["id"]},
        )
        await db_session.execute(
            text(
                "UPDATE course_instructor_references SET instructor_name = 'User-owned mapping' "
                "WHERE instructor_reference_id = ("
                " SELECT instructor_reference_id FROM course_instructor_references "
                " WHERE academic_period_id = :period LIMIT 1)"
            ),
            {"period": period["id"]},
        )
        await db_session.execute(
            text(
                "UPDATE class_instructor_assignments SET source = 'manual', is_pinned = true "
                "WHERE assignment_id = ("
                " SELECT assignment_id FROM class_instructor_assignments "
                " WHERE academic_period_id = :period LIMIT 1)"
            ),
            {"period": period["id"]},
        )

    client.portal.call(edit_user_inputs)

    def snapshot():
        return {
            "preferences": _rows(
                client,
                db_session,
                "SELECT preference_id, user_id, day_of_week, start_time, end_time, kind "
                "FROM lecturer_schedule_preferences WHERE academic_period_id = CAST(:p AS uuid) "
                "ORDER BY preference_id",
                {"p": period["id"]},
            ),
            "mappings": _rows(
                client,
                db_session,
                "SELECT instructor_reference_id, curriculum_course_id, instructor_name, "
                "instructor_role, user_id, position, source_reference_id "
                "FROM course_instructor_references WHERE academic_period_id = CAST(:p AS uuid) "
                "ORDER BY instructor_reference_id",
                {"p": period["id"]},
            ),
            "global_mappings": _rows(
                client,
                db_session,
                "SELECT instructor_reference_id, curriculum_course_id, instructor_name, "
                "instructor_role, user_id, source_reference_id "
                "FROM course_instructor_references WHERE academic_period_id IS NULL "
                "ORDER BY instructor_reference_id",
            ),
            "assignments": _rows(
                client,
                db_session,
                "SELECT assignment_id, class_section_id, user_id, source, is_pinned, is_active "
                "FROM class_instructor_assignments WHERE academic_period_id = CAST(:p AS uuid) "
                "ORDER BY assignment_id",
                {"p": period["id"]},
            ),
        }

    before = snapshot()
    _reseed(client, db_session, monkeypatch)
    _reseed(client, db_session, monkeypatch)
    assert snapshot() == before


def test_reseed_preserves_legacy_and_migrated_reference_provenance(
    client, db_session, monkeypatch
):
    period = _period(client, db_session)
    course = _rows(
        client,
        db_session,
        "SELECT curriculum_course_id FROM curriculum_courses LIMIT 1",
    )[0]["curriculum_course_id"]

    async def create_migrated_pair():
        legacy_id = (
            await db_session.execute(
                text(
                    "INSERT INTO course_instructor_references "
                    "(curriculum_course_id, instructor_name, instructor_role) "
                    "VALUES (:course, 'Legacy provenance source', 'teaching_team') "
                    "RETURNING instructor_reference_id"
                ),
                {"course": course},
            )
        ).scalar()
        await db_session.execute(
            text(
                "INSERT INTO course_instructor_references "
                "(curriculum_course_id, academic_period_id, instructor_name, instructor_role, "
                " position, source_reference_id) "
                "VALUES (:course, :period, 'Legacy provenance source', 'teaching_team', 999, :source)"
            ),
            {"course": course, "period": period["id"], "source": legacy_id},
        )

    client.portal.call(create_migrated_pair)

    def provenance():
        return _rows(
            client,
            db_session,
            """
            SELECT p.instructor_reference_id AS period_id,
                   s.instructor_reference_id AS source_id,
                   p.source_reference_id, p.instructor_name, p.position
            FROM course_instructor_references p
            JOIN course_instructor_references s ON s.instructor_reference_id = p.source_reference_id
            WHERE p.academic_period_id = CAST(:period AS uuid)
              AND p.instructor_name = 'Legacy provenance source'
            """,
            {"period": period["id"]},
        )

    before = provenance()
    _reseed(client, db_session, monkeypatch)
    assert provenance() == before
    assert len(before) == 1


def test_seed_runs_scheduler_once_after_every_class_assignment_exists(client, db_session, monkeypatch):
    period = _period(client, db_session)

    async def clear_runs():
        await db_session.execute(
            text("DELETE FROM schedule_runs WHERE academic_period_id = :period"),
            {"period": period["id"]},
        )
        await db_session.commit()

    client.portal.call(clear_runs)
    original = seed_module.generate_schedule
    calls = 0

    async def checked_generate(db, active_period, *, mode, triggered_by):
        nonlocal calls
        calls += 1
        missing = (
            await db.execute(
                text(
                    """
                    SELECT count(*)
                    FROM class_sections cs
                    JOIN offering_components oc ON oc.offering_component_id = cs.offering_component_id
                    JOIN course_offerings o ON o.course_offering_id = oc.course_offering_id
                    JOIN course_offering_eligibilities e ON e.course_offering_id = o.course_offering_id
                    JOIN curriculum_courses cc ON cc.curriculum_course_id = e.curriculum_course_id
                    JOIN courses c ON c.course_id = cc.course_id
                    LEFT JOIN class_instructor_assignments a ON a.class_section_id = cs.class_section_id
                    WHERE o.academic_period_id = :period
                      AND c.is_active
                      AND EXISTS (
                          SELECT 1 FROM course_instructor_references r
                          JOIN users u ON u.user_id = r.user_id
                          WHERE r.curriculum_course_id = cc.curriculum_course_id
                            AND r.academic_period_id = :period
                            AND r.instructor_role IN ('pjmk', 'teaching_team')
                            AND u.role = 'lecturer' AND u.is_active
                      )
                      AND a.assignment_id IS NULL
                    """
                ),
                {"period": active_period.academic_period_id},
            )
        ).scalar_one()
        assert missing == 0
        return await original(db, active_period, mode=mode, triggered_by=triggered_by)

    monkeypatch.setattr(seed_module, "generate_schedule", checked_generate)
    _reseed(client, db_session, monkeypatch)
    _reseed(client, db_session, monkeypatch)
    assert calls == 1
    runs = _rows(
        client,
        db_session,
        "SELECT status FROM schedule_runs WHERE academic_period_id = CAST(:p AS uuid)",
        {"p": period["id"]},
    )
    assert len(runs) == 1 and runs[0]["status"] == "completed"


def test_demo_roster_covers_five_programs():
    assert {item["prodi_code"] for item in DEMO_ROSTER} == set(DEMO_CODES)
    assert all(
        sum(item["prodi_code"] == code for item in DEMO_ROSTER) >= 3
        for code in DEMO_CODES
    )
