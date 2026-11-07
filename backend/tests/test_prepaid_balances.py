from copy import deepcopy
import pytest
from sqlalchemy import select, func
from app.database.db import transaction
from app.models.entities import OrderBatch, Payment, PrintJob
from app.printing.tickets import receipt_lines
from test_v11 import catalog
from test_workflows import open_session, draft, add, key


def placed(client, headers, amount=500, method='QR', table=5):
    session = open_session(client, headers, table)
    batch = draft(client, headers, session)
    item = add(client, headers, batch, catalog(client, headers)['WANTAN_MEE']).json()
    body = {'prepaid_label': True, 'prepaid_method': method}
    if amount is not None: body['prepaid_amount'] = amount
    response = client.post(f'/api/order-batches/{batch}/submit', headers=key(headers), json=body)
    assert response.status_code == 200, response.text
    return session, batch, item


def bill(client, headers, session):
    return client.get(f'/api/table-sessions/{session}/bill', headers=headers).json()


def pay(client, headers, session, **extra):
    current = bill(client, headers, session)
    body = {'expected_total': current['total'], 'expected_prepaid_total': current['prepaid_total'],
        'expected_prepaid_token': current['prepaid_token'], **extra}
    return client.post(f'/api/table-sessions/{session}/payments', headers=key(headers), json=body)


@pytest.mark.parametrize('method', ['CASH', 'QR', 'OTHER'])
def test_full_prepaid_needs_no_method_collects_nothing_and_finalizes_once(client, headers, method):
    session, batch, _ = placed(client, headers, None, method)
    current = bill(client, headers, session)
    assert current['prepaid_total'] == 800 and current['remaining_amount'] == 0
    assert client.get('/api/tables/5', headers=headers).json()['prepaid_label_status'] == 'ALL'
    with transaction() as db:
        assert db.scalar(select(func.count()).select_from(Payment)) == 0
    request = key(headers)
    body = {'expected_total': 800, 'expected_prepaid_total': 800, 'expected_prepaid_token': current['prepaid_token']}
    response = client.post(f'/api/table-sessions/{session}/payments', headers=request, json=body)
    assert response.status_code == 200, response.text
    payment = response.json()
    assert payment['total'] == payment['received'] == 800 and payment['change'] == 0
    assert payment['method'] == method and payment['settlement']['additional_collected'] == 0
    assert client.post(f'/api/table-sessions/{session}/payments', headers=request, json=body).json() == payment
    report = client.get('/api/reports/daily-sales', headers=headers).json()
    assert report['total'] == report['methods'][method] == 800 and report['completed_sessions'] == 1
    with transaction() as db:
        assert db.scalar(select(func.count()).select_from(Payment)) == 1
        assert db.scalar(select(func.count()).select_from(PrintJob)) == 1
    receipt = client.get(f"/api/payments/{payment['id']}/receipt", headers=headers).json()
    assert receipt['settlement']['prepaid_total'] == 800
    assert '此前已付 RM 8.00' in '\n'.join(text for text, _ in receipt_lines(receipt))


@pytest.mark.parametrize('method,received,change', [('CASH', 500, 200), ('QR', 300, 0), ('OTHER', 300, 0)])
def test_partial_payment_collects_only_balance_and_allocates_daily_methods(client, headers, method, received, change):
    session, _, _ = placed(client, headers)
    current = bill(client, headers, session)
    assert current['remaining_amount'] == 300
    assert client.get('/api/tables/5', headers=headers).json()['prepaid_label_status'] == 'PARTIAL'
    result = pay(client, headers, session, method=method, received=received)
    assert result.status_code == 200, result.text
    payment = result.json()
    assert payment['received'] == 800 + change and payment['change'] == change
    expected = {'QR': 800} if method == 'QR' else {'QR': 500, method: 300}
    assert payment['settlement']['allocations'] == expected
    report = client.get('/api/reports/daily-sales', headers=headers).json()
    assert report['total'] == sum(report['methods'].values()) == 800
    assert all(report['methods'][method] == amount for method, amount in expected.items())


def test_frozen_amount_survives_edits_addons_and_item_cancellation(client, headers):
    session, batch, item = placed(client, headers, 800)
    with transaction() as db:
        original = deepcopy(db.scalar(select(PrintJob)).ticket)
    updated = client.patch(f"/api/order-batches/{batch}/items/{item['id']}", headers=key(headers), json={
        'menu_item_id': item['menu_item_id'], 'quantity': 2, 'option_ids': [mod['option_id'] for mod in item['modifiers']],
        'expected_revision': 1, 'expected_unit_price': 800})
    assert updated.status_code == 200, updated.text
    assert bill(client, headers, session)['remaining_amount'] == 800
    extra = draft(client, headers, session)
    add(client, headers, extra, catalog(client, headers)['MILO'])
    client.post(f'/api/order-batches/{extra}/submit', headers=key(headers))
    assert bill(client, headers, session)['remaining_amount'] == 1100
    cancelled = client.post(f"/api/order-batches/{batch}/items/{item['id']}/cancel", headers=key(headers),
        json={'expected_revision': 2, 'reason': '等太久'})
    assert cancelled.status_code == 200, cancelled.text
    current = bill(client, headers, session)
    assert current['prepaid_total'] == 800 and current['overpaid_amount'] == 500
    assert pay(client, headers, session).status_code == 422
    with transaction() as db:
        assert db.get(OrderBatch, batch).prepaid_amount == 800
        assert db.scalar(select(PrintJob).order_by(PrintJob.id)).ticket == original


