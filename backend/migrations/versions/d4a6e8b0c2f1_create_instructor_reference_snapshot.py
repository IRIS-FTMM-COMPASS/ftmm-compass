"""create instructor reference snapshot tables

Revision ID: d4a6e8b0c2f1
Revises: c9d0e1f2a3b4
Create Date: 2026-11-25 00:00:00.000000

Kolom menyimpan nilai mentah tanpa FK ke tabel hidup agar baris arsip tetap
dapat dipulihkan setelah referensi aslinya dihapus.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "d4a6e8b0c2f1"
down_revision: str | Sequence[str] | None = "c9d0e1f2a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS instructor_reference_merge_snapshot (
            instructor_reference_id UUID NOT NULL PRIMARY KEY,
            curriculum_course_id UUID NOT NULL,
            academic_period_id UUID,
            source_document_id UUID,
            instructor_name VARCHAR(200) NOT NULL,
            instructor_role VARCHAR(30) NOT NULL,
            user_id UUID,
            position SMALLINT,
            source_reference_id UUID
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS instructor_reference_restore_map (
            archived_reference_id UUID NOT NULL PRIMARY KEY,
            retained_reference_id UUID NOT NULL,
            curriculum_course_id UUID NOT NULL,
            academic_period_id UUID
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS instructor_reference_restore_map")
    op.execute("DROP TABLE IF EXISTS instructor_reference_merge_snapshot")
