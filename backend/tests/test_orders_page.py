from app.database.db import transaction
from app.models.entities import PrintJob, RestaurantTable
from app.printing.worker import run_once
from test_receipts import submitted
from test_workflows import key


def test_orders_completion_follows_paid_session_and_keeps_table_snapshot(client, headers):
    session, total = submitted(client, headers)
    assert run_once()
    active = client.get('/api/print-jobs?completed=false', headers=headers).json()
    original = active[0]
    assert original['table'] == 'T05' and original['session_id'] == session
    assert original['session_status'] == 'OCCUPIED' and original['completed'] is False
    assert original['status'] == 'SENT'  # Sending a ticket does not complete an order.
    assert client.get('/api/print-jobs?completed=true', headers=headers).json() == []

    payment = client.post(f'/api/table-sessions/{session}/payments', headers=key(headers),
        json={'method': 'QR', 'received': total, 'expected_total': total, 'print_receipt': True})
    assert payment.status_code == 200
    assert client.get('/api/print-jobs?completed=false', headers=headers).json() == []
    completed = client.get('/api/print-jobs?completed=true', headers=headers).json()
    assert len(completed) == 2 and all(job['completed'] and job['session_status'] == 'PAID' for job in completed)
    assert all(job['table'] == 'T05' for job in completed)

    new_session, _ = submitted(client, headers)
    with transaction() as db:
        db.get(RestaurantTable, 5).name = 'NEW TABLE NAME'
    active = client.get('/api/print-jobs?completed=false', headers=headers).json()
    assert len(active) == 1 and active[0]['session_id'] == new_session != session
    assert active[0]['table'] == 'T05'
    completed = client.get('/api/print-jobs?completed=true', headers=headers).json()
    assert all(job['session_id'] == session for job in completed)
    token = client.post('/api/auth/login', json={'name': 'staff', 'pin': '654321'}).json()['token']
    staff_completed = client.get('/api/print-jobs?completed=true', headers={'Authorization': f'Bearer {token}'}).json()
    assert len(staff_completed) == 1 and staff_completed[0]['payment_id'] is None


def test_active_orders_are_not_buried_by_recent_completed_print_records(client, headers):
    session, _ = submitted(client, headers)
    with transaction() as db:
        for _ in range(105):
            db.add(PrintJob(status='SENT', ticket={'table': 'TEST'}))
    assert len(client.get('/api/print-jobs?completed=true', headers=headers).json()) == 100
    active = client.get('/api/print-jobs?completed=false', headers=headers).json()
    assert len(active) == 1 and active[0]['session_id'] == session


def test_failed_and_uncertain_test_prints_remain_visible(client, headers):
    with transaction() as db:
        for status in ['PENDING', 'FAILED', 'UNKNOWN', 'SENT']:
            db.add(PrintJob(status=status, ticket={'table': 'TEST'}))
    active = client.get('/api/print-jobs?completed=false', headers=headers).json()
    assert {job['status'] for job in active} == {'PENDING', 'FAILED', 'UNKNOWN'}
    assert all(job['table'] == 'TEST' and job['session_status'] is None for job in active)
    completed = client.get('/api/print-jobs?completed=true', headers=headers).json()
    assert len(completed) == 1 and completed[0]['status'] == 'SENT'
