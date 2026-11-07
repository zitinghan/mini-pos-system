from copy import deepcopy
import pytest
from sqlalchemy import select, func

from app.database.db import transaction
from app.database.seed import seed
from app.models.entities import OrderItem, OrderBatch, TableSession, PrintJob, Payment, AuditLog
from app.printing.tickets import ticket_lines
from app.printing.worker import run_once
from app.services import table_controls
from test_v11 import catalog, selections
from test_workflows import open_session, draft, add, submit, key


def placed(client, headers, skus=('WANTAN_MEE',), prepaid=False):
    foods = catalog(client, headers)
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    for sku in skus: add(client, headers, batch, foods[sku], selections(foods[sku]))
    result = client.post(f'/api/order-batches/{batch}/submit', headers=key(headers), json={'prepaid_label': prepaid})
    assert result.status_code == 200, result.text
    return session, batch, client.get(f'/api/table-sessions/{session}/bill', headers=headers).json()


@pytest.mark.parametrize('portion,egg,price', [('普通','不加蛋',800),('普通','加蛋',900),('大份','不加蛋',1000),('大份','加蛋',1100)])
def test_kueh_big_and_egg_are_independently_priced(client, headers, portion, egg, price):
    food = catalog(client, headers)['MEE_HOON_KUEH']
    batch = draft(client, headers, open_session(client, headers))
    assert add(client, headers, batch, food, selections(food, portion, egg), 2).json()['line_total'] == price * 2
    group = next(group for group in food['groups'] if group['name'] == '份量')
    legacy = [identity for identity in selections(food, egg) if identity not in [option['id'] for option in group['options']]]
    assert add(client, headers, batch, food, legacy).json()['unit_price'] == (900 if egg == '加蛋' else 800)
    seed(); seed()
    assert len([group for group in catalog(client, headers)['MEE_HOON_KUEH']['groups'] if group['name'] == '份量']) == 1


def test_cancel_item_removes_charge_preserves_snapshots_and_prints_only_affected_stall(client, headers):
    session, batch, bill = placed(client, headers, ('WANTAN_MEE', 'CURRY_RICE', 'MILO'))
    line = bill['items'][0]
    with transaction() as db: original = deepcopy(db.scalar(select(PrintJob)).ticket)
    endpoint = f"/api/order-batches/{batch}/items/{line['id']}/cancel"
    request = key(headers); payload = {'expected_revision': line['revision'], 'reason': '等候太久'}
    result = client.post(endpoint, headers=request, json=payload)
    assert result.status_code == 200 and result.json()['status'] == 'CANCELLED'
    assert result.json()['print_jobs'][0]['routing_group'] == 'KITCHEN'
    assert client.post(endpoint, headers=request, json=payload).json() == result.json()
    assert client.post(endpoint, headers=key(headers), json=payload).status_code == 409
    current = client.get(f'/api/table-sessions/{session}/bill', headers=headers).json()
    assert current['total'] == bill['total'] - line['line_total'] and len(current['items']) == 2
    with transaction() as db:
        assert db.scalar(select(PrintJob).order_by(PrintJob.id)).ticket == original
        record = db.get(OrderItem, line['id'])
        assert record.quantity == line['quantity'] and record.unit_price == line['unit_price']
        assert record.cancellation_reason == '等候太久' and record.revision == 2
        cancellation = db.get(PrintJob, result.json()['print_jobs'][0]['id'])
        text = '\n'.join(text for text, _ in ticket_lines(cancellation.ticket))
        assert '取消单' in text and '停止制作' in text and '等候太久' in text
        assert '云吞面' in text and 'Milo' not in text


def test_whole_table_cancel_covers_rounds_and_other_staff_drafts_without_payment(client, headers):
    session, batch, _ = placed(client, headers, ('WANTAN_MEE', 'CURRY_RICE', 'MILO'), prepaid=True)
    foods = catalog(client, headers)
    another = draft(client, headers, session)
    add(client, headers, another, foods['CARLSBERG'], selections(foods['CARLSBERG'], '3瓶'))
    submit(client, headers, another)
    token = client.post('/api/auth/login', json={'name':'staff','pin':'654321'}).json()['token']
    staff = {'Authorization': f'Bearer {token}'}
    unfinished = draft(client, staff, session)
    add(client, staff, unfinished, foods['PLAIN_WATER'], selections(foods['PLAIN_WATER']))
    before = client.get(f'/api/table-sessions/{session}/bill', headers=headers).json()
    request = key(headers)
    payload = {'expected_change_token': before['change_token'], 'reason': '等候太久，整桌取消'}
    endpoint = f'/api/table-sessions/{session}/cancel'
    cancelled = client.post(endpoint, headers=request, json=payload)
    assert cancelled.status_code == 200, cancelled.text
    assert len(cancelled.json()['print_jobs']) == 3
    assert client.post(endpoint, headers=request, json=payload).json() == cancelled.json()
    assert client.get('/api/tables/5', headers=headers).json()['status'] == 'AVAILABLE'
    with transaction() as db:
        table = db.get(TableSession, session)
        assert table.status == 'CANCELLED' and table.closed_at and not table.paid_at
        assert table.first_order_at == before['first_order_at']
        assert not db.scalar(select(Payment))
        assert all(item.status == 'CANCELLED' for item in db.scalars(select(OrderItem)))
        assert all(batch.status == 'CANCELLED' for batch in db.scalars(select(OrderBatch)))
        jobs = list(db.scalars(select(PrintJob).where(PrintJob.change_id.is_not(None))))
        assert len(jobs) == 3 and all(job.session_id == session for job in jobs)
        items = [item for job in jobs for item in job.ticket['items']]
        assert len(items) == len({item['id'] for item in items}) == 4
        assert not any(item['sku'] == 'PLAIN_WATER' for item in items)  # Draft was never sent to a stall.
    assert client.get('/api/reports/daily-sales', headers=headers).json()['total'] == 0
    assert open_session(client, headers) != session


