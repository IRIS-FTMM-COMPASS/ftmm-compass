"""scrub anonymized trace identity

Revision ID: 7c1d2e3f4a5b
Revises: 2933222d7314
Create Date: 2026-11-28 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

revision: str = "7c1d2e3f4a5b"
down_revision: str | Sequence[str] | None = "2933222d7314"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE admin_authority_traces
        SET target_snapshot = jsonb_build_object(
            'user_id', target_snapshot::jsonb -> 'user_id',
            'role', target_snapshot::jsonb -> 'role',
            'is_active', target_snapshot::jsonb -> 'is_active',
            'redacted', true
        )::text
        WHERE action = 'anonymize'
          AND target_snapshot LIKE '{%'
          AND pg_input_is_valid(target_snapshot, 'jsonb')
        """
    )


def downgrade() -> None:
    # PII yang sudah dihapus tidak dapat dipulihkan.
    pass
