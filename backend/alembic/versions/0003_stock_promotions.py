"""Add shared sold-out availability and scheduled menu promotions."""
from alembic import op
import sqlalchemy as sa

revision = '0003_stock_promotions'
down_revision = '0002_v11'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('menu_items', sa.Column('sold_out', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table('menu_promotions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('created_at', sa.String(), nullable=False),
        sa.Column('updated_at', sa.String(), nullable=False),
        sa.Column('code', sa.String(), nullable=False, unique=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('unit_price', sa.Integer(), nullable=False),
        sa.Column('starts_on', sa.String(), nullable=False),
        sa.Column('ends_on', sa.String(), nullable=False),
        sa.Column('skus', sa.JSON(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint('unit_price > 0'),
    )


def downgrade():
    raise RuntimeError('Destructive downgrade disabled; restore a verified backup instead')
