"""add schedule generation idempotency

Revision ID: 5219117f9b0b
Revises: 6cae961f6694
Create Date: 2026-11-27 23:41:30.007733

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '5219117f9b0b'
down_revision: Union[str, Sequence[str], None] = '6cae961f6694'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE schedule_runs ADD COLUMN IF NOT EXISTS "
        "request_key VARCHAR(64) NULL"
    )
    op.execute(
        "ALTER TABLE schedule_runs ADD COLUMN IF NOT EXISTS response JSONB NULL"
    )
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_schedule_runs_request_key
        ON schedule_runs (academic_period_id, request_key)
        WHERE request_key IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_schedule_runs_request_key")
    op.execute("ALTER TABLE schedule_runs DROP COLUMN IF EXISTS response")
    op.execute("ALTER TABLE schedule_runs DROP COLUMN IF EXISTS request_key")
