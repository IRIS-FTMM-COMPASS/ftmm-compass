"""Transactional integration tests for the legacy scheduling data migration."""

from importlib import import_module
from datetime import time
import uuid

import pytest
from sqlalchemy import func, select, text

from models import (
    AcademicPeriod,
    CourseInstructorReference,
    CurriculumCourse,
    LecturerProfile,
    LecturerSchedulePreference,
    SchedulePeriodSettings,
    User,
)
from scheduling_legacy_migration import (
    ActivePeriodAmbiguityError,
    ActivePeriodMismatchError,
    LegacyPreferenceConflictError,
    rollback_legacy_scheduling,
    upgrade_legacy_scheduling,
)

AVAILABILITY_MAP = "legacy_availability_migration_map"
REFERENCE_MAP = "legacy_instructor_reference_migration_map"
STATE_TABLE = "scheduling_legacy_migration_state"


@pytest.fixture
def migration_case(client, db_session):
    async def setup():
        await db_session.execute(text(f"DELETE FROM {REFERENCE_MAP}"))
        await db_session.execute(text(f"DELETE FROM {AVAILABILITY_MAP}"))
        await db_session.execute(text(f"DELETE FROM {STATE_TABLE}"))
        await db_session.execute(text("DELETE FROM lecturer_schedule_preferences"))
        await db_session.execute(text("DELETE FROM course_instructor_references"))
        await db_session.execute(text("DELETE FROM lecturer_availability"))
        await db_session.execute(text("UPDATE academic_periods SET is_active = FALSE"))

        last_year = (
            await db_session.execute(select(func.max(AcademicPeriod.academic_year_start)))
        ).scalar_one()
        active = AcademicPeriod(
            academic_year_start=last_year + 1,
            semester_number=1,
            term="ganjil",
            is_active=True,
        )
        other = AcademicPeriod(
            academic_year_start=last_year + 2,
            semester_number=1,
            term="ganjil",
            is_active=False,
        )
        db_session.add_all([active, other])
        await db_session.flush()

        lecturers = (
            (
                await db_session.execute(
                    select(User)
                    .join(LecturerProfile, LecturerProfile.user_id == User.user_id)
                    .order_by(User.user_id)
                    .limit(2)
                )
            )
            .scalars()
            .all()
        )
        courses = (
            (
                await db_session.execute(
                    select(CurriculumCourse).order_by(CurriculumCourse.curriculum_course_id).limit(2)
                )
            )
            .scalars()
            .all()
        )
        assert len(lecturers) == 2
        assert len(courses) == 2

        source_document_id = uuid.uuid4()
        await db_session.execute(
            text(
                """
                INSERT INTO source_documents (
                    source_document_id, document_title, document_type, academic_year_label
                ) VALUES (
                    :source_document_id, 'T04 migration fixture', 'dataset_extract', '2026/2027'
                )
                """
            ),
            {"source_document_id": source_document_id},
        )
        await db_session.commit()
        return {
            "active_id": active.academic_period_id,
            "other_id": other.academic_period_id,
            "lecturer_ids": [lecturer.user_id for lecturer in lecturers],
            "course_ids": [course.curriculum_course_id for course in courses],
            "source_document_id": source_document_id,
        }

    return client.portal.call(setup)


