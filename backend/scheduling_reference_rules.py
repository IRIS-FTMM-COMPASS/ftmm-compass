"""Aturan referensi dosen: normalisasi nama, merger duplikat, backfill PJ MK.

SQL di sini adalah salinan beku dari migrasi b7d2e4f6a8c1. Seed memakainya ulang
agar hasil seeding konsisten dengan hasil migrasi: nama orang dinormalisasi ke
akun dosen, baris identik digabung, dan setiap mata kuliah yang punya referensi
berformat orang mendapat tepat satu PJ MK.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_TITLES_SQL = (
    "ARRAY['dr','ir','prof','drs','dra','eng','hj','h','cand','sp','btkv','k']"
)

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

_NORMALIZED_NAME_SQL = "lower(regexp_replace(btrim({source}), '\\s+', ' ', 'g'))"

MAP_REFERENCES_SQL = f"""
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

MERGE_DUPLICATES_SQL = f"""
WITH ranked AS (
    SELECT
        instructor_reference_id,
        row_number() OVER (
            PARTITION BY
                curriculum_course_id,
                academic_period_id,
                {_NORMALIZED_NAME_SQL.format(source='instructor_name')},
                instructor_role
            ORDER BY (user_id IS NULL), position NULLS LAST, instructor_reference_id
        ) AS position
    FROM course_instructor_references
)
DELETE FROM course_instructor_references r
USING ranked k
WHERE r.instructor_reference_id = k.instructor_reference_id
  AND k.position > 1
"""

BACKFILL_PJMK_SQL = """
WITH candidates AS (
    SELECT
        r.instructor_reference_id,
        row_number() OVER (
            PARTITION BY r.curriculum_course_id, r.academic_period_id
            ORDER BY (r.user_id IS NULL), r.position NULLS LAST, r.instructor_reference_id
        ) AS position
    FROM course_instructor_references r
    WHERE r.instructor_name LIKE '%,%'
      AND r.instructor_name NOT ILIKE 'tim pengajar%'
      AND (
          r.academic_period_id IS NULL
          OR EXISTS (
              SELECT 1
              FROM users u
              JOIN lecturer_profiles lp ON lp.user_id = u.user_id
              WHERE u.user_id = r.user_id
                AND u.role = 'lecturer'
                AND u.is_active
          )
      )
      AND NOT EXISTS (
          SELECT 1
          FROM course_instructor_references p
          WHERE p.curriculum_course_id = r.curriculum_course_id
            AND p.academic_period_id IS NOT DISTINCT FROM r.academic_period_id
            AND p.instructor_role = 'pjmk'
      )
)
UPDATE course_instructor_references r
SET instructor_role = 'pjmk'
FROM candidates c
WHERE r.instructor_reference_id = c.instructor_reference_id
  AND c.position = 1
"""


async def apply_instructor_reference_rules(session: AsyncSession) -> None:
    await session.execute(text(MAP_REFERENCES_SQL.format(titles=_TITLES_SQL)))
    await session.execute(text(MERGE_DUPLICATES_SQL))
    await session.execute(text(BACKFILL_PJMK_SQL))
