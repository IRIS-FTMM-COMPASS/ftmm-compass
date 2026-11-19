"""relax curriculum assignment validation for deactivation

Revision ID: f8a5c3e1b2d4
Revises: e7a4b2c9d1f3
Create Date: 2026-11-19 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

revision: str = 'f8a5c3e1b2d4'
down_revision: str | Sequence[str] | None = 'e7a4b2c9d1f3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_VALIDATE = """
CREATE OR REPLACE FUNCTION validate_student_curriculum_assignment()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_profile_program uuid;
    v_curriculum_program uuid;
BEGIN
    SELECT study_program_id INTO v_profile_program FROM student_profiles WHERE user_id = NEW.user_id;
    IF v_profile_program IS NULL THEN
        RAISE EXCEPTION 'student profile does not exist for user %', NEW.user_id;
    END IF;

    -- Menonaktifkan penugasan lama saat koreksi prodi tidak boleh diblokir
    -- oleh kurikulum lama; penugasan aktif tetap tervalidasi penuh.
    IF TG_OP = 'UPDATE' AND OLD.is_current AND NOT NEW.is_current THEN
        RETURN NEW;
    END IF;

    SELECT study_program_id INTO v_curriculum_program FROM curricula WHERE curriculum_id = NEW.curriculum_id;
    IF v_curriculum_program IS NULL OR v_profile_program <> v_curriculum_program THEN
        RAISE EXCEPTION 'assigned curriculum must belong to the student profile study program';
    END IF;

    IF NEW.assignment_source = 'student_change' AND NEW.assigned_by_user_id IS DISTINCT FROM NEW.user_id THEN
        RAISE EXCEPTION 'student_change must be initiated by the same user';
    END IF;

    IF NEW.assignment_source = 'admin_override' THEN
        IF NEW.assigned_by_user_id IS NULL OR NOT EXISTS (
            SELECT 1 FROM users u
            WHERE u.user_id = NEW.assigned_by_user_id
              AND u.role IN ('faculty_staff','admin')
              AND u.is_active
        ) THEN
            RAISE EXCEPTION 'admin_override requires an active faculty_staff/admin actor';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;
"""

_ORIGINAL = """
CREATE OR REPLACE FUNCTION validate_student_curriculum_assignment()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_profile_program uuid;
    v_curriculum_program uuid;
BEGIN
    SELECT study_program_id INTO v_profile_program FROM student_profiles WHERE user_id = NEW.user_id;
    IF v_profile_program IS NULL THEN
        RAISE EXCEPTION 'student profile does not exist for user %', NEW.user_id;
    END IF;

    SELECT study_program_id INTO v_curriculum_program FROM curricula WHERE curriculum_id = NEW.curriculum_id;
    IF v_curriculum_program IS NULL OR v_profile_program <> v_curriculum_program THEN
        RAISE EXCEPTION 'assigned curriculum must belong to the student profile study program';
    END IF;

    IF NEW.assignment_source = 'student_change' AND NEW.assigned_by_user_id IS DISTINCT FROM NEW.user_id THEN
        RAISE EXCEPTION 'student_change must be initiated by the same user';
    END IF;

    IF NEW.assignment_source = 'admin_override' THEN
        IF NEW.assigned_by_user_id IS NULL OR NOT EXISTS (
            SELECT 1 FROM users u
            WHERE u.user_id = NEW.assigned_by_user_id
              AND u.role IN ('faculty_staff','admin')
              AND u.is_active
        ) THEN
            RAISE EXCEPTION 'admin_override requires an active faculty_staff/admin actor';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;
"""


def upgrade() -> None:
    op.execute(_VALIDATE)


def downgrade() -> None:
    op.execute(_ORIGINAL)
