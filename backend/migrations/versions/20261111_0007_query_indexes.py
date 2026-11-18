"""indexes for import publication and the dashboard's recent searches

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-11 20:40:00

Found by the Phase 3 index review (docs/performance-benchmarks.md): publishing an import deletes a
provider's departures by date range, and the dashboard lists a user's latest searches.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("departures", schema=None) as batch_op:
        batch_op.create_index("ix_departures_provider_date", ["provider_id", "travel_date"], unique=False)
    with op.batch_alter_table("journey_searches", schema=None) as batch_op:
        batch_op.drop_index("ix_journey_searches_user_id")
        batch_op.create_index("ix_journey_searches_user_created", ["user_id", "created_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("journey_searches", schema=None) as batch_op:
        batch_op.drop_index("ix_journey_searches_user_created")
        batch_op.create_index("ix_journey_searches_user_id", ["user_id"], unique=False)
    with op.batch_alter_table("departures", schema=None) as batch_op:
        batch_op.drop_index("ix_departures_provider_date")