async def _seed_legacy(
    db_session,
    case,
    *,
    availability: list[tuple[int, int, int, int]] | None = None,
    references: list[tuple[int, str, str, int | None]] | None = None,
):
    if availability is None:
        availability = [(0, 1, 8, 10), (0, 2, 13, 15)]
    if references is None:
        references = [
            (0, "Dr. Dosen Satu, Ph.D.", "pjmk", 0),
            (1, "Dosen Dua", "teaching_team", 1),
        ]
    availability_ids = []
    for lecturer_index, day, start, end in availability:
        availability_id = uuid.uuid4()
        await db_session.execute(
            text(
                "INSERT INTO lecturer_availability "
                "(availability_id, user_id, day_of_week, start_hour, end_hour) "
                "VALUES (:availability_id, :user_id, :day_of_week, :start_hour, :end_hour)"
            ),
            {
                "availability_id": availability_id,
                "user_id": case["lecturer_ids"][lecturer_index],
                "day_of_week": day,
                "start_hour": start,
                "end_hour": end,
            },
        )
        availability_ids.append(availability_id)
    reference_ids = []
    for course_index, name, role, lecturer_index in references:
        row = CourseInstructorReference(
            curriculum_course_id=case["course_ids"][course_index],
            source_document_id=case["source_document_id"],
            instructor_name=name,
            instructor_role=role,
            user_id=(
                case["lecturer_ids"][lecturer_index]
                if lecturer_index is not None
                else None
            ),
        )
        db_session.add(row)
        await db_session.flush()
        reference_ids.append(row.instructor_reference_id)
    await db_session.commit()
    return {"availability_ids": availability_ids, "reference_ids": reference_ids}


async def _period_preferences(db_session, period_id):
    result = await db_session.execute(
        select(LecturerSchedulePreference)
        .where(LecturerSchedulePreference.academic_period_id == period_id)
        .order_by(
            LecturerSchedulePreference.day_of_week,
            LecturerSchedulePreference.start_time,
        )
    )
    return result.scalars().all()


async def _period_references(db_session, period_id):
    result = await db_session.execute(
        select(CourseInstructorReference)
        .where(CourseInstructorReference.academic_period_id == period_id)
        .order_by(
            CourseInstructorReference.instructor_role,
            CourseInstructorReference.instructor_name,
        )
    )
    return result.scalars().all()


async def _legacy_snapshot(db_session):
    availability = (
        await db_session.execute(
            text(
                "SELECT availability_id, user_id, day_of_week, start_hour, end_hour "
                "FROM lecturer_availability ORDER BY availability_id"
            )
        )
    ).mappings().all()
    references = (
        (
            await db_session.execute(
                select(
                    CourseInstructorReference.instructor_reference_id,
                    CourseInstructorReference.curriculum_course_id,
                    CourseInstructorReference.source_document_id,
                    CourseInstructorReference.instructor_name,
                    CourseInstructorReference.instructor_role,
                    CourseInstructorReference.user_id,
                )
                .where(CourseInstructorReference.academic_period_id.is_(None))
                .order_by(CourseInstructorReference.instructor_reference_id)
            )
        )
        .all()
    )
    return availability, references


def test_copy_counts_payloads_and_revision_are_preserved(client, db_session, migration_case):
    case = migration_case

    async def scenario():
        await _seed_legacy(db_session, case)
        settings = SchedulePeriodSettings(
            academic_period_id=case["active_id"], input_revision=7
        )
        db_session.add(settings)
        await db_session.commit()
        before = await _legacy_snapshot(db_session)
        connection = await db_session.connection()
        result = await connection.run_sync(upgrade_legacy_scheduling)

        assert result.status == "completed"
        assert result.academic_period_id == case["active_id"]
        assert result.availability_sources == result.availability_inserted == 2
        assert result.reference_sources == result.references_inserted == 2
        assert result.availability_skipped_existing == result.references_skipped_existing == 0
        assert result.availability_conflicts == result.references_conflicts == 0
        assert result.provenance_copied == 4
        assert result.provenance_skipped == 0
        assert result.integrity_errors == ()

        preferences = await _period_preferences(db_session, case["active_id"])
        assert [(row.day_of_week, row.start_time, row.end_time, row.kind) for row in preferences] == [
            (1, time(8), time(10), "preferred"),
            (2, time(13), time(15), "preferred"),
        ]
        references = await _period_references(db_session, case["active_id"])
        assert [(row.instructor_name, row.instructor_role, row.user_id) for row in references] == [
            ("Dr. Dosen Satu, Ph.D.", "pjmk", case["lecturer_ids"][0]),
            ("Dosen Dua", "teaching_team", case["lecturer_ids"][1]),
        ]
        assert all(row.source_document_id == case["source_document_id"] for row in references)
        assert await _legacy_snapshot(db_session) == before

        persisted_settings = (
            await db_session.execute(
                select(SchedulePeriodSettings).where(
                    SchedulePeriodSettings.academic_period_id == case["active_id"]
                )
            )
        ).scalar_one()
        assert persisted_settings.input_revision == 7
        fingerprints = (
            await db_session.execute(
                text(
                    f"SELECT payload_fingerprint FROM {AVAILABILITY_MAP} "
                    f"UNION ALL SELECT payload_fingerprint FROM {REFERENCE_MAP}"
                )
            )
        ).scalars().all()
        assert len(fingerprints) == 4
        assert all(len(value) == 64 for value in fingerprints)
        return result

    result = client.portal.call(scenario)
    assert result.availability_rerun == result.references_rerun == 0


