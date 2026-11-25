"""backfill instructor reference snapshot

Revision ID: e5b7f9c1d3a2
Revises: d4a6e8b0c2f1
Create Date: 2026-11-25 00:00:00.000000

Menyalin seluruh referensi dosen saat ini ke snapshot. Peta pemulihan dimulai
dari pemetaan identitas; penggabungan duplikat berikutnya mengarahkan
`archived_reference_id` ke baris yang dipertahankan. Migrasi ini tidak
menyisipkan baris kembali ke tabel hidup.
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "e5b7f9c1d3a2"
down_revision: str | Sequence[str] | None = "d4a6e8b0c2f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SNAPSHOT_SQL = """
INSERT INTO instructor_reference_merge_snapshot (
    instructor_reference_id, curriculum_course_id, academic_period_id,
    source_document_id, instructor_name, instructor_role, user_id,
    position, source_reference_id
)
SELECT instructor_reference_id, curriculum_course_id, academic_period_id,
       source_document_id, instructor_name, instructor_role, user_id,
       position, source_reference_id
FROM course_instructor_references
ON CONFLICT (instructor_reference_id) DO NOTHING
"""

_RESTORE_MAP_SQL = """
INSERT INTO instructor_reference_restore_map (
    archived_reference_id, retained_reference_id, curriculum_course_id, academic_period_id
)
SELECT instructor_reference_id, instructor_reference_id, curriculum_course_id,
       academic_period_id
FROM course_instructor_references
ON CONFLICT (archived_reference_id) DO NOTHING
"""


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(text(_SNAPSHOT_SQL))
    bind.execute(text(_RESTORE_MAP_SQL))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(text("DELETE FROM instructor_reference_restore_map"))
    bind.execute(text("DELETE FROM instructor_reference_merge_snapshot"))
