import pytest
from sqlalchemy import select
from app.database.db import transaction
from app.models.entities import Payment, PrintJob, User
from test_workflows import open_session, draft, add, submit, key, menu


@pytest.mark.parametrize('method', ['CASH', 'QR'])
def test_staff_can_checkout_pay_and_print_own_receipt(client, headers, method):
    token = client.post('/api/auth/login', json={'name': 'staff', 'pin': '654321'}).json()['token']
    staff = {'Authorization': 'Bearer ' + token}
    session = open_session(client, staff)
    batch = draft(client, staff, session)
    assert add(client, staff, batch, menu(client, staff)[0]).status_code == 201
    assert submit(client, staff, batch).status_code == 200
    checkout = client.post(f'/api/table-sessions/{session}/checkout', headers=staff)
    assert checkout.status_code == 200
    total = checkout.json()['total']
    assert client.post(f'/api/table-sessions/{session}/resume', headers=staff).status_code == 200
    assert client.post(f'/api/table-sessions/{session}/checkout', headers=staff).status_code == 200
    assert client.post(f'/api/table-sessions/{session}/customer-display', headers=staff,
        json={'expected_total': total, 'final_total': total}).status_code == 200
    payment_headers = key(staff)
    data = {'method': method, 'received': total + 500 if method == 'CASH' else total, 'expected_total': total}
    result = client.post(f'/api/table-sessions/{session}/payments', headers=payment_headers, json=data)
    assert result.status_code == 200, result.text
    payment = result.json()
    assert payment['change'] == (500 if method == 'CASH' else 0)
    assert client.post(f'/api/table-sessions/{session}/payments', headers=payment_headers, json=data).json()['id'] == payment['id']
    receipt_url = f"/api/payments/{payment['id']}/receipt"
    receipt = client.get(receipt_url, headers=staff)
    assert receipt.status_code == 200 and receipt.json()['cashier'] == 'staff'
    printed = client.post(receipt_url + '/print', headers=key(staff))
    assert printed.status_code == 201
    job = printed.json()['id']
    assert client.get(f'/api/print-jobs/{job}', headers=staff).status_code == 200
    with transaction() as db:
        db.get(PrintJob, job).status = 'SENT'
        stored = db.get(Payment, payment['id'])
        assert stored.user_id == db.scalar(select(User.id).where(User.name == 'staff'))
    assert client.post(f'/api/print-jobs/{job}/retry', headers=key(staff)).status_code == 201
    for endpoint in ['/api/users', '/api/printers/config', '/api/reports/transactions']:
        assert client.get(endpoint, headers=staff).status_code == 403
    assert client.post(f'/api/table-sessions/{session}/checkout').status_code == 401
