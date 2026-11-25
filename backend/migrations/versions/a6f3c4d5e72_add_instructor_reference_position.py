"""add instructor reference position and copy provenance

Revision ID: a6f3c4d5e72
Revises: 9d5e2f3a4b61
Create Date: 2026-11-25 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a6f3c4d5e72"
down_revision: str | Sequence[str] | None = "9d5e2f3a4b61"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE course_instructor_references "
        "ADD COLUMN IF NOT EXISTS position SMALLINT NULL"
    )
    op.execute(
        "ALTER TABLE course_instructor_references "
        "ADD COLUMN IF NOT EXISTS source_reference_id UUID NULL "
        "REFERENCES course_instructor_references(instructor_reference_id) "
        "ON DELETE SET NULL"
    )
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_constraint "
        "WHERE conrelid = 'course_instructor_references'::regclass "
        "AND conname = 'ck_instructor_reference_position') THEN "
        "ALTER TABLE course_instructor_references ADD CONSTRAINT "
        "ck_instructor_reference_position CHECK "
        "(position IS NULL OR position > 0); "
        "END IF; END $$"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS "
        "uq_instructor_reference_pool_position "
        "ON course_instructor_references "
        "(curriculum_course_id, academic_period_id, position) "
        "WHERE academic_period_id IS NOT NULL AND position IS NOT NULL "
        "AND instructor_role IN ('pjmk', 'teaching_team')"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_instructor_reference_pool_position")
    op.execute(
        "ALTER TABLE course_instructor_references "
        "DROP CONSTRAINT IF EXISTS ck_instructor_reference_position"
    )
    op.execute(
        "ALTER TABLE course_instructor_references "
        "DROP COLUMN IF EXISTS source_reference_id"
    )
    op.execute(
        "ALTER TABLE course_instructor_references DROP COLUMN IF EXISTS position"
    )
