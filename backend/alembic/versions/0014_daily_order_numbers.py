"""Separate visible daily order numbers from permanent database identities."""
from alembic import op
import sqlalchemy as sa

revision = '0014_daily_order_numbers'
down_revision = '0013_canned_fixed_price'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('order_batches', sa.Column('order_number', sa.Integer(), nullable=True))
    op.add_column('order_batches', sa.Column('business_day', sa.String(), nullable=True))
    # Keep every previously submitted order's displayed number unchanged.
    # Malaysia business date = UTC timestamp minus four hours (UTC+8, noon cutoff).
    op.execute("UPDATE order_batches SET order_number=id, business_day=date(submitted_at, '-4 hours') WHERE submitted_at IS NOT NULL")
    op.create_index('uq_order_number_per_day', 'order_batches', ['business_day', 'order_number'], unique=True)


def downgrade():
    raise RuntimeError('Destructive downgrade disabled; restore a verified backup instead')
