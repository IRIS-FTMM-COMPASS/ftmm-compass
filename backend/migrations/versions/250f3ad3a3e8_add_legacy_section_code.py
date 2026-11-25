"""add legacy section code

Revision ID: 250f3ad3a3e8
Revises: f1e2d3c4b5a6
Create Date: 2026-11-26 01:25:19.596522

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '250f3ad3a3e8'
down_revision: Union[str, Sequence[str], None] = 'f1e2d3c4b5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE class_sections "
        "ADD COLUMN IF NOT EXISTS legacy_section_code VARCHAR(30) NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE class_sections DROP COLUMN IF EXISTS legacy_section_code")
