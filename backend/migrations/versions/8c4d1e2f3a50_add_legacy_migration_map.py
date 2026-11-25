"""add FK-backed legacy scheduling migration provenance

Revision ID: 8c4d1e2f3a50
Revises: 7f3c9a2d1e40
Create Date: 2026-11-25 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "8c4d1e2f3a50"
down_revision: str | Sequence[str] | None = "7f3c9a2d1e40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS scheduling_legacy_migration_state (
            singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
            target_academic_period_id UUID NOT NULL
                REFERENCES academic_periods(academic_period_id) ON DELETE RESTRICT,
            migration_revision VARCHAR(32) NOT NULL,
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS legacy_availability_migration_map (
            availability_id UUID NOT NULL
                REFERENCES lecturer_availability(availability_id) ON DELETE CASCADE,
            academic_period_id UUID NOT NULL
                REFERENCES academic_periods(academic_period_id) ON DELETE CASCADE,
            preference_id UUID
                REFERENCES lecturer_schedule_preferences(preference_id) ON DELETE SET NULL,
            payload_fingerprint CHAR(64),
            migration_revision VARCHAR(32) NOT NULL,
            status VARCHAR(16) NOT NULL CHECK (status IN ('copied', 'skipped')),
            skip_reason VARCHAR(64),
            copied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (availability_id, academic_period_id),
            CONSTRAINT ck_legacy_availability_map_payload CHECK (
                (status = 'copied' AND payload_fingerprint IS NOT NULL AND skip_reason IS NULL)
                OR
                (status = 'skipped' AND payload_fingerprint IS NULL AND skip_reason IS NOT NULL)
            )
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_legacy_availability_map_period
        ON legacy_availability_migration_map (academic_period_id)
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS legacy_instructor_reference_migration_map (
            instructor_reference_id UUID NOT NULL
                REFERENCES course_instructor_references(instructor_reference_id) ON DELETE CASCADE,
            academic_period_id UUID NOT NULL
                REFERENCES academic_periods(academic_period_id) ON DELETE CASCADE,
            target_reference_id UUID
                REFERENCES course_instructor_references(instructor_reference_id) ON DELETE SET NULL,
            payload_fingerprint CHAR(64),
            migration_revision VARCHAR(32) NOT NULL,
            status VARCHAR(16) NOT NULL CHECK (status IN ('copied', 'skipped')),
            skip_reason VARCHAR(64),
            copied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (instructor_reference_id, academic_period_id),
            CONSTRAINT ck_legacy_reference_map_payload CHECK (
                (status = 'copied' AND payload_fingerprint IS NOT NULL AND skip_reason IS NULL)
                OR
                (status = 'skipped' AND payload_fingerprint IS NULL AND skip_reason IS NOT NULL)
            )
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_legacy_reference_map_period
        ON legacy_instructor_reference_migration_map (academic_period_id)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS legacy_instructor_reference_migration_map")
    op.execute("DROP TABLE IF EXISTS legacy_availability_migration_map")
    op.execute("DROP TABLE IF EXISTS scheduling_legacy_migration_state")
