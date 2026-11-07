from copy import deepcopy
import pytest
from sqlalchemy import select, func
from app.database.db import transaction
from app.models.entities import Payment, PrintJob, AuditLog, MenuItem
from app.printing.tickets import receipt_lines
from test_v11 import catalog
from test_workflows import open_session, draft, add, submit, key


def mixed_order(client, headers):
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    foods = catalog(client, headers)
    for sku in ['WANTAN_MEE', 'WANTAN_SOUP', 'MILO', 'CARLSBERG']:
        assert add(client, headers, batch, foods[sku]).status_code == 201
    assert submit(client, headers, batch).json()['total'] == 4100
    return session


@pytest.mark.parametrize('method', ['QR', 'CASH', 'OTHER'])
def test_offer_records_actual_payment_without_changing_food_and_reconciles_reports(client, headers, method):
    session = mixed_order(client, headers)
    endpoint = f'/api/table-sessions/{session}/payments'
    before = client.get(f'/api/table-sessions/{session}/bill', headers=headers).json()['items']
    request = key(headers)
    body = {'method': method, 'received': 5000 if method == 'CASH' else 3999,
        'expected_total': 4100, 'final_total': 3999, 'offer_reason': '熟客优惠'}
    response = client.post(endpoint, headers=request, json=body)
    assert response.status_code == 200, response.text
    payment = response.json()
    assert payment['total'] == 3999 and payment['original_total'] == 4100
    assert payment['received'] == (5000 if method == 'CASH' else 3999)
    assert payment['change'] == (1001 if method == 'CASH' else 0)
    assert payment['offer_reason'] == '熟客优惠'
    assert client.post(endpoint, headers=request, json=body).json() == payment
    assert client.post(endpoint, headers=request, json={**body, 'final_total': 3900}).status_code == 409
    assert client.get(f'/api/table-sessions/{session}/bill', headers=headers).json()['items'] == before
    receipt = client.get(f"/api/payments/{payment['id']}/receipt", headers=headers).json()
    assert receipt['total'] == 3999 and receipt['original_total'] == 4100
    assert receipt['items'] == before
    text = '\n'.join(line for line, _ in receipt_lines(receipt))
    assert '原价 RM 41.00' in text and '优惠 -RM 1.01' in text and '合计 RM 39.99' in text
    assert '熟客优惠' in text
    report = client.get('/api/reports/daily-sales', headers=headers).json()
    assert report['total'] == report['methods'][method] == 3999
    assert report['original_sales'] == 4100 and report['discounts'] == 101
    assert report['category_sales'] == {'MAINS': 780, 'SNACKS': 780, 'DRINKS': 293, 'BEER': 2146}
    assert sum(report['category_sales'].values()) == report['total']
    assert report['beer_bottles'] == report['beer_units'] == 1
    with transaction() as db:
        job = db.scalar(select(PrintJob).where(PrintJob.payment_id == payment['id']))
        snapshot = deepcopy(job.ticket)
        assert snapshot['original_total'] == 4100 and snapshot['total'] == 3999
        assert db.scalar(select(func.count()).select_from(Payment)) == 1
        audit = db.scalar(select(AuditLog).where(AuditLog.action == 'PAYMENT'))
        assert audit.details['discount'] == 101
        db.get(MenuItem, before[0]['menu_item_id']).base_price = 2000
    assert client.get(f"/api/payments/{payment['id']}/receipt", headers=headers).json()['items'] == before
    with transaction() as db:
        assert db.scalar(select(PrintJob).where(PrintJob.payment_id == payment['id'])).ticket == snapshot


def test_invalid_offers_staff_and_stale_bill_cannot_create_a_payment(client, headers):
    session = mixed_order(client, headers)
    endpoint = f'/api/table-sessions/{session}/payments'
    base = {'method': 'QR', 'received': 4000, 'expected_total': 4100}
    for invalid in [-1, 4101, 10000001, 1.5]:
        assert client.post(endpoint, headers=key(headers), json={**base, 'final_total': invalid}).status_code == 422
    token = client.post('/api/auth/login', json={'name': 'staff', 'pin': '654321'}).json()['token']
    assert client.post(endpoint, headers=key({'Authorization': f'Bearer {token}'}),
        json={**base, 'final_total': 4000}).status_code == 403
    assert client.post(endpoint, headers=key(headers), json={**base, 'expected_total': 4000, 'final_total': 3900}).status_code == 409
    assert client.post(endpoint, headers=key(headers), json={**base, 'method': 'CASH', 'received': 3800, 'final_total': 3900}).status_code == 422
    with transaction() as db:
        assert db.scalar(select(func.count()).select_from(Payment)) == 0


def test_full_discount_preserves_original_sales_and_zeroes_all_paid_categories(client, headers):
    session = mixed_order(client, headers)
    response = client.post(f'/api/table-sessions/{session}/payments', headers=key(headers),
        json={'method': 'QR', 'received': 0, 'expected_total': 4100, 'final_total': 0})
    assert response.status_code == 200 and response.json()['total'] == 0
    report = client.get('/api/reports/daily-sales', headers=headers).json()
    assert report['total'] == 0 and report['discounts'] == report['original_sales'] == 4100
    assert all(amount == 0 for amount in report['category_sales'].values())
    assert report['completed_sessions'] == 1
