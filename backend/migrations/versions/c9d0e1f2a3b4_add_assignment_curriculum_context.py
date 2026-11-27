"""add assignment curriculum context

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-11-25 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: str | Sequence[str] | None = "b8c9d0e1f2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE class_instructor_assignments "
        "ADD COLUMN IF NOT EXISTS curriculum_course_id UUID NULL "
        "REFERENCES curriculum_courses(curriculum_course_id) ON DELETE RESTRICT"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE class_instructor_assignments "
        "DROP COLUMN IF EXISTS curriculum_course_id"
    )
