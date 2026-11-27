"""migrate legacy scheduling to the active period

Revision ID: 9d5e2f3a4b61
Revises: 8c4d1e2f3a50
Create Date: 2026-11-25 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

from scheduling_legacy_migration import (
    rollback_legacy_scheduling,
    upgrade_legacy_scheduling,
)

revision: str = "9d5e2f3a4b61"
down_revision: str | Sequence[str] | None = "8c4d1e2f3a50"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    result = upgrade_legacy_scheduling(op.get_bind())
    print(
        "Legacy scheduling migration "
        f"status={result.status} period={result.academic_period_id} "
        f"sources={result.availability_sources}/{result.reference_sources} "
        f"availability={result.availability_inserted}/"
        f"{result.availability_skipped_existing}/"
        f"{result.availability_conflicts}/{result.availability_rerun} "
        f"references={result.references_inserted}/"
        f"{result.references_skipped_existing}/"
        f"{result.references_conflicts}/{result.references_rerun} "
        "counts=inserted/skipped/conflict/rerun "
        f"integrity_errors={len(result.integrity_errors)}"
        f"provenance={result.provenance_copied}/{result.provenance_skipped} "
        f"cleared={result.cleared_preference_copies}/{result.cleared_reference_copies} "
        f"modified={result.modified_preference_copies}/{result.modified_reference_copies} "
    )


def downgrade() -> None:
    result = rollback_legacy_scheduling(op.get_bind())
    print(
        "Legacy scheduling rollback "
        f"preferences={result.preferences_deleted}/"
        f"{result.preferences_preserved_modified}/"
        f"{result.preferences_already_deleted} "
        f"references={result.references_deleted}/"
        f"{result.references_preserved_modified}/"
        f"{result.references_already_deleted} "
        "counts=deleted/preserved_modified/already_deleted "
        f"provenance_deleted={result.provenance_deleted}"
    )
