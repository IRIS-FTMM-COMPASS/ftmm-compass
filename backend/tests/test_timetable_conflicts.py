"""Kontrak pemakaian dan hasil deteksi v_timetable_conflicts."""

from pathlib import Path

from sqlalchemy import text

APP_ROOT = Path(__file__).resolve().parents[1]


def test_application_code_scopes_conflict_view_to_one_timetable():
    sources = list(APP_ROOT.glob("*.py")) + list((APP_ROOT / "api").glob("*.py"))
    for path in sources:
        body = path.read_text(encoding="utf-8")
        for occurrence in body.split("v_timetable_conflicts")[1:]:
            assert "timetable_id" in occurrence.split(";")[0], path.name


def test_view_pairs_match_independent_overlap_calculation(client, db_session):
    async def compare():
        active = (
            await db_session.execute(
                text(
                    """
                    SELECT t.timetable_id, ti.class_section_id
                    FROM timetables t
                    JOIN timetable_items ti USING (timetable_id)
                    WHERE t.is_active = true
                    ORDER BY ti.class_section_id
                    LIMIT 2
                    """
                )
            )
        ).all()
        if len(active) < 2:
            return

        timetable_id = active[0][0]
        for _, section_id in active:
            await db_session.execute(
                text(
                    """
                    INSERT INTO class_schedules
                        (class_section_id, day_of_week, start_time, end_time, room_name)
                    VALUES (:section, 1, '09:00', '10:30', 'Ruang Uji')
                    """
                ),
                {"section": section_id},
            )

        from_view = (
            await db_session.execute(
                text(
                    """
                    SELECT timetable_item_a_id, timetable_item_b_id
                    FROM v_timetable_conflicts WHERE timetable_id = :tid
                    """
                ),
                {"tid": timetable_id},
            )
        ).all()
        independent = (
            await db_session.execute(
                text(
                    """
                    SELECT a.timetable_item_id, b.timetable_item_id
                    FROM timetable_items a
                    JOIN timetable_items b
                      ON b.timetable_id = a.timetable_id
                     AND b.timetable_item_id > a.timetable_item_id
                    JOIN class_schedules sa ON sa.class_section_id = a.class_section_id
                    JOIN class_schedules sb
                      ON sb.class_section_id = b.class_section_id
                     AND sb.day_of_week = sa.day_of_week
                     AND sa.start_time < sb.end_time
                     AND sb.start_time < sa.end_time
                    WHERE a.timetable_id = :tid
                    """
                ),
                {"tid": timetable_id},
            )
        ).all()

        assert from_view
        assert {tuple(row) for row in from_view} == {tuple(row) for row in independent}

    client.portal.call(compare)
