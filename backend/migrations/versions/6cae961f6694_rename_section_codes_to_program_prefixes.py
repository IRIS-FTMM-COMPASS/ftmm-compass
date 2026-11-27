"""rename section codes to program prefixes

Revision ID: 6cae961f6694
Revises: 250f3ad3a3e8
Create Date: 2026-11-26 01:25:20.011535

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '6cae961f6694'
down_revision: Union[str, Sequence[str], None] = '250f3ad3a3e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE class_sections SET legacy_section_code = section_code "
        "WHERE legacy_section_code IS NULL"
    )
    op.execute(
        """
        UPDATE class_sections cs
        SET section_code = 'tmp' || lpad(ranked.ordinal::text, 6, '0')
        FROM (
            SELECT class_section_id,
                   row_number() OVER (
                       PARTITION BY offering_component_id ORDER BY section_code
                   ) AS ordinal
            FROM class_sections
        ) ranked
        WHERE cs.class_section_id = ranked.class_section_id
        """
    )
    op.execute(
        """
        WITH context AS (
            SELECT cs.class_section_id,
                   count(DISTINCT sp.program_code) AS program_count,
                   bool_or(cc.course_scope IN ('fakultas', 'universitas')) AS shared_scope,
                   min(sp.program_code) AS program_code
            FROM class_sections cs
            LEFT JOIN offering_components oc
                ON oc.offering_component_id = cs.offering_component_id
            LEFT JOIN course_offerings co
                ON co.course_offering_id = oc.course_offering_id
            LEFT JOIN course_offering_eligibilities coe
                ON coe.course_offering_id = co.course_offering_id
            LEFT JOIN curriculum_courses cc
                ON cc.curriculum_course_id = coe.curriculum_course_id
            LEFT JOIN curricula cur ON cur.curriculum_id = cc.curriculum_id
            LEFT JOIN study_programs sp
                ON sp.study_program_id = cur.study_program_id
            GROUP BY cs.class_section_id
        ), ranked AS (
            SELECT class_section_id,
                   row_number() OVER (
                       PARTITION BY offering_component_id ORDER BY section_code
                   ) AS ordinal
            FROM class_sections
        )
        UPDATE class_sections cs
        SET section_code = CASE
                WHEN context.program_count > 1
                     OR context.shared_scope
                     OR context.program_code IS NULL THEN 'UM'
                WHEN context.program_code = 'TSD' THEN 'SD'
                WHEN context.program_code = 'TRKB' THEN 'RK'
                ELSE context.program_code
            END || '-A' || ranked.ordinal::text
        FROM context, ranked
        WHERE cs.class_section_id = context.class_section_id
          AND cs.class_section_id = ranked.class_section_id
        """
    )


def downgrade() -> None:
    op.execute(
        "UPDATE class_sections SET section_code = legacy_section_code "
        "WHERE legacy_section_code IS NOT NULL"
    )
