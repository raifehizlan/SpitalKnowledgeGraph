"""Record which model and prompt produced an assertion."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261111_0005"
down_revision = "20261110_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assertion", sa.Column("model_name", sa.String(length=128), nullable=True))
    op.add_column("assertion", sa.Column("prompt_version", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("assertion", "prompt_version")
    op.drop_column("assertion", "model_name")