def test_repeat_run_is_stable_and_does_not_retarget(client, db_session, migration_case):
    case = migration_case

    async def scenario():
        await _seed_legacy(db_session, case)
        connection = await db_session.connection()
        first = await connection.run_sync(upgrade_legacy_scheduling)
        first_preferences = await _period_preferences(db_session, case["active_id"])
        first_references = await _period_references(db_session, case["active_id"])
        second = await connection.run_sync(upgrade_legacy_scheduling)

        assert first.availability_inserted == first.references_inserted == 2
        assert second.availability_inserted == second.references_inserted == 0
        assert second.availability_skipped_existing == second.references_skipped_existing == 0
        assert second.availability_conflicts == second.references_conflicts == 0
        assert second.availability_rerun == second.references_rerun == 2
        assert second.provenance_copied == 4
        assert second.integrity_errors == ()
        assert await _period_preferences(db_session, case["active_id"]) == first_preferences
        assert await _period_references(db_session, case["active_id"]) == first_references

        await db_session.execute(
            text("UPDATE academic_periods SET is_active = FALSE WHERE academic_period_id = :id"),
            {"id": case["active_id"]},
        )
        await db_session.execute(
            text("UPDATE academic_periods SET is_active = TRUE WHERE academic_period_id = :id"),
            {"id": case["other_id"]},
        )
        await db_session.flush()
        with pytest.raises(ActivePeriodMismatchError):
            await connection.run_sync(upgrade_legacy_scheduling)
        assert await _period_preferences(db_session, case["other_id"]) == []
        assert await _period_references(db_session, case["other_id"]) == []
        await db_session.execute(text("UPDATE academic_periods SET is_active = FALSE"))
        await db_session.flush()
        with pytest.raises(ActivePeriodMismatchError):
            await connection.run_sync(upgrade_legacy_scheduling)

    client.portal.call(scenario)


