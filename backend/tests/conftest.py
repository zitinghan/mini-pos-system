import os
from pathlib import Path
import tempfile

ROOT = Path(tempfile.mkdtemp(prefix='keke-tests-'))
os.environ['DATABASE_URL'] = f'sqlite:///{ROOT}/pos.db'
os.environ['PRINT_OUTPUT_DIR'] = str(ROOT / 'tickets')
os.environ['SETUP_TOKEN'] = 'test-only-setup-token-not-a-pin'
# Discover local CJK fonts for development tests; container has a fixed Noto path.
for candidate in ['/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf', str(Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/msyh.ttc')]:
    if Path(candidate).exists():
        os.environ['FONT_PATH'] = candidate
        break

import pytest
from fastapi.testclient import TestClient
from app.database.db import Base, engine, transaction
from app.database.seed import seed
from app.main import app
from app.models.entities import User
from app.core.security import hash_pin

@pytest.fixture(autouse=True)
def database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    seed()
    with transaction() as db:
        db.add(User(name='cashier', pin_hash=hash_pin('123456'), role='ADMIN'))
        db.add(User(name='staff', pin_hash=hash_pin('654321'), role='STAFF'))
    yield

@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client

@pytest.fixture
def headers(client):
    token = client.post('/api/auth/login', json={'name': 'cashier', 'pin': '123456'}).json()['token']
    return {'Authorization': f'Bearer {token}'}
