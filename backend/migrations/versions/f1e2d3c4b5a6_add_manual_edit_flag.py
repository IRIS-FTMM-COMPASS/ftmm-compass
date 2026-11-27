"""add manual edit flag to schedule edit log

Revision ID: f1e2d3c4b5a6
Revises: e5b7f9c1d3a2
Create Date: 2026-11-25 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f1e2d3c4b5a6"
down_revision: str | Sequence[str] | None = "e5b7f9c1d3a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE schedule_edit_log "
        "ADD COLUMN IF NOT EXISTS is_manual_edit BOOLEAN NOT NULL DEFAULT FALSE"
    )
    op.execute(
        "UPDATE schedule_edit_log SET is_manual_edit = TRUE "
        "WHERE jsonb_exists(before_state, 'day_of_week') "
        "AND reason NOT IN ("
        "'generate', 'regenerate', 'normalisasi blok', "
        "'perbaikan jadwal tanpa ruang maupun nama ruang', "
        "'full_reset', 'finalize'"
        ")"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE schedule_edit_log DROP COLUMN IF EXISTS is_manual_edit")
