"""indeks unik parsial satu PJ MK per mata kuliah kurikulum

Revision ID: c8e3f5a7b9d2
Revises: b7d2e4f6a8c1
Create Date: 2026-11-22 00:00:00.000000

DDL saja; normalisasi data ada di b7d2e4f6a8c1 agar indeks dapat dibuat tanpa
pelanggaran duplikat. Indeks parsial adalah pengaman terakhir untuk aturan satu
pjmk per curriculum_course.
"""

from collections.abc import Sequence

from alembic import op

revision: str = 'c8e3f5a7b9d2'
down_revision: str | Sequence[str] | None = 'b7d2e4f6a8c1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS uq_course_instructor_pjmk
    ON course_instructor_references (curriculum_course_id)
    WHERE instructor_role = 'pjmk'
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_course_instructor_pjmk")
