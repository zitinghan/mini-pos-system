"""Initial versioned POS schema.

Revision ID: 0001
"""
from alembic import op

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

# Frozen SQL schema is loaded instead of deriving migrations from future ORM changes.
def upgrade():
    from pathlib import Path
    statements = Path(__file__).with_name('0001_schema.sql').read_text().split(';')
    for statement in statements:
        if statement.strip():
            op.execute(statement)


def downgrade():
    raise RuntimeError('Destructive downgrade disabled; restore a verified backup instead')
