"""add token version and recovery code hash

Menambahkan kolom pencabutan sesi (token_version) dan penyimpanan kode
pemulihan yang di-hash (recovery_code_hash) pada tabel users.

Revision ID: f3c9d1a7b2e8
Revises: c4d2e6f8a1b3
Create Date: 2026-11-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "f3c9d1a7b2e8"
down_revision: Union[str, Sequence[str], None] = "c4d2e6f8a1b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version "
        "INTEGER NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS recovery_code_hash VARCHAR(64)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS recovery_code_hash")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS token_version")
