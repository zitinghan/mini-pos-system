"""Keep original payments intact when a cashier restores an accidentally closed table."""
from alembic import op
import sqlalchemy as sa

revision = '0010_payment_reversals'
down_revision = '0009_cashier_offer'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('payment_reversals',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('created_at', sa.String(), nullable=False),
        sa.Column('updated_at', sa.String(), nullable=False),
        sa.Column('payment_id', sa.Integer(), sa.ForeignKey('payments.id'), nullable=False, unique=True),
        sa.Column('restored_session_id', sa.Integer(), sa.ForeignKey('table_sessions.id'), nullable=False, unique=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('reason', sa.String(), nullable=False))


def downgrade():
    raise RuntimeError('Destructive downgrade disabled; restore a verified backup instead')
