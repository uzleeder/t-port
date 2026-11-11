"""import lifecycle: progress, cancellation, diagnostics, widened status set

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-11 17:52:36.111795

Additive: new nullable columns or columns with server defaults, plus a wider status check.
Downgrade maps the new statuses (pending/validating/publishing/cancelled) to 'failed'
before restoring the old constraint; only Phase 2 audit detail is lost.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0004'
down_revision: str | None = '0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW = "status in ('pending','running','validating','publishing','succeeded','failed','cancelled')"
OLD = "status in ('running','succeeded','failed')"


def upgrade() -> None:
    with op.batch_alter_table('data_imports', schema=None) as batch_op:
        batch_op.add_column(sa.Column('requests_total', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('requests_done', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('cancel_requested', sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column('duration_ms', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column(
            'diagnostics', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'),
            nullable=True,
        ))
        batch_op.drop_constraint('ck_data_imports_status', type_='check')
        batch_op.create_check_constraint('ck_data_imports_status', NEW)


def downgrade() -> None:
    op.execute(
        "UPDATE data_imports SET status = 'failed' "
        "WHERE status IN ('pending','validating','publishing','cancelled')"
    )
    with op.batch_alter_table('data_imports', schema=None) as batch_op:
        batch_op.drop_constraint('ck_data_imports_status', type_='check')
        batch_op.create_check_constraint('ck_data_imports_status', OLD)
        batch_op.drop_column('diagnostics')
        batch_op.drop_column('duration_ms')
        batch_op.drop_column('cancel_requested')
        batch_op.drop_column('requests_done')
        batch_op.drop_column('requests_total')
