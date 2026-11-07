"""Freeze paid-first amounts and keep final method allocations with the payment."""
from alembic import op
import sqlalchemy as sa

revision = '0012_prepaid_balances'
down_revision = '0011_prepaid_method'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('order_batches', sa.Column('prepaid_amount', sa.Integer(), nullable=True))
    op.add_column('payments', sa.Column('settlement', sa.JSON(), nullable=True))


def downgrade():
    raise RuntimeError('Destructive downgrade disabled; restore a verified backup instead')
