"""Store an optional payment method with manual paid-first round labels."""
from alembic import op
import sqlalchemy as sa

revision = '0011_prepaid_method'
down_revision = '0010_payment_reversals'
branch_labels = None
depends_on = None


def upgrade():
    # Existing labels have unknown methods; never infer a historical cash/QR sale.
    op.add_column('order_batches', sa.Column('prepaid_method', sa.String(), nullable=True))


def downgrade():
    raise RuntimeError('Destructive downgrade disabled; restore a verified backup instead')
