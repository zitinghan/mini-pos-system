from alembic.config import Config
from alembic import command
from app.database.seed import seed


def main():
    command.upgrade(Config('alembic.ini'), 'head')
    seed()

if __name__ == '__main__':
    main()
