"""tambah semester_number pada periode akademik

Revision ID: a9d4f7b2c8e1
Revises: c3f8a1d24e75
Create Date: 2026-11-21 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

revision: str = 'a9d4f7b2c8e1'
down_revision: str | Sequence[str] | None = 'c3f8a1d24e75'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE academic_periods ADD COLUMN IF NOT EXISTS semester_number SMALLINT")
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'academic_periods_semester_number_check'
              AND conrelid = 'academic_periods'::regclass
        ) THEN
            ALTER TABLE academic_periods
                ADD CONSTRAINT academic_periods_semester_number_check
                CHECK (semester_number IS NULL OR semester_number BETWEEN 1 AND 14);
        END IF;
    END $$;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE academic_periods DROP CONSTRAINT IF EXISTS academic_periods_semester_number_check")
    op.execute("ALTER TABLE academic_periods DROP COLUMN IF EXISTS semester_number")
