from sqlalchemy import select, func
from app.database.db import transaction
from app.models.entities import TableSession, AuditLog, Payment, PrintJob
from app.services import orders, table_attention
from test_v11 import catalog
from test_workflows import open_session, draft, add, submit, key


def test_wait_alert_starts_after_first_order_and_strictly_after_45_minutes(client, headers, monkeypatch):
    monkeypatch.setattr(orders, 'now', lambda: '2026-11-07T04:00:00+00:00')
    clock = ['2026-11-07T04:45:00+00:00']
    monkeypatch.setattr(table_attention, 'now', lambda: clock[0])
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    food = catalog(client, headers)['WANTAN_MEE']
    add(client, headers, batch, food)
    assert not client.get('/api/tables/5', headers=headers).json()['wait_alert_due']
    submit(client, headers, batch)
    assert not client.get('/api/tables/5', headers=headers).json()['wait_alert_due']
    endpoint = f'/api/table-sessions/{session}/acknowledge-wait'
    assert client.post(endpoint, headers=headers).status_code == 409
    clock[0] = '2026-11-07T04:45:01+00:00'
    assert client.get('/api/tables/5', headers=headers).json()['wait_alert_due']
    batch = draft(client, headers, session)
    add(client, headers, batch, food)
    monkeypatch.setattr(orders, 'now', lambda: '2026-11-07T04:45:01+00:00')
    submit(client, headers, batch)
    with transaction() as db:
        assert db.get(TableSession, session).first_order_at == '2026-11-07T04:00:00+00:00'
    assert client.get('/api/tables/5', headers=headers).json()['wait_alert_due']


def test_acknowledgement_is_shared_idempotent_and_resets_for_the_next_session(client, headers, monkeypatch):
    monkeypatch.setattr(orders, 'now', lambda: '2026-11-07T04:00:00+00:00')
    monkeypatch.setattr(table_attention, 'now', lambda: '2026-11-07T04:46:00+00:00')
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    add(client, headers, batch, catalog(client, headers)['WANTAN_MEE'])
    submit(client, headers, batch)
    before = client.get(f'/api/table-sessions/{session}/bill', headers=headers).json()
    staff_token = client.post('/api/auth/login', json={'name': 'staff', 'pin': '654321'}).json()['token']
    staff = {'Authorization': f'Bearer {staff_token}'}
    endpoint = f'/api/table-sessions/{session}/acknowledge-wait'
    assert client.post(endpoint).status_code == 401
    first = client.post(endpoint, headers=staff)
    assert first.status_code == 200
    assert client.post(endpoint, headers=headers).json() == first.json()
    table = client.get('/api/tables/5', headers=headers).json()
    assert table['wait_alert_due'] and table['wait_alert_acknowledged_at'] == first.json()['wait_alert_acknowledged_at']
    assert table['status'] == 'OCCUPIED'
    assert client.get(f'/api/table-sessions/{session}/bill', headers=headers).json() == before
    with transaction() as db:
        assert db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == 'ACKNOWLEDGE_TABLE_WAIT')) == 1
        assert db.scalar(select(func.count()).select_from(Payment)) == 0
        assert db.scalar(select(func.count()).select_from(PrintJob)) == 1
    assert client.post(f'/api/table-sessions/{session}/payments', headers=key(headers),
        json={'method': 'QR', 'received': 800, 'expected_total': 800}).status_code == 200
    assert client.post(endpoint, headers=staff).status_code == 409
    table = client.get('/api/tables/5', headers=headers).json()
    assert table['status'] == 'AVAILABLE' and not table['wait_alert_due'] and table['wait_alert_acknowledged_at'] is None
    fresh = open_session(client, headers)
    assert fresh != session
    table = client.get('/api/tables/5', headers=headers).json()
    assert not table['wait_alert_due'] and table['wait_alert_acknowledged_at'] is None
    with transaction() as db:
        assert db.get(TableSession, session).wait_alert_acknowledged_at is not None


def test_invalid_missing_future_and_closed_session_times_do_not_raise_alerts(client, headers, monkeypatch):
    monkeypatch.setattr(table_attention, 'now', lambda: '2026-11-07T04:46:00+00:00')
    session = open_session(client, headers)
    for value in [None, 'invalid', '2026-11-07T04:00:00', '2026-11-08T04:00:00+00:00']:
        with transaction() as db:
            db.get(TableSession, session).first_order_at = value
        assert not client.get('/api/tables/5', headers=headers).json()['wait_alert_due']
    with transaction() as db:
        record = db.get(TableSession, session)
        record.first_order_at = '2026-11-07T04:00:00+00:00'
        record.status = 'PAYMENT_PENDING'
    assert client.get('/api/tables/5', headers=headers).json()['wait_alert_due']
    assert client.post(f'/api/table-sessions/{session}/acknowledge-wait', headers=headers).status_code == 200
    with transaction() as db:
        db.get(TableSession, session).status = 'CANCELLED'
    assert not client.get('/api/tables/5', headers=headers).json()['wait_alert_due']
