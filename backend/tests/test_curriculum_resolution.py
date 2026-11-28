import uuid

from sqlalchemy import text

from catalog import cohort_curriculum_id


def test_cohort_curriculum_uses_admission_year(client, db_session):
    suffix = uuid.uuid4().hex[:8]

    async def setup():
        program_id = await db_session.scalar(
            text(
                "INSERT INTO study_programs (program_code, program_name, degree_level) "
                "VALUES (:code, :name, 'sarjana') RETURNING study_program_id"
            ),
            {"code": f"CR{suffix}", "name": f"Prodi Kurikulum {suffix}"},
        )
        old_id = await db_session.scalar(
            text(
                "INSERT INTO curricula (study_program_id, curriculum_name, curriculum_year) "
                "VALUES (:program, :name, 2021) RETURNING curriculum_id"
            ),
            {"program": program_id, "name": f"Kurikulum 2021 {suffix}"},
        )
        new_id = await db_session.scalar(
            text(
                "INSERT INTO curricula (study_program_id, curriculum_name, curriculum_year) "
                "VALUES (:program, :name, 2025) RETURNING curriculum_id"
            ),
            {"program": program_id, "name": f"Kurikulum 2025 {suffix}"},
        )
        await db_session.execute(
            text(
                "INSERT INTO curriculum_cohort_rules "
                "(study_program_id, curriculum_id, admission_year_from, "
                "admission_year_to, priority) VALUES "
                "(:program, :old, 2021, 2024, 1), "
                "(:program, :new, 2025, NULL, 1)"
            ),
            {"program": program_id, "old": old_id, "new": new_id},
        )
        return program_id, old_id, new_id

    program_id, old_id, new_id = client.portal.call(setup)
    assert client.portal.call(
        cohort_curriculum_id, db_session, program_id, 2024
    ) == old_id
    assert client.portal.call(
        cohort_curriculum_id, db_session, program_id, 2026
    ) == new_id
