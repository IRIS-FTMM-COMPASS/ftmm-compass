"""create admin authority traces

Revision ID: e7a4b2c9d1f3
Revises: f3c9d1a7b2e8
Create Date: 2026-11-19 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e7a4b2c9d1f3'
down_revision: str | Sequence[str] | None = 'f3c9d1a7b2e8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS admin_authority_traces (
        trace_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        actor_user_id UUID NOT NULL,
        actor_snapshot TEXT NOT NULL,
        target_user_id UUID NOT NULL,
        target_snapshot TEXT NOT NULL,
        action TEXT NOT NULL,
        field_name TEXT NULL,
        old_value TEXT NULL,
        new_value TEXT NULL,
        reason TEXT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)
    op.execute("""
    CREATE INDEX IF NOT EXISTS idx_admin_authority_traces_created_at
    ON admin_authority_traces (created_at DESC)
    """)
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS needs_revalidation "
        "BOOLEAN NOT NULL DEFAULT false"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS needs_revalidation")
    op.execute("DROP INDEX IF EXISTS idx_admin_authority_traces_created_at")
    op.execute("DROP TABLE IF EXISTS admin_authority_traces")
