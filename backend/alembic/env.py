from alembic import context
from app.database.db import engine, Base
from app.models import entities  # noqa: F401 -- registers migration metadata

with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()