def test_equivalent_user_rows_are_skipped_and_never_claimed(client, db_session, migration_case):
    case = migration_case

    async def scenario():
        await _seed_legacy(db_session, case)
        existing_preference = LecturerSchedulePreference(
            user_id=case["lecturer_ids"][0],
            academic_period_id=case["active_id"],
            day_of_week=1,
            start_time=time(8),
            end_time=time(10),
            kind="preferred",
        )
        existing_reference = CourseInstructorReference(
            curriculum_course_id=case["course_ids"][1],
            academic_period_id=case["active_id"],
            source_document_id=case["source_document_id"],
            instructor_name="Nama Pengguna Berbeda",
            instructor_role="teaching_team",
            user_id=case["lecturer_ids"][1],
        )
        db_session.add_all([existing_preference, existing_reference])
        await db_session.commit()
        connection = await db_session.connection()
        result = await connection.run_sync(upgrade_legacy_scheduling)

        assert result.availability_inserted == 1
        assert result.availability_skipped_existing == 1
        assert result.references_inserted == 1
        assert result.references_skipped_existing == 1
        assert result.provenance_copied == 2
        assert result.provenance_skipped == 2
        skipped_preferences = (
            await db_session.execute(
                text(
                    f"SELECT preference_id, skip_reason FROM {AVAILABILITY_MAP} "
                    "WHERE status = 'skipped'"
                )
            )
        ).mappings().all()
        skipped_references = (
            await db_session.execute(
                text(
                    f"SELECT target_reference_id, skip_reason FROM {REFERENCE_MAP} "
                    "WHERE status = 'skipped'"
                )
            )
        ).mappings().all()
        assert skipped_preferences[0]["preference_id"] is None
        assert skipped_preferences[0]["skip_reason"] == "equivalent_preference"
        assert skipped_references[0]["target_reference_id"] is None
        assert skipped_references[0]["skip_reason"] == "equivalent_reference"
        rollback = await connection.run_sync(rollback_legacy_scheduling)
        assert rollback.preferences_deleted == rollback.references_deleted == 1
        remaining_preferences = await _period_preferences(db_session, case["active_id"])
        remaining_references = await _period_references(db_session, case["active_id"])
        assert [row.preference_id for row in remaining_preferences] == [existing_preference.preference_id]
        assert [row.instructor_reference_id for row in remaining_references] == [
            existing_reference.instructor_reference_id
        ]

    client.portal.call(scenario)


def test_pjmk_conflict_is_recorded_without_overwrite(client, db_session, migration_case):
    case = migration_case

    async def scenario():
        await _seed_legacy(db_session, case)
        existing = CourseInstructorReference(
            curriculum_course_id=case["course_ids"][0],
            academic_period_id=case["active_id"],
            instructor_name="PJ MK Pengguna",
            instructor_role="pjmk",
            user_id=case["lecturer_ids"][1],
        )
        db_session.add(existing)
        await db_session.commit()
        connection = await db_session.connection()
        result = await connection.run_sync(upgrade_legacy_scheduling)

        assert result.references_inserted == 1
        assert result.references_conflicts == 1
        assert result.references_skipped_existing == 0
        conflict = (
            await db_session.execute(
                text(f"SELECT status, skip_reason FROM {REFERENCE_MAP} WHERE status = 'skipped'")
            )
        ).mappings().one()
        assert conflict == {"status": "skipped", "skip_reason": "pjmk_conflict"}
        references = await _period_references(db_session, case["active_id"])
        pjmk = [row for row in references if row.instructor_role == "pjmk"]
        assert len(pjmk) == 1
        assert pjmk[0].instructor_reference_id == existing.instructor_reference_id
        assert pjmk[0].user_id == case["lecturer_ids"][1]

    client.portal.call(scenario)


def test_teaching_team_identity_conflict_is_not_duplicated(client, db_session, migration_case):
    case = migration_case

    async def scenario():
        await _seed_legacy(db_session, case)
        existing = CourseInstructorReference(
            curriculum_course_id=case["course_ids"][1],
            academic_period_id=case["active_id"],
            instructor_name="Dosen Dua",
            instructor_role="teaching_team",
            user_id=case["lecturer_ids"][0],
        )
        db_session.add(existing)
        await db_session.commit()
        connection = await db_session.connection()
        result = await connection.run_sync(upgrade_legacy_scheduling)

        assert result.references_inserted == 1
        assert result.references_conflicts == 1
        reason = (
            await db_session.execute(
                text(f"SELECT skip_reason FROM {REFERENCE_MAP} WHERE status = 'skipped'")
            )
        ).scalar_one()
        assert reason == "instructor_identity_conflict"
        team = [
            row
            for row in await _period_references(db_session, case["active_id"])
            if row.instructor_role == "teaching_team"
        ]
        assert len(team) == 1
        assert team[0].instructor_reference_id == existing.instructor_reference_id

    client.portal.call(scenario)


