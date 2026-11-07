"""Save customer receipts and route their payment-linked print jobs independently."""
from alembic import op
import sqlalchemy as sa

revision = '0004_receipts'
down_revision = '0003_stock_promotions'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('receipts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('created_at', sa.String(), nullable=False),
        sa.Column('updated_at', sa.String(), nullable=False),
        sa.Column('payment_id', sa.Integer(), sa.ForeignKey('payments.id'), nullable=False, unique=True),
        sa.Column('snapshot', sa.JSON(), nullable=False),
    )
    op.execute('ALTER TABLE print_jobs ADD COLUMN payment_id INTEGER REFERENCES payments(id)')
    op.add_column('print_jobs', sa.Column('printer_mode', sa.String(), nullable=True))
    op.create_index('ix_print_jobs_payment_id', 'print_jobs', ['payment_id'])
    op.create_index('uq_active_print_payment', 'print_jobs', ['payment_id'], unique=True,
                    sqlite_where=sa.text("status IN ('PENDING','SENDING')"))
    op.create_index('uq_original_receipt_print', 'print_jobs', ['payment_id'], unique=True,
                    sqlite_where=sa.text('reprint = 0 AND payment_id IS NOT NULL'))


def downgrade():
    raise RuntimeError('Destructive downgrade disabled; restore a verified backup instead')
