"""add lecturer profiles

Revision ID: a2b7c4d6e8f1
Revises: f8a5c3e1b2d4
Create Date: 2026-11-19 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

revision: str = 'a2b7c4d6e8f1'
down_revision: str | Sequence[str] | None = 'f8a5c3e1b2d4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS lecturer_profiles (
        user_id UUID PRIMARY KEY REFERENCES users(user_id) ON DELETE RESTRICT,
        study_program_id UUID NOT NULL REFERENCES study_programs(study_program_id) ON DELETE RESTRICT,
        is_program_coordinator BOOLEAN NOT NULL DEFAULT false,
        employee_number VARCHAR(30),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)
    op.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS uq_lecturer_profiles_pj_per_prodi
    ON lecturer_profiles(study_program_id) WHERE is_program_coordinator
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_lecturer_profiles_pj_per_prodi")
    op.execute("DROP TABLE IF EXISTS lecturer_profiles")