def test_legacy_overlap_preflight_fails_before_writes(client, db_session, migration_case):
    case = migration_case

    async def scenario():
        await _seed_legacy(
            db_session,
            case,
            availability=[(0, 1, 8, 10), (0, 1, 9, 11)],
            references=[],
        )
        connection = await db_session.connection()
        with pytest.raises(LegacyPreferenceConflictError) as raised:
            await connection.run_sync(upgrade_legacy_scheduling)
        conflicts = raised.value.conflicts
        assert len(conflicts) == 1
        assert conflicts[0].reason == "legacy_availability_overlap"
        assert conflicts[0].other_source_id is not None
        assert conflicts[0].other_start_hour in {8, 9}
        assert await _period_preferences(db_session, case["active_id"]) == []
        assert (
            await db_session.execute(text(f"SELECT count(*) FROM {STATE_TABLE}"))
        ).scalar_one() == 0
        assert (
            await db_session.execute(text(f"SELECT count(*) FROM {AVAILABILITY_MAP}"))
        ).scalar_one() == 0

    client.portal.call(scenario)


def test_existing_unavailable_overlap_fails_before_writes(client, db_session, migration_case):
    case = migration_case

    async def scenario():
        await _seed_legacy(
            db_session,
            case,
            availability=[(0, 1, 8, 10)],
            references=[],
        )
        unavailable = LecturerSchedulePreference(
            user_id=case["lecturer_ids"][0],
            academic_period_id=case["active_id"],
            day_of_week=1,
            start_time=time(9),
            end_time=time(11),
            kind="unavailable",
        )
        db_session.add(unavailable)
        await db_session.commit()
        connection = await db_session.connection()
        with pytest.raises(LegacyPreferenceConflictError) as raised:
            await connection.run_sync(upgrade_legacy_scheduling)
        conflict = raised.value.conflicts[0]
        assert conflict.reason == "existing_preference_overlap"
        assert conflict.other_preference_id == unavailable.preference_id
        assert conflict.other_kind == "unavailable"
        assert await _period_preferences(db_session, case["active_id"]) == [unavailable]
        assert (
            await db_session.execute(text(f"SELECT count(*) FROM {STATE_TABLE}"))
        ).scalar_one() == 0

    client.portal.call(scenario)


def test_deleted_copy_is_a_watermark_and_is_not_refilled(client, db_session, migration_case):
    case = migration_case

    async def scenario():
        await _seed_legacy(
            db_session,
            case,
            availability=[(0, 1, 8, 10)],
            references=[],
        )
        connection = await db_session.connection()
        first = await connection.run_sync(upgrade_legacy_scheduling)
        target = (await _period_preferences(db_session, case["active_id"]))[0]
        await db_session.delete(target)
        await db_session.flush()
        second = await connection.run_sync(upgrade_legacy_scheduling)

        assert first.availability_inserted == 1
        assert second.availability_inserted == 0
        assert second.availability_rerun == 1
        assert second.cleared_preference_copies == 1
        assert await _period_preferences(db_session, case["active_id"]) == []
        watermark = (
            await db_session.execute(
                text(
                    f"SELECT status, preference_id FROM {AVAILABILITY_MAP} "
                    "WHERE availability_id = :id"
                ),
                {"id": (await _legacy_snapshot(db_session))[0][0]["availability_id"]},
            )
        ).mappings().one()
        assert watermark == {"status": "copied", "preference_id": None}
        rollback = await connection.run_sync(rollback_legacy_scheduling)
        assert rollback.preferences_deleted == 0
        assert rollback.preferences_already_deleted == 1
        assert rollback.provenance_deleted == 1
        assert await _period_preferences(db_session, case["active_id"]) == []

    client.portal.call(scenario)


