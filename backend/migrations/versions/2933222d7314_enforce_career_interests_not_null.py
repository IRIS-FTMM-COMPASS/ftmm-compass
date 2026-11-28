"""enforce career interests not null

Revision ID: 2933222d7314
Revises: 5219117f9b0b
Create Date: 2026-11-28 06:18:51.057936

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '2933222d7314'
down_revision: Union[str, Sequence[str], None] = '5219117f9b0b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "UPDATE users SET career_interests = '[]'::jsonb "
        "WHERE career_interests IS NULL"
    )
    op.execute(
        "ALTER TABLE users ALTER COLUMN career_interests SET DEFAULT '[]'::jsonb"
    )
    op.execute(
        "ALTER TABLE users ALTER COLUMN career_interests SET NOT NULL"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        "ALTER TABLE users ALTER COLUMN career_interests DROP NOT NULL"
    )
