"""Add v1.1 menu variants, immutable order metadata, routing and dining times."""
from alembic import op
import sqlalchemy as sa

revision = '0002_v11'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    additions = {
        'table_sessions': [('opened_at', sa.String(), ''), ('first_order_at', sa.String(), None), ('paid_at', sa.String(), None)],
        'menu_categories': [('code', sa.String(), None), ('english_name', sa.String(), ''), ('printer_group', sa.String(), 'KITCHEN')],
        'menu_items': [('sku', sa.String(), None), ('description', sa.String(), ''), ('complimentary', sa.Boolean(), '0'), ('verification_required', sa.Boolean(), '0'), ('verification_note', sa.String(), '')],
        'modifier_options': [('unit_price', sa.Integer(), None), ('bottles', sa.Integer(), '0'), ('enabled', sa.Boolean(), '1'), ('incompatible_with', sa.JSON(), '[]')],
        'order_items': [('sku', sa.String(), None), ('category_code', sa.String(), 'MAINS'), ('printer_group', sa.String(), 'KITCHEN'), ('description', sa.String(), ''), ('variant_name', sa.String(), None), ('bottles_per_unit', sa.Integer(), '0'), ('physical_bottles', sa.Integer(), '0'), ('notes', sa.String(), '')],
        'print_jobs': [('routing_group', sa.String(), 'COMBINED')],
    }
    for table, columns in additions.items():
        for name, kind, default in columns:
            op.add_column(table, sa.Column(name, kind, nullable=default is None, server_default=default))
    op.create_index('uq_menu_category_code', 'menu_categories', ['code'], unique=True)
    op.create_index('uq_menu_item_sku', 'menu_items', ['sku'], unique=True)
    op.drop_index('uq_active_print_batch', table_name='print_jobs')
    op.create_index('uq_active_print_batch', 'print_jobs', ['batch_id', 'routing_group'], unique=True, sqlite_where=sa.text("status IN ('PENDING','SENDING')"))
    op.execute('UPDATE table_sessions SET opened_at = created_at')
    op.execute("UPDATE table_sessions SET first_order_at = (SELECT MIN(submitted_at) FROM order_batches WHERE session_id = table_sessions.id AND status = 'SUBMITTED')")
    op.execute('UPDATE table_sessions SET paid_at = (SELECT created_at FROM payments WHERE session_id = table_sessions.id)')
    # Payments have no inbound foreign keys. Copy every original column while allowing
    # a legitimately submitted complimentary-water-only table to close at RM0.
    op.execute('''CREATE TABLE payments_v11 (
        id INTEGER NOT NULL PRIMARY KEY, created_at VARCHAR NOT NULL, updated_at VARCHAR NOT NULL,
        session_id INTEGER NOT NULL UNIQUE REFERENCES table_sessions(id),
        user_id INTEGER NOT NULL REFERENCES users(id), idempotency_key VARCHAR NOT NULL UNIQUE,
        request_hash VARCHAR NOT NULL, method VARCHAR NOT NULL, total INTEGER NOT NULL,
        received INTEGER NOT NULL, change INTEGER NOT NULL,
        CHECK (method IN ('CASH','QR','OTHER')),
        CHECK (total >= 0 AND received >= total AND change = received - total))''')
    op.execute('INSERT INTO payments_v11 SELECT * FROM payments')
    op.drop_table('payments')
    op.rename_table('payments_v11', 'payments')
    op.create_index('ix_payments_created', 'payments', ['created_at'])


def downgrade():
    raise RuntimeError('Destructive downgrade disabled; restore a verified backup instead')
