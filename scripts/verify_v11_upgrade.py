"""Rehearse v1.1 on an SQLite backup without changing the live database."""
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

from backup import backup

ROOT = Path(__file__).resolve().parents[1]
TABLES = ('users', 'auth_sessions', 'table_sessions', 'order_batches', 'order_items', 'order_item_modifiers', 'payments', 'print_jobs', 'audit_logs')


def snapshot(path):
    with closing(sqlite3.connect(path)) as db:
        return {table: ([row[1] for row in db.execute(f'PRAGMA table_info({table})')], db.execute(f'SELECT * FROM {table} ORDER BY id').fetchall()) for table in TABLES}


def verify(path, before):
    counts = {}
    with closing(sqlite3.connect(path)) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
        for table, (columns, original) in before.items():
            assert db.execute(f'SELECT {", ".join(columns)} FROM {table} ORDER BY id').fetchall() == original, f'Historical records changed: {table}'
            counts[table] = len(original)
    return counts


def main():
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    source = ROOT / 'backend/data/pos.db'
    saved = ROOT / f'backups/pre-v11-{stamp}.db'
    trial = ROOT / f'artifacts/upgrade/pos-{stamp}.db'
    backup(source, saved)
    backup(saved, trial)
    before = snapshot(trial)
    env = {**os.environ, 'DATABASE_URL': f'sqlite:///{trial.as_posix()}', 'PYTHONUTF8': '1'}
    for _ in range(2):
        subprocess.run([sys.executable, '-m', 'app.database.initialize'], cwd=ROOT / 'backend', env=env, check=True)
    report = {'backup': str(saved), 'trial_database': str(trial), 'preserved_records': verify(trial, before), 'repeated_migration_and_seed': 'passed'}
    (ROOT / 'artifacts/upgrade/result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
