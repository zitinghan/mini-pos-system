"""Canned drinks have one RM3 price and no temperature selection."""
from alembic import op
import sqlalchemy as sa

revision = '0013_canned_fixed_price'
down_revision = '0012_prepaid_balances'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    connection.execute(sa.text("UPDATE menu_items SET base_price=300, verification_required=0, verification_note='' WHERE sku='CANNED'"))
    # Keep old groups/options and order snapshots for historical references.
    connection.execute(sa.text("""DELETE FROM menu_item_modifier_groups
        WHERE item_id IN (SELECT id FROM menu_items WHERE sku='CANNED')
        AND group_id IN (SELECT id FROM modifier_groups WHERE name=:temperature)"""), {'temperature': '温度'})


def downgrade():
    raise RuntimeError('Destructive downgrade disabled; restore a verified backup instead')
