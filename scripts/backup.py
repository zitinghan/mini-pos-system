#!/usr/bin/env python3
"""SQLite online backup and offline restore, usable inside the backend container."""
import argparse
from contextlib import closing
import os
import secrets
from pathlib import Path
import sqlite3
import tempfile


def backup(source: Path, target: Path):
    if not source.is_file():
        raise ValueError('Source database does not exist')
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ValueError('Backup destination already exists')
    descriptor, temporary = tempfile.mkstemp(dir=target.parent, suffix='.sqlite-tmp')
    os.close(descriptor)
    try:
        with closing(sqlite3.connect(f'{source.resolve().as_uri()}?mode=ro', uri=True)) as live, closing(sqlite3.connect(temporary)) as copy:
            live.backup(copy)
            if copy.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('Backup failed integrity check')
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def restore(source: Path, target: Path, stopped: bool):
    if not stopped:
        raise ValueError('Stop backend, worker and init before restoring; pass --services-stopped')
    with closing(sqlite3.connect(f'{source.resolve().as_uri()}?mode=ro', uri=True)) as database:
        if database.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Source backup failed integrity check')
        if database.execute("SELECT name FROM sqlite_master WHERE name='alembic_version'").fetchone() is None:
            raise ValueError('Not a migrated POS database')
    if target.exists():
        backup(target, target.with_name(target.name + '.before-restore-' + secrets.token_hex(8)))
    for suffix in ('-wal', '-shm'):
        Path(str(target) + suffix).unlink(missing_ok=True)
    temporary = target.with_name(target.name + '.restore-tmp')
    backup(source, temporary)
    os.replace(temporary, target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['backup', 'restore'])
    parser.add_argument('source', type=Path)
    parser.add_argument('target', type=Path)
    parser.add_argument('--services-stopped', action='store_true')
    args = parser.parse_args()
    if args.action == 'backup':
        backup(args.source, args.target)
    else:
        restore(args.source, args.target, args.services_stopped)
    print(f'{args.action} complete: {args.target}')

if __name__ == '__main__':
    main()
