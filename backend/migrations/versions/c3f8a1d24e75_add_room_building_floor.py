"""add building and floor to rooms

Revision ID: c3f8a1d24e75
Revises: 9d4e7a1b2c3f
Create Date: 2026-11-21 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

revision: str = 'c3f8a1d24e75'
down_revision: str | Sequence[str] | None = '9d4e7a1b2c3f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
    ALTER TABLE rooms
    ADD COLUMN IF NOT EXISTS building VARCHAR(50) NOT NULL DEFAULT 'NANO'
    """)
    op.execute("""
    ALTER TABLE rooms
    ADD COLUMN IF NOT EXISTS floor VARCHAR(20)
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE rooms DROP COLUMN IF EXISTS floor")
    op.execute("ALTER TABLE rooms DROP COLUMN IF EXISTS building")
