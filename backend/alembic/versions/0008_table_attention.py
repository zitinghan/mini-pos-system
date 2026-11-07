"""Remember staff acknowledgement of long-running table sessions."""
from alembic import op
import sqlalchemy as sa

revision = '0008_table_attention'
down_revision = '0007_table_controls'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('table_sessions', sa.Column('wait_alert_acknowledged_at', sa.String(), nullable=True))


def downgrade():
    raise RuntimeError('Destructive downgrade disabled; restore a verified backup instead')
