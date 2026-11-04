#!/usr/bin/env python3
"""Dependency-free verification of frozen migration, concurrency and safe backups."""
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('backup', ROOT / 'scripts/backup.py')
backup_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup_module)

credentials_spec = importlib.util.spec_from_file_location('credentials', ROOT / 'backend/app/core/credentials.py')
credentials = importlib.util.module_from_spec(credentials_spec)
credentials_spec.loader.exec_module(credentials)

class CredentialInvariants(unittest.TestCase):
    def test_salted_pin_hash_and_verification(self):
        first = credentials.hash_pin('928461')
        second = credentials.hash_pin('928461')
        self.assertNotEqual(first, second)
        self.assertNotEqual(first, '928461')
        self.assertTrue(credentials.verify_pin('928461', first))
        self.assertFalse(credentials.verify_pin('111111', first))
        self.assertFalse(credentials.verify_pin('928461', 'invalid-record'))

    def test_token_fingerprint(self):
        fingerprint = credentials.token_hash('opaque-test-token')
        self.assertEqual(len(fingerprint), 64)
        self.assertEqual(fingerprint, credentials.token_hash('opaque-test-token'))
        self.assertNotEqual(fingerprint, 'opaque-test-token')

class DatabaseInvariants(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'pos.db'
        self.database = sqlite3.connect(self.path)
        self.database.execute('PRAGMA foreign_keys=ON')
        self.database.execute('PRAGMA journal_mode=WAL')
        self.database.executescript((ROOT / 'backend/alembic/versions/0001_schema.sql').read_text())
        self.database.execute('CREATE TABLE alembic_version (version_num TEXT PRIMARY KEY)')
        self.database.execute("INSERT INTO alembic_version VALUES ('0001')")
        self.database.execute("INSERT INTO restaurant_tables VALUES (1,'now','now','T01')")
        self.database.commit()

    def tearDown(self):
        self.database.close()
        self.directory.cleanup()

    def test_frozen_schema_and_foreign_keys(self):
        self.assertEqual(self.database.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        tables = {r[0] for r in self.database.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({'users','payments','print_jobs','order_items','table_sessions'}.issubset(tables))
        with self.assertRaises(sqlite3.IntegrityError):
            self.database.execute("INSERT INTO table_sessions VALUES (1,'now','now',999,'OCCUPIED',NULL)")

    def test_unique_active_table_and_reopen_after_paid(self):
        self.database.execute("INSERT INTO table_sessions VALUES (1,'now','now',1,'OCCUPIED',NULL)")
        with self.assertRaises(sqlite3.IntegrityError):
            self.database.execute("INSERT INTO table_sessions VALUES (2,'now','now',1,'PAYMENT_PENDING',NULL)")
        self.database.execute("UPDATE table_sessions SET status='PAID' WHERE id=1")
        self.database.execute("INSERT INTO table_sessions VALUES (2,'now','now',1,'OCCUPIED',NULL)")

    def test_concurrent_open_constraint(self):
        def open_table(_):
            db = sqlite3.connect(self.path, timeout=10)
            try:
                db.execute('BEGIN IMMEDIATE')
                db.execute("INSERT INTO table_sessions(created_at,updated_at,table_id,status) VALUES ('now','now',1,'OCCUPIED')")
                db.commit()
                return True
            except sqlite3.IntegrityError:
                db.rollback()
                return False
            finally:
                db.close()
        with ThreadPoolExecutor(max_workers=6) as pool:
            self.assertEqual(sum(pool.map(open_table, range(6))), 1)

    def test_unique_payment_and_submission_keys(self):
        self.database.execute("INSERT INTO users VALUES (1,'now','now','admin','hashed','ADMIN',0,NULL)")
        self.database.execute("INSERT INTO table_sessions VALUES (1,'now','now',1,'OCCUPIED',NULL)")
        self.database.execute("INSERT INTO order_batches VALUES (1,'now','now',1,1,'SUBMITTED','request-123','now')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.database.execute("INSERT INTO order_batches VALUES (2,'now','now',1,1,'SUBMITTED','request-123','now')")
        self.database.execute("INSERT INTO payments VALUES (1,'now','now',1,1,'pay-key','hash','CASH',2900,5000,2100)")
        with self.assertRaises(sqlite3.IntegrityError):
            self.database.execute("INSERT INTO payments VALUES (2,'now','now',1,1,'other-key','hash','CASH',2900,5000,2100)")

    def test_repeated_restores_preserve_distinct_safety_copies(self):
        destination = Path(self.directory.name) / 'backup.db'
        backup_module.backup(self.path, destination)
        self.database.close()
        try:
            backup_module.restore(destination, self.path, True)
            backup_module.restore(destination, self.path, True)
            copies = list(Path(self.directory.name).glob('pos.db.before-restore-*'))
            self.assertEqual(len(copies), 2)
        finally:
            self.database = sqlite3.connect(self.path)

    def test_online_backup_preserves_wal_and_restore(self):
        destination = Path(self.directory.name) / 'backup.db'
        backup_module.backup(self.path, destination)
        with sqlite3.connect(destination) as copy:
            self.assertEqual(copy.execute('SELECT name FROM restaurant_tables').fetchone()[0], 'T01')
        with self.assertRaises(ValueError):
            backup_module.restore(destination, self.path, False)
        self.database.close()
        backup_module.restore(destination, self.path, True)
        self.database = sqlite3.connect(self.path)
        self.assertEqual(self.database.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

if __name__ == '__main__':
    unittest.main(verbosity=2)
