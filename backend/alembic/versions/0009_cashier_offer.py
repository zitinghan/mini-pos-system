"""Keep original totals and cashier offer details alongside actual payments."""
from alembic import op
import sqlalchemy as sa

revision = '0009_cashier_offer'
down_revision = '0008_table_attention'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('payments', sa.Column('original_total', sa.Integer(), nullable=True))
    op.add_column('payments', sa.Column('offer_reason', sa.String(), nullable=False, server_default=''))
    op.execute('UPDATE payments SET original_total=total')


def downgrade():
    raise RuntimeError('Destructive downgrade disabled; restore a verified backup instead')
