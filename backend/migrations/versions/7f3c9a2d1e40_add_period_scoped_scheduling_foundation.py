"""period-scoped scheduling foundation

Revision ID: 7f3c9a2d1e40
Revises: c8e3f5a7b9d2
Create Date: 2026-11-25 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "7f3c9a2d1e40"
down_revision: str | Sequence[str] | None = "c8e3f5a7b9d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        "ALTER TABLE course_instructor_references "
        "ADD COLUMN IF NOT EXISTS academic_period_id UUID NULL "
        "REFERENCES academic_periods(academic_period_id) ON DELETE RESTRICT"
    )
    op.execute("DROP INDEX IF EXISTS uq_course_instructor_pjmk")
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_course_instructor_pjmk
        ON course_instructor_references (curriculum_course_id)
        WHERE instructor_role = 'pjmk' AND academic_period_id IS NULL
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_course_instructor_pjmk_period
        ON course_instructor_references (curriculum_course_id, academic_period_id)
        WHERE instructor_role = 'pjmk' AND academic_period_id IS NOT NULL
    """)
    op.execute(
        "ALTER TABLE schedule_runs ADD COLUMN IF NOT EXISTS "
        "input_revision INTEGER NOT NULL DEFAULT 0"
    )
    op.execute("""
        CREATE TABLE IF NOT EXISTS lecturer_schedule_preferences (
            preference_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            academic_period_id UUID NOT NULL REFERENCES academic_periods(academic_period_id) ON DELETE RESTRICT,
            day_of_week SMALLINT NOT NULL,
            start_time TIME WITHOUT TIME ZONE NOT NULL,
            end_time TIME WITHOUT TIME ZONE NOT NULL,
            kind VARCHAR(20) NOT NULL,
            CONSTRAINT ck_preference_day CHECK (day_of_week BETWEEN 1 AND 5),
            CONSTRAINT ck_preference_kind CHECK (kind IN ('preferred', 'unavailable')),
            CONSTRAINT ck_preference_start CHECK (
                start_time >= TIME '07:00:00' AND start_time < TIME '17:00:00'
            ),
            CONSTRAINT ck_preference_end CHECK (
                end_time > TIME '07:00:00' AND end_time <= TIME '17:00:00'
            ),
            CONSTRAINT ck_preference_range CHECK (end_time > start_time),
            CONSTRAINT ck_preference_whole_hour CHECK (
                EXTRACT(MINUTE FROM start_time) = 0
                AND EXTRACT(SECOND FROM start_time) = 0
                AND EXTRACT(MICROSECONDS FROM start_time) = 0
                AND EXTRACT(MINUTE FROM end_time) = 0
                AND EXTRACT(SECOND FROM end_time) = 0
                AND EXTRACT(MICROSECONDS FROM end_time) = 0
            ),
            CONSTRAINT ex_preference_overlap EXCLUDE USING gist (
                user_id WITH =,
                academic_period_id WITH =,
                day_of_week WITH =,
                int4range(
                    EXTRACT(HOUR FROM start_time)::int,
                    EXTRACT(HOUR FROM end_time)::int,
                    '[)'
                ) WITH &&
            )
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS class_instructor_assignments (
            assignment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            class_section_id UUID NOT NULL REFERENCES class_sections(class_section_id) ON DELETE CASCADE,
            academic_period_id UUID NOT NULL REFERENCES academic_periods(academic_period_id) ON DELETE RESTRICT,
            user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
            source VARCHAR(10) NOT NULL DEFAULT 'manual',
            is_pinned BOOLEAN NOT NULL DEFAULT false,
            is_active BOOLEAN NOT NULL DEFAULT true,
            assigned_by UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
            assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_assignment_source CHECK (source IN ('auto', 'manual'))
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_assignment_active_class
        ON class_instructor_assignments (class_section_id)
        WHERE is_active
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION enforce_active_lecturer_assignment()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM users AS u
                JOIN lecturer_profiles AS lp ON lp.user_id = u.user_id
                WHERE u.user_id = NEW.user_id
                  AND u.role = 'lecturer'
                  AND u.is_active
            ) THEN
                RAISE EXCEPTION 'Assignment requires an active lecturer account'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("DROP TRIGGER IF EXISTS trg_assignment_active_lecturer ON class_instructor_assignments")
    op.execute("""
        CREATE TRIGGER trg_assignment_active_lecturer
        BEFORE INSERT OR UPDATE OF user_id ON class_instructor_assignments
        FOR EACH ROW EXECUTE FUNCTION enforce_active_lecturer_assignment()
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS schedule_period_settings (
            settings_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            academic_period_id UUID NOT NULL REFERENCES academic_periods(academic_period_id) ON DELETE RESTRICT,
            study_program_id UUID NULL REFERENCES study_programs(study_program_id) ON DELETE RESTRICT,
            preference_deadline TIMESTAMPTZ NULL,
            input_revision INTEGER NOT NULL DEFAULT 0,
            finalized_by UUID NULL REFERENCES users(user_id) ON DELETE SET NULL,
            finalized_at TIMESTAMPTZ NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_period_settings_revision CHECK (input_revision >= 0)
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_period_settings_global
        ON schedule_period_settings (academic_period_id)
        WHERE study_program_id IS NULL
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_period_settings_program
        ON schedule_period_settings (academic_period_id, study_program_id)
        WHERE study_program_id IS NOT NULL
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION enforce_monotonic_input_revision()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.input_revision < OLD.input_revision THEN
                RAISE EXCEPTION 'input_revision cannot decrease'
                    USING ERRCODE = '23514';
            END IF;
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("DROP TRIGGER IF EXISTS trg_period_settings_revision ON schedule_period_settings")
    op.execute("""
        CREATE TRIGGER trg_period_settings_revision
        BEFORE UPDATE ON schedule_period_settings
        FOR EACH ROW EXECUTE FUNCTION enforce_monotonic_input_revision()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_period_settings_revision ON schedule_period_settings")
    op.execute("DROP FUNCTION IF EXISTS enforce_monotonic_input_revision()")
    op.execute("DROP TABLE IF EXISTS schedule_period_settings")
    op.execute("DROP TRIGGER IF EXISTS trg_assignment_active_lecturer ON class_instructor_assignments")
    op.execute("DROP FUNCTION IF EXISTS enforce_active_lecturer_assignment()")
    op.execute("DROP TABLE IF EXISTS class_instructor_assignments")
    op.execute("DROP TABLE IF EXISTS lecturer_schedule_preferences")
    op.execute("ALTER TABLE schedule_runs DROP COLUMN IF EXISTS input_revision")
    op.execute("DROP INDEX IF EXISTS uq_course_instructor_pjmk_period")
    op.execute("DROP INDEX IF EXISTS uq_course_instructor_pjmk")
    op.execute("ALTER TABLE course_instructor_references DROP COLUMN IF EXISTS academic_period_id")
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM course_instructor_references
                WHERE instructor_role = 'pjmk'
                GROUP BY curriculum_course_id
                HAVING COUNT(*) > 1
            ) THEN
                RAISE NOTICE 'Legacy PJ MK uniqueness not restored because scoped rows are incompatible';
            ELSE
                CREATE UNIQUE INDEX IF NOT EXISTS uq_course_instructor_pjmk
                ON course_instructor_references (curriculum_course_id)
                WHERE instructor_role = 'pjmk';
            END IF;
        END;
        $$ LANGUAGE plpgsql
    """)