def test_rollback_preserves_edited_copies_and_user_rows(client, db_session, migration_case):
    case = migration_case

    async def scenario():
        await _seed_legacy(
            db_session,
            case,
            availability=[(0, 1, 8, 10)],
            references=[(0, "Dosen Satu", "pjmk", 0)],
        )
        connection = await db_session.connection()
        await connection.run_sync(upgrade_legacy_scheduling)
        preference = (await _period_preferences(db_session, case["active_id"]))[0]
        reference = (await _period_references(db_session, case["active_id"]))[0]
        preference.end_time = time(11)
        reference.instructor_name = "Nama Yang Diedit Pengguna"
        user_preference = LecturerSchedulePreference(
            user_id=case["lecturer_ids"][1],
            academic_period_id=case["active_id"],
            day_of_week=3,
            start_time=time(8),
            end_time=time(9),
            kind="preferred",
        )
        user_reference = CourseInstructorReference(
            curriculum_course_id=case["course_ids"][1],
            academic_period_id=case["active_id"],
            instructor_name="Anggota Pengguna",
            instructor_role="teaching_team",
            user_id=case["lecturer_ids"][1],
        )
        db_session.add_all([user_preference, user_reference])
        await db_session.commit()
        before_legacy = await _legacy_snapshot(db_session)
        rerun = await connection.run_sync(upgrade_legacy_scheduling)
        assert rerun.modified_preference_copies == rerun.modified_reference_copies == 1

        rollback = await connection.run_sync(rollback_legacy_scheduling)
        assert rollback.preferences_deleted == rollback.references_deleted == 0
        assert rollback.preferences_preserved_modified == 1
        assert rollback.references_preserved_modified == 1
        remaining_preferences = await _period_preferences(db_session, case["active_id"])
        remaining_references = await _period_references(db_session, case["active_id"])
        assert {row.preference_id for row in remaining_preferences} == {
            preference.preference_id,
            user_preference.preference_id,
        }
        assert {row.instructor_reference_id for row in remaining_references} == {
            reference.instructor_reference_id,
            user_reference.instructor_reference_id,
        }
        assert await _legacy_snapshot(db_session) == before_legacy

    client.portal.call(scenario)


def test_rollback_deletes_only_owned_unchanged_copies(client, db_session, migration_case):
    case = migration_case

    async def scenario():
        await _seed_legacy(db_session, case)
        connection = await db_session.connection()
        await connection.run_sync(upgrade_legacy_scheduling)
        user_preference = LecturerSchedulePreference(
            user_id=case["lecturer_ids"][1],
            academic_period_id=case["active_id"],
            day_of_week=3,
            start_time=time(8),
            end_time=time(9),
            kind="preferred",
        )
        user_reference = CourseInstructorReference(
            curriculum_course_id=case["course_ids"][0],
            academic_period_id=case["active_id"],
            instructor_name="Anggota Pengguna",
            instructor_role="teaching_team",
            user_id=case["lecturer_ids"][1],
        )
        db_session.add_all([user_preference, user_reference])
        await db_session.commit()
        before_legacy = await _legacy_snapshot(db_session)

        rollback = await connection.run_sync(rollback_legacy_scheduling)
        assert rollback.preferences_deleted == rollback.references_deleted == 2
        assert rollback.preferences_preserved_modified == rollback.references_preserved_modified == 0
        assert rollback.provenance_deleted == 4
        assert [row.preference_id for row in await _period_preferences(db_session, case["active_id"])] == [
            user_preference.preference_id
        ]
        assert [
            row.instructor_reference_id
            for row in await _period_references(db_session, case["active_id"])
        ] == [user_reference.instructor_reference_id]
        assert await _legacy_snapshot(db_session) == before_legacy

        second = await connection.run_sync(rollback_legacy_scheduling)
        assert second.preferences_deleted == second.references_deleted == 0
        assert second.provenance_deleted == 0

    client.portal.call(scenario)


def test_zero_active_period_is_safe(client, db_session, migration_case):
    case = migration_case

    async def scenario():
        await _seed_legacy(db_session, case)
        await db_session.execute(
            text("UPDATE academic_periods SET is_active = FALSE WHERE academic_period_id = :id"),
            {"id": case["active_id"]},
        )
        await db_session.flush()
        connection = await db_session.connection()
        result = await connection.run_sync(upgrade_legacy_scheduling)
        assert result.status == "no_active_period"
        assert result.academic_period_id is None
        assert result.availability_sources == result.reference_sources == 2
        assert result.provenance_copied == result.provenance_skipped == 0
        assert (
            await db_session.execute(text(f"SELECT count(*) FROM {STATE_TABLE}"))
        ).scalar_one() == 0

    client.portal.call(scenario)


