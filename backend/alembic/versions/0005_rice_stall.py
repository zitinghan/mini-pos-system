"""Per-item stall routing and menu priority, preserving order/print snapshots."""
from alembic import op
import sqlalchemy as sa

revision = '0005_rice_stall'
down_revision = '0004_receipts'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('menu_items', sa.Column('printer_group', sa.String(), nullable=True))
    op.add_column('menu_items', sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'))
    op.execute("UPDATE menu_items SET printer_group='RICE' WHERE sku='CURRY_RICE'")


def downgrade():
    raise RuntimeError('Destructive downgrade disabled; restore a verified backup instead')
