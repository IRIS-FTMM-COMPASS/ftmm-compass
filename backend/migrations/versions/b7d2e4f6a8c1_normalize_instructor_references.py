"""normalisasi dan pemetaan referensi dosen ke akun lecturer

Revision ID: b7d2e4f6a8c1
Revises: a9d4f7b2c8e1
Create Date: 2026-11-22 00:00:00.000000

Pemisahan DDL/DML: migrasi ini hanya memanipulasi data. Tiga tahap:

1. Nama berformat orang (mengandung koma, bukan "Tim Pengajar ...") dinormalisasi
   ke `users.full_name` bila ada tepat satu kecocokan konservatif di antara dosen
   aktif. Kecocokan memakai nama belakang hasil normalisasi ditambah minimal satu
   token nama lain; gelar setelah koma dan inisial satu huruf diabaikan. Nama
   tanpa kecocokan dibiarkan apa adanya tanpa log maupun error.
2. Baris yang menjadi identik pada (curriculum_course_id,
   lower(nama ternormalisasi), instructor_role) digabung: dipertahankan baris
   dengan user_id tidak null, jika tidak ada maka instructor_reference_id
   terkecil.
3. Setiap mata kuliah yang belum punya PJ MK mendapat tepat satu baris pjmk
   dari baris berformat orang: baris yang sudah terpetakan ke akun didahulukan,
   lalu urutan instructor_reference_id. Mata kuliah yang hanya punya baris
   generik ("Dosen Tim Pengajar ...") tetap tanpa pjmk.

Urutan idempoten: menjalankan ulang tidak menambah atau mengubah baris lagi.

Downgrade mengembalikan seluruh baris pjmk ke teaching_team. Ini kehilangan
informasi PJ MK asli (termasuk baris pjmk yang sudah ada sebelum migrasi);
catatan kehilangan data ini disengaja karena status pjmk tidak dapat dipulihkan
tanpa sumber eksternal.
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = 'b7d2e4f6a8c1'
down_revision: str | Sequence[str] | None = 'a9d4f7b2c8e1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Gelar/jabatan yang lazim mendahului nama pada katalog. Gelar setelah koma
# tidak perlu didaftar karena bagian itu sudah dibuang sebelum tokenisasi.
_TITLES_SQL = (
    "ARRAY['dr','ir','prof','drs','dra','eng','hj','h','cand','sp','btkv','k']"
)

# Token nama orang ternormalisasi: huruf kecil, tanpa tanda baca, tanpa gelar,
# tanpa inisial satu huruf.
_TOKEN_SQL = """
array_remove(
    ARRAY(
        SELECT tk
        FROM regexp_split_to_table(
            lower(
                regexp_replace(
                    split_part({source}, ',', 1),
                    '[^A-Za-z]+',
                    ' ',
                    'g'
                )
            ),
            '\\s+'
        ) AS tk
        WHERE length(tk) > 1
          AND NOT (tk = ANY({titles}))
    ),
    NULL
)
"""

_NORMALIZED_NAME_SQL = (
    "lower(regexp_replace(btrim({source}), '\\s+', ' ', 'g'))"
)

_MAP_REFERENCES_SQL = f"""
WITH ref_tokens AS (
    SELECT
        r.instructor_reference_id,
        {_TOKEN_SQL.format(source='r.instructor_name', titles='{titles}')} AS tokens
    FROM course_instructor_references r
    WHERE r.instructor_name LIKE '%,%'
      AND r.instructor_name NOT ILIKE 'tim pengajar%'
),
ref_parts AS (
    SELECT
        instructor_reference_id,
        tokens,
        tokens[array_length(tokens, 1)] AS surname,
        tokens[1:array_length(tokens, 1) - 1] AS others
    FROM ref_tokens
    WHERE array_length(tokens, 1) >= 2
),
lecturer_tokens AS (
    SELECT
        u.user_id,
        {_TOKEN_SQL.format(source='u.full_name', titles='{titles}')} AS tokens
    FROM users u
    WHERE u.role = 'lecturer'
      AND u.is_active
),
matches AS (
    SELECT p.instructor_reference_id, l.user_id
    FROM ref_parts p
    JOIN lecturer_tokens l
      ON p.surname = ANY(l.tokens)
     AND EXISTS (
        SELECT 1
        FROM unnest(p.others) AS other_token
        WHERE other_token = ANY(l.tokens)
     )
),
unique_matches AS (
    SELECT instructor_reference_id, user_id
    FROM (
        SELECT
            m.instructor_reference_id,
            m.user_id,
            count(*) OVER (
                PARTITION BY m.instructor_reference_id
            ) AS match_count
        FROM matches m
    ) counted
    WHERE match_count = 1
)
UPDATE course_instructor_references r
SET instructor_name = u.full_name,
    user_id = m.user_id
FROM unique_matches m
JOIN users u ON u.user_id = m.user_id
WHERE r.instructor_reference_id = m.instructor_reference_id
  AND (
      r.user_id IS DISTINCT FROM m.user_id
      OR r.instructor_name IS DISTINCT FROM u.full_name
  )
"""

_MERGE_DUPLICATES_SQL = f"""
WITH ranked AS (
    SELECT
        instructor_reference_id,
        row_number() OVER (
            PARTITION BY
                curriculum_course_id,
                {_NORMALIZED_NAME_SQL.format(source='instructor_name')},
                instructor_role
            ORDER BY (user_id IS NULL), instructor_reference_id
        ) AS position
    FROM course_instructor_references
)
DELETE FROM course_instructor_references r
USING ranked k
WHERE r.instructor_reference_id = k.instructor_reference_id
  AND k.position > 1
"""

_BACKFILL_PJMK_SQL = """
WITH candidates AS (
    SELECT
        r.instructor_reference_id,
        row_number() OVER (
            PARTITION BY r.curriculum_course_id
            ORDER BY (r.user_id IS NULL), r.instructor_reference_id
        ) AS position
    FROM course_instructor_references r
    WHERE r.instructor_name LIKE '%,%'
      AND r.instructor_name NOT ILIKE 'tim pengajar%'
      AND NOT EXISTS (
          SELECT 1
          FROM course_instructor_references p
          WHERE p.curriculum_course_id = r.curriculum_course_id
            AND p.instructor_role = 'pjmk'
      )
)
UPDATE course_instructor_references r
SET instructor_role = 'pjmk'
FROM candidates c
WHERE r.instructor_reference_id = c.instructor_reference_id
  AND c.position = 1
"""

_RESET_PJMK_SQL = """
UPDATE course_instructor_references
SET instructor_role = 'teaching_team'
WHERE instructor_role = 'pjmk'
"""


def upgrade() -> None:
    bind = op.get_bind()
    titles = _TITLES_SQL
    bind.execute(text(_MAP_REFERENCES_SQL.format(titles=titles)))
    bind.execute(text(_MERGE_DUPLICATES_SQL))
    bind.execute(text(_BACKFILL_PJMK_SQL))


def downgrade() -> None:
    # Catatan: seluruh baris pjmk menjadi teaching_team; status PJ MK hilang.
    op.get_bind().execute(text(_RESET_PJMK_SQL))
