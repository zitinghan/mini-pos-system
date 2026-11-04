from contextlib import contextmanager
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.core.config import DATABASE_URL

if DATABASE_URL.startswith('sqlite:///'):
    Path(DATABASE_URL.removeprefix('sqlite:///')).parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False, 'timeout': 15})

@event.listens_for(engine, 'connect')
def configure_sqlite(connection, _):
    connection.isolation_level = None
    connection.execute('PRAGMA foreign_keys=ON')
    connection.execute('PRAGMA journal_mode=WAL')
    connection.execute('PRAGMA busy_timeout=15000')

@event.listens_for(engine, 'begin')
def begin(connection):
    connection.exec_driver_sql('BEGIN IMMEDIATE')

class Base(DeclarativeBase):
    pass

Session = sessionmaker(engine, expire_on_commit=False)

@contextmanager
def transaction():
    with Session.begin() as session:
        yield session
