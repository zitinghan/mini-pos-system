"""Unpaid cancellations, editable remarks and manual per-round paid labels."""
from alembic import op
import sqlalchemy as sa

revision = '0007_table_controls'
down_revision = '0006_order_editing'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('table_sessions', sa.Column('notes', sa.String(), nullable=False, server_default=''))
    op.add_column('table_sessions', sa.Column('metadata_revision', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('order_batches', sa.Column('prepaid_label', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('order_batches', sa.Column('info_revision', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('order_items', sa.Column('cancellation_reason', sa.String(), nullable=False, server_default=''))
    op.execute('ALTER TABLE print_jobs ADD COLUMN session_id INTEGER REFERENCES table_sessions(id)')
    op.create_index('ix_print_jobs_session_id', 'print_jobs', ['session_id'])
    op.execute('UPDATE print_jobs SET session_id=(SELECT session_id FROM order_batches WHERE id=print_jobs.batch_id) WHERE batch_id IS NOT NULL')
    op.execute('UPDATE print_jobs SET session_id=(SELECT session_id FROM payments WHERE id=print_jobs.payment_id) WHERE payment_id IS NOT NULL')


def downgrade():
    raise RuntimeError('Destructive downgrade disabled; restore a verified backup instead')
