"""Official Leistungsauftrag rows from a cantonal hospital list.

A row is a service mandate. It is not a department and it has no site.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261111_0006"
down_revision = "20261111_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "service_mandate" in sa.inspect(bind).get_table_names():
        return
    op.create_table(
        "service_mandate",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("hospital_organization.id"), nullable=True),
        sa.Column("source_file_id", sa.Uuid(), sa.ForeignKey("source_file.id"), nullable=True),
        sa.Column("list_kind", sa.String(32), nullable=False),
        sa.Column("edition", sa.String(32), nullable=False),
        sa.Column("canton_scope", sa.String(32), nullable=False),
        sa.Column("source_name", sa.Text(), nullable=False),
        sa.Column("code", sa.String(32), nullable=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("match_status", sa.String(32), nullable=False),
        sa.Column("source_row_fingerprint", sa.String(128), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("service_mandate")
