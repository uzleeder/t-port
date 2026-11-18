"""user preferences and aggregate booking redirect counts

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-11 20:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "user_preferences",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("modes", JSON, nullable=False),
        sa.Column("prefer_modes", JSON, nullable=False),
        sa.Column("sort", sa.String(length=16), nullable=False),
        sa.Column("max_transfers", sa.Integer(), nullable=False),
        sa.Column("max_price", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("max_transfers >= 0 AND max_transfers <= 2", name="ck_user_preferences_transfers"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "booking_redirect_counts",
        sa.Column("provider_id", sa.String(length=64), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("provider_id", "day"),
    )


def downgrade() -> None:
    op.drop_table("booking_redirect_counts")
    op.drop_table("user_preferences")
