"""Initial system-of-record tables."""

from __future__ import annotations

from alembic import op

revision = "20261110_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    from swiss_hospital_intelligence.database.schema import Base

    bind = op.get_bind()
    Base.metadata.create_all(bind)


def downgrade() -> None:
    from swiss_hospital_intelligence.database.schema import Base

    bind = op.get_bind()
    Base.metadata.drop_all(bind)