def test_adjustable_amount_offer_and_stale_payment_protection(client, headers):
    session, batch, _ = placed(client, headers)
    old = bill(client, headers, session)
    endpoint = f'/api/order-batches/{batch}/details'
    body = {'expected_revision': 1, 'notes': '', 'prepaid_label': True, 'prepaid_method': 'CASH', 'prepaid_amount': 600}
    request = key(headers)
    updated = client.patch(endpoint, headers=request, json=body)
    assert updated.status_code == 200
    assert client.patch(endpoint, headers=request, json=body).json() == updated.json()
    stale = {'expected_total': 800, 'expected_prepaid_total': 500, 'expected_prepaid_token': old['prepaid_token'], 'method': 'QR', 'received': 300}
    assert client.post(f'/api/table-sessions/{session}/payments', headers=key(headers), json=stale).status_code == 409
    assert client.post(f'/api/table-sessions/{session}/payments', headers=key(headers), json={'expected_total': 800, 'method': 'QR', 'received': 800}).status_code == 409
    assert pay(client, headers, session, final_total=500).status_code == 422
    result = pay(client, headers, session, final_total=600, offer_reason='优惠')
    assert result.status_code == 200, result.text
    assert result.json()['total'] == 600 and result.json()['settlement']['allocations'] == {'CASH': 600}


def test_cash_underpayment_full_double_collection_and_stale_method_are_rejected(client, headers):
    session, batch, _ = placed(client, headers)
    assert pay(client, headers, session, method='CASH', received=299).status_code == 422
    assert pay(client, headers, session).status_code == 422
    old = bill(client, headers, session)
    client.patch(f'/api/order-batches/{batch}/details', headers=key(headers), json={
        'expected_revision': 1, 'notes': '', 'prepaid_label': True, 'prepaid_method': 'CASH', 'prepaid_amount': 800})
    assert pay(client, headers, session, method='QR', received=800).status_code == 422
    client.post(f'/api/table-sessions/{session}/checkout', headers=headers)
    assert client.post(f'/api/table-sessions/{session}/customer-display', headers=headers,
        json={'expected_total': 800, 'final_total': 0, 'expected_prepaid_token': old['prepaid_token']}).status_code == 409
    assert pay(client, headers, session).status_code == 200


def test_legacy_null_amount_is_explicitly_estimated_until_staff_confirms(client, headers):
    session, batch, _ = placed(client, headers)
    with transaction() as db: db.get(OrderBatch, batch).prepaid_amount = None
    current = bill(client, headers, session)
    assert current['prepaid_rounds'][0]['amount_estimated'] and current['prepaid_total'] == 800
    result = client.patch(f'/api/order-batches/{batch}/details', headers=key(headers), json={
        'expected_revision': 1, 'notes': '核实已收', 'prepaid_label': True, 'prepaid_amount': 500})
    assert result.status_code == 200
    assert bill(client, headers, session)['prepaid_total'] == 500
    assert not bill(client, headers, session)['prepaid_rounds'][0]['amount_estimated']


def test_multiple_prepaid_rounds_and_remaining_cash_preserve_every_method(client, headers):
    session, _, _ = placed(client, headers, 500, 'QR')
    extra = draft(client, headers, session)
    add(client, headers, extra, catalog(client, headers)['MILO'])
    client.post(f'/api/order-batches/{extra}/submit', headers=key(headers), json={
        'prepaid_label': True, 'prepaid_method': 'OTHER', 'prepaid_amount': 200})
    current = bill(client, headers, session)
    assert current['prepaid_total'] == 700 and current['remaining_amount'] == 400
    result = pay(client, headers, session, method='CASH', received=500).json()
    assert result['settlement']['allocations'] == {'QR': 500, 'OTHER': 200, 'CASH': 400}
    assert result['change'] == 100 and result['total'] == 1100


def test_customer_display_shows_only_remaining_balance_and_new_cash_change(client, headers, monkeypatch):
    from unittest.mock import Mock
    from app.services import customer_display
    session, _, _ = placed(client, headers)
    send = Mock(return_value={'status':'sent'})
    monkeypatch.setattr(customer_display, 'show_amount', send)
    checkout = client.post(f'/api/table-sessions/{session}/checkout', headers=headers).json()
    send.assert_called_once_with(300)
    send.reset_mock()
    response = client.post(f'/api/table-sessions/{session}/customer-display', headers=headers, json={
        'expected_total':800,'final_total':100,'expected_prepaid_token':checkout['prepaid_token']})
    assert response.status_code == 200
    send.assert_called_once_with(100)
    send.reset_mock()
    response = pay(client, headers, session, final_total=600, method='CASH', received=200)
    assert response.status_code == 200 and response.json()['method'] == 'OTHER'
    send.assert_called_once_with(100)


def test_explicit_null_paid_amount_defaults_to_full_and_submit_retry_is_safe(client, headers):
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    add(client, headers, batch, catalog(client, headers)['WANTAN_MEE'])
    body = {'prepaid_label': True, 'prepaid_method': 'QR', 'prepaid_amount': None}
    endpoint = f'/api/order-batches/{batch}/submit'
    request = key(headers)
    original = client.post(endpoint, headers=request, json=body)
    assert original.status_code == 200
    assert client.post(endpoint, headers=request, json=body).json() == original.json()
    assert client.post(endpoint, headers=request, json={**body,'prepaid_amount':500}).status_code == 409
    assert bill(client, headers, session)['prepaid_total'] == 800