def test_multiple_active_periods_are_rejected(client, db_session, migration_case):
    case = migration_case

    async def scenario():
        await _seed_legacy(db_session, case)
        await db_session.execute(
            text("UPDATE academic_periods SET is_active = TRUE WHERE academic_period_id = :id"),
            {"id": case["other_id"]},
        )
        await db_session.flush()
        connection = await db_session.connection()
        with pytest.raises(ActivePeriodAmbiguityError) as raised:
            await connection.run_sync(upgrade_legacy_scheduling)
        assert set(raised.value.period_ids) == {case["active_id"], case["other_id"]}
        assert (
            await db_session.execute(text(f"SELECT count(*) FROM {STATE_TABLE}"))
        ).scalar_one() == 0
        assert await _period_preferences(db_session, case["active_id"]) == []
        assert await _period_references(db_session, case["active_id"]) == []

    client.portal.call(scenario)


def test_seed_recreation_cascades_stale_provenance_and_recopies(client, db_session, migration_case):
    case = migration_case

    async def scenario():
        await _seed_legacy(
            db_session,
            case,
            availability=[],
            references=[(0, "Dosen Satu", "pjmk", 0)],
        )
        connection = await db_session.connection()
        await connection.run_sync(upgrade_legacy_scheduling)
        await db_session.execute(text("DELETE FROM course_instructor_references"))
        await db_session.flush()
        assert (
            await db_session.execute(text(f"SELECT count(*) FROM {REFERENCE_MAP}"))
        ).scalar_one() == 0
        recreated = CourseInstructorReference(
            curriculum_course_id=case["course_ids"][0],
            source_document_id=case["source_document_id"],
            instructor_name="Dosen Satu",
            instructor_role="pjmk",
            user_id=case["lecturer_ids"][0],
        )
        db_session.add(recreated)
        await db_session.flush()
        result = await connection.run_sync(upgrade_legacy_scheduling)

        assert result.references_inserted == 1
        assert result.references_rerun == 0
        references = await _period_references(db_session, case["active_id"])
        assert len(references) == 1
        mapping = (
            await db_session.execute(text(f"SELECT * FROM {REFERENCE_MAP}"))
        ).mappings().one()
        assert mapping["instructor_reference_id"] == recreated.instructor_reference_id
        assert mapping["target_reference_id"] == references[0].instructor_reference_id
        assert result.academic_period_id == case["active_id"]

    client.portal.call(scenario)


def test_reference_snapshot_ddl_is_idempotent_and_reversible(monkeypatch):
    ddl = import_module(
        "migrations.versions.d4a6e8b0c2f1_create_instructor_reference_snapshot"
    )
    statements: list[str] = []

    def execute(statement):
        statements.append(str(statement))

    monkeypatch.setattr(ddl.op, "execute", execute)
    ddl.upgrade()
    ddl.upgrade()
    ddl.downgrade()
    ddl.downgrade()

    assert ddl.revision == "d4a6e8b0c2f1"
    assert ddl.down_revision == "c9d0e1f2a3b4"
    creates = [item for item in statements if "CREATE TABLE" in item]
    drops = [item for item in statements if "DROP TABLE" in item]
    assert len(creates) == len(drops) == 4
    assert all("IF NOT EXISTS" in item for item in creates)
    assert all("IF EXISTS" in item for item in drops)
    assert any("instructor_reference_merge_snapshot" in item for item in creates)
    assert any("instructor_reference_restore_map" in item for item in creates)
    assert not any(
        item.lstrip().upper().startswith(("INSERT ", "UPDATE ", "DELETE "))
        for item in statements
    )


