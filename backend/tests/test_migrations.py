import os
import sqlite3
import subprocess
import sys


def test_migrate_seed_and_restart_without_data_loss(tmp_path):
    path = tmp_path / 'migration.db'
    env = {**os.environ, 'DATABASE_URL': f'sqlite:///{path}'}
    for _ in range(2):
        result = subprocess.run([sys.executable, '-m', 'app.database.initialize'], env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT COUNT(*) FROM restaurant_tables').fetchone()[0] == 15
        assert db.execute('SELECT COUNT(*) FROM menu_items').fetchone()[0] == 3
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == '0001'
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
