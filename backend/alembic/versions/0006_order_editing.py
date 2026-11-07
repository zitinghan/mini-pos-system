"""Order notes and revisioned unpaid edits with independent correction print jobs."""
from alembic import op
import sqlalchemy as sa

revision = '0006_order_editing'
down_revision = '0005_rice_stall'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('order_batches', sa.Column('notes', sa.String(), nullable=False, server_default=''))
    op.add_column('order_items', sa.Column('revision', sa.Integer(), nullable=False, server_default='1'))
    op.execute('ALTER TABLE print_jobs ADD COLUMN change_id INTEGER REFERENCES audit_logs(id)')
    op.create_index('ix_print_jobs_change_id', 'print_jobs', ['change_id'])
    op.drop_index('uq_active_print_batch', table_name='print_jobs')
    op.create_index('uq_active_print_batch', 'print_jobs', ['batch_id', 'routing_group'], unique=True,
        sqlite_where=sa.text("status IN ('PENDING','SENDING') AND change_id IS NULL"))
    op.create_index('uq_active_print_change', 'print_jobs', ['change_id', 'routing_group'], unique=True,
        sqlite_where=sa.text("status IN ('PENDING','SENDING') AND change_id IS NOT NULL"))


def downgrade():
    raise RuntimeError('Destructive downgrade disabled; restore a verified backup instead')