def test_snapshot_backfill_is_idempotent_and_restorable(
    client, db_session, migration_case, monkeypatch
):
    case = migration_case
    backfill = import_module(
        "migrations.versions.e5b7f9c1d3a2_backfill_instructor_reference_snapshot"
    )

    async def scenario():
        await db_session.execute(text("DELETE FROM instructor_reference_merge_snapshot"))
        await db_session.execute(text("DELETE FROM instructor_reference_restore_map"))
        seeded = await _seed_legacy(
            db_session,
            case,
            availability=[],
            references=[(0, "Dr. Dosen Satu, Ph.D.", "pjmk", 0)],
        )
        reference_id = seeded["reference_ids"][0]
        snapshot_columns = (
            "instructor_reference_id, curriculum_course_id, academic_period_id, "
            "source_document_id, instructor_name, instructor_role, user_id"
        )
        connection = await db_session.connection()

        def run(operation):
            def with_bind(sync_connection):
                monkeypatch.setattr(backfill.op, "get_bind", lambda: sync_connection)
                operation()

            return connection.run_sync(with_bind)

        await run(backfill.upgrade)
        await run(backfill.upgrade)

        live = (
            await db_session.execute(
                text(
                    f"SELECT {snapshot_columns} FROM course_instructor_references "
                    "WHERE instructor_reference_id = :id"
                ),
                {"id": reference_id},
            )
        ).mappings().one()
        snapshot = (
            await db_session.execute(
                text(
                    f"SELECT {snapshot_columns} FROM instructor_reference_merge_snapshot "
                    "WHERE instructor_reference_id = :id"
                ),
                {"id": reference_id},
            )
        ).mappings().one()
        assert dict(live) == dict(snapshot)
        assert (
            await db_session.execute(
                text(
                    "SELECT count(*) FROM course_instructor_references "
                    "WHERE instructor_reference_id = :id"
                ),
                {"id": reference_id},
            )
        ).scalar_one() == 1
        assert (
            await db_session.execute(
                text("SELECT count(*) FROM instructor_reference_merge_snapshot")
            )
        ).scalar_one() == 1
        restore_map = (
            await db_session.execute(
                text(
                    "SELECT archived_reference_id, retained_reference_id "
                    "FROM instructor_reference_restore_map"
                )
            )
        ).mappings().one()
        assert (
            restore_map["archived_reference_id"]
            == restore_map["retained_reference_id"]
            == reference_id
        )

        # Snapshot survives deletion of the live row, which is what a merge does.
        await db_session.execute(
            text(
                "DELETE FROM course_instructor_references "
                "WHERE instructor_reference_id = :id"
            ),
            {"id": reference_id},
        )
        await db_session.execute(
            text(
                "INSERT INTO course_instructor_references ("
                "instructor_reference_id, curriculum_course_id, academic_period_id, "
                "source_document_id, instructor_name, instructor_role, user_id, "
                "position, source_reference_id"
                ") SELECT instructor_reference_id, curriculum_course_id, "
                "academic_period_id, source_document_id, instructor_name, "
                "instructor_role, user_id, position, source_reference_id "
                "FROM instructor_reference_merge_snapshot "
                "WHERE instructor_reference_id = :id"
            ),
            {"id": reference_id},
        )
        restored = (
            await db_session.execute(
                text(
                    f"SELECT {snapshot_columns} FROM course_instructor_references "
                    "WHERE instructor_reference_id = :id"
                ),
                {"id": reference_id},
            )
        ).mappings().one()
        assert dict(restored) == dict(live)

        await run(backfill.downgrade)
        assert (
            await db_session.execute(
                text("SELECT count(*) FROM instructor_reference_merge_snapshot")
            )
        ).scalar_one() == 0
        assert (
            await db_session.execute(
                text("SELECT count(*) FROM instructor_reference_restore_map")
            )
        ).scalar_one() == 0
        assert backfill.revision == "e5b7f9c1d3a2"
        assert backfill.down_revision == "d4a6e8b0c2f1"

    client.portal.call(scenario)
