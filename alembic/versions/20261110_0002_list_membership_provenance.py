"""Provenance columns for cantonal-list membership."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261110_0002"
down_revision = "20261110_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("list_membership", sa.Column("source_file_id", sa.Uuid(), nullable=True))
    op.add_column(
        "list_membership",
        sa.Column("source_row_fingerprint", sa.String(length=128), nullable=True),
    )
    op.create_foreign_key(
        "list_membership_source_file_id_fkey",
        "list_membership",
        "source_file",
        ["source_file_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("list_membership_source_file_id_fkey", "list_membership", type_="foreignkey")
    op.drop_column("list_membership", "source_row_fingerprint")
    op.drop_column("list_membership", "source_file_id")
