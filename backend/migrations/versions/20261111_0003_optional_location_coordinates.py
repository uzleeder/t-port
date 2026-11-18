"""Allow locations whose coordinates are unavailable."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("locations") as batch:
        batch.alter_column("latitude", existing_type=sa.Numeric(9, 6), nullable=True)
        batch.alter_column("longitude", existing_type=sa.Numeric(9, 6), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("locations") as batch:
        batch.alter_column("latitude", existing_type=sa.Numeric(9, 6), nullable=False)
        batch.alter_column("longitude", existing_type=sa.Numeric(9, 6), nullable=False)
