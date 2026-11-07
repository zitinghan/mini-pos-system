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
        assert db.execute('SELECT COUNT(*) FROM menu_items').fetchone()[0] == 29
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == '0003_stock_promotions'
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'


def test_v1_upgrade_preserves_paid_history_and_adopts_legacy_names(tmp_path):
    path = tmp_path / 'legacy.db'
    env = {**os.environ, 'DATABASE_URL': f'sqlite:///{path}'}
    result = subprocess.run([sys.executable, '-c', "from alembic import command; from alembic.config import Config; command.upgrade(Config('alembic.ini'), '0001')"], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    created, submitted, paid = '2026-11-06T03:50:00+00:00', '2026-11-06T04:00:00+00:00', '2026-11-06T04:42:00+00:00'
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO users VALUES (1, ?, ?, 'owner', 'historical-hash', 'ADMIN', 0, NULL)", (created, created))
        db.execute("INSERT INTO restaurant_tables VALUES (1, ?, ?, 'T01')", (created, created))
        db.execute("INSERT INTO menu_categories VALUES (1, ?, ?, '面粉糕', 0)", (created, created))
        db.execute("INSERT INTO menu_items VALUES (1, ?, ?, 1, '面粉糕', 800, 1)", (created, created))
        db.execute("INSERT INTO table_sessions VALUES (1, ?, ?, 1, 'PAID', ?)", (created, paid, paid))
        db.execute("INSERT INTO order_batches VALUES (1, ?, ?, 1, 1, 'SUBMITTED', 'old-submit-key', ?)", (created, submitted, submitted))
        db.execute("INSERT INTO order_items VALUES (1, ?, ?, 1, 1, '面粉糕', 1, 800, 900, 900, 'SUBMITTED')", (created, submitted))
        db.execute("INSERT INTO payments VALUES (1, ?, ?, 1, 1, 'old-payment-key', 'original-fingerprint', 'CASH', 900, 1000, 100)", (paid, paid))
        original_payment = db.execute('SELECT * FROM payments').fetchall()
        original_item = db.execute('SELECT * FROM order_items').fetchall()
    for _ in range(2):
        result = subprocess.run([sys.executable, '-m', 'app.database.initialize'], env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT * FROM payments').fetchall() == original_payment
        assert [row[:11] for row in db.execute('SELECT * FROM order_items')] == original_item
        assert db.execute("SELECT id, name FROM menu_items WHERE sku = 'MEE_HOON_KUEH'").fetchone() == (1, '面粉粿')
        assert db.execute("SELECT COUNT(*) FROM menu_items WHERE active = 1 AND name IN ('面粉糕', '面粉粿')").fetchone()[0] == 1
        assert db.execute('SELECT opened_at, first_order_at, paid_at FROM table_sessions').fetchone() == (created, submitted, paid)
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
