"""add scheduling tables

Revision ID: 9d4e7a1b2c3f
Revises: a2b7c4d6e8f1
Create Date: 2026-11-20 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

revision: str = '9d4e7a1b2c3f'
down_revision: str | Sequence[str] | None = 'a2b7c4d6e8f1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS rooms (
        room_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        room_code VARCHAR(50) NOT NULL UNIQUE,
        capacity SMALLINT NOT NULL,
        owner_study_program_id UUID REFERENCES study_programs(study_program_id) ON DELETE SET NULL,
        is_active BOOLEAN NOT NULL DEFAULT true,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT rooms_capacity_check CHECK (capacity > 0)
    )
    """)
    op.execute("""
    CREATE TABLE IF NOT EXISTS lecturer_availability (
        availability_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        day_of_week SMALLINT NOT NULL,
        start_hour SMALLINT NOT NULL,
        end_hour SMALLINT NOT NULL,
        CONSTRAINT lecturer_availability_day_check CHECK (day_of_week BETWEEN 1 AND 5),
        CONSTRAINT lecturer_availability_start_check CHECK (start_hour BETWEEN 7 AND 16),
        CONSTRAINT lecturer_availability_end_check CHECK (end_hour BETWEEN 8 AND 17),
        CONSTRAINT lecturer_availability_range_check CHECK (end_hour > start_hour),
        CONSTRAINT lecturer_availability_unique_slot UNIQUE (user_id, day_of_week, start_hour)
    )
    """)
    op.execute("""
    CREATE TABLE IF NOT EXISTS schedule_runs (
        run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        academic_period_id UUID NOT NULL REFERENCES academic_periods(academic_period_id) ON DELETE RESTRICT,
        mode VARCHAR(20) NOT NULL,
        triggered_by UUID REFERENCES users(user_id) ON DELETE SET NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'running',
        stats JSONB NOT NULL DEFAULT '{}'::jsonb,
        started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        ended_at TIMESTAMPTZ NULL
    )
    """)
    op.execute("""
    CREATE TABLE IF NOT EXISTS schedule_program_status (
        academic_period_id UUID NOT NULL REFERENCES academic_periods(academic_period_id) ON DELETE RESTRICT,
        study_program_id UUID NOT NULL REFERENCES study_programs(study_program_id) ON DELETE RESTRICT,
        state VARCHAR(20) NOT NULL DEFAULT 'draft',
        finalized_by UUID REFERENCES users(user_id) ON DELETE SET NULL,
        finalized_at TIMESTAMPTZ NULL,
        PRIMARY KEY (academic_period_id, study_program_id)
    )
    """)
    op.execute("""
    CREATE TABLE IF NOT EXISTS unassigned_classes (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        run_id UUID NOT NULL REFERENCES schedule_runs(run_id) ON DELETE CASCADE,
        class_section_id UUID NOT NULL REFERENCES class_sections(class_section_id) ON DELETE CASCADE,
        reason VARCHAR(200) NOT NULL
    )
    """)
    op.execute("""
    CREATE TABLE IF NOT EXISTS schedule_edit_log (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        class_section_id UUID NOT NULL REFERENCES class_sections(class_section_id) ON DELETE CASCADE,
        changed_by UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
        reason VARCHAR(500) NOT NULL,
        before_state JSONB NULL,
        after_state JSONB NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)
    op.execute("""
    CREATE TABLE IF NOT EXISTS class_count_overrides (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        academic_period_id UUID NOT NULL REFERENCES academic_periods(academic_period_id) ON DELETE CASCADE,
        course_id UUID NOT NULL REFERENCES courses(course_id) ON DELETE CASCADE,
        study_program_id UUID NOT NULL REFERENCES study_programs(study_program_id) ON DELETE CASCADE,
        class_count SMALLINT NOT NULL,
        CONSTRAINT class_count_overrides_class_count_check CHECK (class_count BETWEEN 1 AND 3),
        CONSTRAINT class_count_overrides_unique UNIQUE (academic_period_id, course_id, study_program_id)
    )
    """)
    op.execute("""
    CREATE TABLE IF NOT EXISTS schedule_period_locks (
        academic_period_id UUID PRIMARY KEY REFERENCES academic_periods(academic_period_id) ON DELETE CASCADE,
        krs_open BOOLEAN NOT NULL DEFAULT false,
        locked_at TIMESTAMPTZ NULL,
        locked_by UUID REFERENCES users(user_id) ON DELETE SET NULL
    )
    """)
    op.execute("""
    ALTER TABLE class_schedules ADD COLUMN IF NOT EXISTS room_id UUID NULL
    REFERENCES rooms(room_id) ON DELETE SET NULL
    """)
    op.execute("""
    ALTER TABLE course_instructor_references ADD COLUMN IF NOT EXISTS user_id UUID NULL
    REFERENCES users(user_id) ON DELETE SET NULL
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE course_instructor_references DROP COLUMN IF EXISTS user_id")
    op.execute("ALTER TABLE class_schedules DROP COLUMN IF EXISTS room_id")
    op.execute("DROP TABLE IF EXISTS schedule_period_locks")
    op.execute("DROP TABLE IF EXISTS class_count_overrides")
    op.execute("DROP TABLE IF EXISTS schedule_edit_log")
    op.execute("DROP TABLE IF EXISTS unassigned_classes")
    op.execute("DROP TABLE IF EXISTS schedule_program_status")
    op.execute("DROP TABLE IF EXISTS schedule_runs")
    op.execute("DROP TABLE IF EXISTS lecturer_availability")
    op.execute("DROP TABLE IF EXISTS rooms")