def test_cancel_token_detects_free_new_items_and_failed_outbox_rolls_everything_back(client, headers, monkeypatch):
    session, batch, old = placed(client, headers)
    food = catalog(client, headers)['PLAIN_WATER']
    additional = draft(client, headers, session)
    add(client, headers, additional, food, selections(food))
    endpoint = f'/api/table-sessions/{session}/cancel'
    assert client.post(endpoint, headers=key(headers), json={'expected_change_token':old['change_token']}).status_code == 409
    current = client.get(f'/api/table-sessions/{session}/bill', headers=headers).json()
    def fail(**kwargs): raise RuntimeError('Cancel outbox failed')
    monkeypatch.setattr(table_controls, 'PrintJob', fail)
    with pytest.raises(RuntimeError, match='Cancel outbox failed'):
        client.post(endpoint, headers=key(headers), json={'expected_change_token':current['change_token']})
    assert client.get(f'/api/table-sessions/{session}/bill', headers=headers).json()['change_token'] == current['change_token']
    with transaction() as db:
        assert db.get(TableSession, session).status == 'OCCUPIED'
        assert not db.scalar(select(AuditLog).where(AuditLog.action == 'CANCEL_TABLE'))


def test_editable_remarks_send_note_not_food_and_paid_label_is_not_a_payment(client, headers):
    session, batch, before = placed(client, headers, ('WANTAN_MEE','CURRY_RICE','MILO'), prepaid=True)
    assert before['has_prepaid_label']
    with transaction() as db:
        assert not db.scalar(select(Payment))
        assert all(job.ticket['prepaid_label'] for job in db.scalars(select(PrintJob)))
    request = key(headers)
    payload = {'expected_revision':before['metadata_revision'], 'notes':'一起上菜\n先送饮料'}
    saved = client.patch(f'/api/table-sessions/{session}/notes', headers=request, json=payload)
    assert saved.status_code == 200 and len(saved.json()['print_jobs']) == 3
    assert client.patch(f'/api/table-sessions/{session}/notes', headers=request, json=payload).json() == saved.json()
    assert client.patch(f'/api/table-sessions/{session}/notes', headers=key(headers), json=payload).status_code == 409
    detail = client.patch(f'/api/order-batches/{batch}/details', headers=key(headers),
        json={'expected_revision':1,'notes':'本轮先送','prepaid_label':False})
    assert detail.status_code == 200
    with transaction() as db:
        for job in db.scalars(select(PrintJob).where(PrintJob.change_id.is_not(None))):
            assert job.ticket['order_type'] == 'NOTE' and job.ticket['items'] == []
            assert '请勿重复制作' in '\n'.join(text for text,_ in ticket_lines(job.ticket))
        assert not db.scalar(select(Payment))
    another = draft(client, headers, session)
    food = catalog(client, headers)['MILO']
    add(client, headers, another, food, selections(food)); submit(client, headers, another)
    with transaction() as db:
        assert db.get(OrderBatch, another).prepaid_label is False
        ticket = db.scalar(select(PrintJob).where(PrintJob.batch_id == another)).ticket
        assert ticket['table_notes'] == payload['notes'] and not ticket['prepaid_label']
    while run_once(): pass
    current = client.get(f'/api/table-sessions/{session}/bill', headers=headers).json()
    payment = client.post(f'/api/table-sessions/{session}/payments', headers=key(headers),
        json={'method':'QR','received':current['total'],'expected_total':current['total']}).json()
    receipt = client.get(f"/api/payments/{payment['id']}/receipt", headers=headers).json()
    assert receipt['table_notes'] == payload['notes']
    assert client.patch(f'/api/table-sessions/{session}/notes', headers=key(headers), json={'expected_revision':2,'notes':'late'}).status_code == 409
    assert client.post(f'/api/table-sessions/{session}/cancel', headers=key(headers), json={'expected_change_token':current['change_token']}).status_code == 409


def test_cancel_draft_has_no_print_and_staff_cannot_cancel_someone_elses_draft(client, headers):
    food = catalog(client, headers)['WANTAN_MEE']
    session = open_session(client, headers); batch = draft(client, headers, session)
    line = add(client, headers, batch, food, selections(food)).json()
    token = client.post('/api/auth/login', json={'name':'staff','pin':'654321'}).json()['token']
    endpoint = f"/api/order-batches/{batch}/items/{line['id']}/cancel"
    assert client.post(endpoint, headers=key({'Authorization':f'Bearer {token}'}), json={'expected_revision':1}).status_code == 403
    result = client.post(endpoint, headers=key(headers), json={'expected_revision':1})
    assert result.status_code == 200 and result.json()['print_jobs'] == []
    assert client.get('/api/print-jobs', headers=headers).json() == []
