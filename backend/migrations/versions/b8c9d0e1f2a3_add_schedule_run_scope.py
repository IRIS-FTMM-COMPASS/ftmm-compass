"""add schedule run program scope

Revision ID: b8c9d0e1f2a3
Revises: a6f3c4d5e72
Create Date: 2026-11-25 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: str | Sequence[str] | None = "a6f3c4d5e72"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE schedule_runs ADD COLUMN IF NOT EXISTS study_program_id UUID NULL "
        "REFERENCES study_programs(study_program_id) ON DELETE RESTRICT"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_schedule_runs_period_scope_started "
        "ON schedule_runs (academic_period_id, study_program_id, started_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_schedule_runs_period_scope_started")
    op.execute("ALTER TABLE schedule_runs DROP COLUMN IF EXISTS study_program_id")
