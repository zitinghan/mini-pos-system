from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import pytest
from sqlalchemy import select, func

from app.database.db import transaction
from app.models.entities import OrderItem, OrderItemModifier, OrderBatch, PrintJob, AuditLog, MenuItem
from app.printing.worker import run_once
from app.printing.tickets import ticket_lines, render
from app.services import order_edits
from test_workflows import key, open_session, draft, add, submit
from test_v11 import catalog, selections


def setup_item(client, headers, sku='WANTAN_MEE', submitted=True):
    food = catalog(client, headers)[sku]
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    line = add(client, headers, batch, food, selections(food)).json()
    if submitted:
        submit(client, headers, batch)
        line = client.get(f'/api/table-sessions/{session}/bill', headers=headers).json()['items'][0]
    return food, session, batch, line


def edit_payload(food, line, quantity=None, names=(), notes='', price=None):
    return {'menu_item_id': food['id'], 'quantity': quantity if quantity is not None else line['quantity'],
        'option_ids': selections(food, *names), 'notes': notes, 'expected_revision': line['revision'],
        'expected_unit_price': line['unit_price'] if price is None else price}


def test_table_stays_available_until_successful_first_submission(client, headers):
    opened = client.post('/api/tables/5/open', headers=headers).json()
    assert opened['status'] == 'AVAILABLE'
    session = opened['session_id']
    batch = draft(client, headers, session)
    food = catalog(client, headers)['WANTAN_MEE']
    add(client, headers, batch, food, selections(food))
    assert client.get('/api/tables/5', headers=headers).json()['status'] == 'AVAILABLE'
    with transaction() as db:
        db.get(MenuItem, food['id']).sold_out = True
    assert submit(client, headers, batch).status_code == 409
    assert client.get('/api/tables/5', headers=headers).json()['status'] == 'AVAILABLE'
    with transaction() as db:
        db.get(MenuItem, food['id']).sold_out = False
    assert submit(client, headers, batch).status_code == 200
    table = client.get('/api/tables/5', headers=headers).json()
    assert table['status'] == 'OCCUPIED' and table['first_order_at']


def test_order_notes_print_on_all_relevant_stalls_and_customer_receipt(client, headers):
    foods = catalog(client, headers)
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    for sku in ['WANTAN_MEE', 'CURRY_RICE', 'MILO']:
        add(client, headers, batch, foods[sku], selections(foods[sku]))
    request = key(headers)
    endpoint = f'/api/order-batches/{batch}/submit'
    result = client.post(endpoint, headers=request, json={'notes': '  一起上菜  '})
    assert result.status_code == 200
    assert client.post(endpoint, headers=request, json={'notes': '一起上菜'}).json() == result.json()
    assert client.post(endpoint, headers=request, json={'notes': 'Changed'}).status_code == 409
    with transaction() as db:
        jobs = list(db.scalars(select(PrintJob)))
        assert len(jobs) == 3 and all(job.ticket['notes'] == '一起上菜' for job in jobs)
        assert all('整单备注 一起上菜' in '\n'.join(text for text, _ in ticket_lines(job.ticket)) for job in jobs)
    bill = client.get(f'/api/table-sessions/{session}/bill', headers=headers).json()
    paid = client.post(f'/api/table-sessions/{session}/payments', headers=key(headers),
        json={'method': 'QR', 'received': bill['total'], 'expected_total': bill['total']}).json()
    receipt = client.get(f"/api/payments/{paid['id']}/receipt", headers=headers).json()
    assert receipt['order_notes'] == [{'batch_id': batch, 'notes': '一起上菜'}]
    assert '一起上菜' in '\n'.join(text for text, _ in ticket_lines(receipt))


def test_draft_edit_updates_quantity_options_notes_without_printing(client, headers):
    food, session, batch, line = setup_item(client, headers, submitted=False)
    payload = edit_payload(food, line, 2, ['加面', '打包'], '不要太咸', 1000)
    result = client.patch(f"/api/order-batches/{batch}/items/{line['id']}", headers=key(headers), json=payload)
    assert result.status_code == 200, result.text
    assert result.json()['line_total'] == 2000 and result.json()['revision'] == 2
    assert result.json()['notes'] == '不要太咸'
    assert client.get('/api/print-jobs', headers=headers).json() == []
    assert client.get('/api/tables/5', headers=headers).json()['status'] == 'AVAILABLE'
    assert submit(client, headers, batch).json()['total'] == 2000


def test_submitted_edit_is_atomic_audited_frozen_for_free_changes_and_printed_once(client, headers):
    food, session, batch, line = setup_item(client, headers)
    with transaction() as db:
        original = db.scalar(select(PrintJob))
        old_ticket, original_id = deepcopy(original.ticket), original.id
        db.get(MenuItem, food['id']).base_price = 1200
    payload = edit_payload(food, line, 2, ['打包'], '少盐')
    endpoint = f"/api/order-batches/{batch}/items/{line['id']}"
    request = key(headers)
    result = client.patch(endpoint, headers=request, json=payload)
    assert result.status_code == 200, result.text
    updated = result.json()
    assert updated['unit_price'] == 800 and updated['line_total'] == 1600 and updated['revision'] == 2
    assert client.patch(endpoint, headers=request, json=payload).json() == updated
    assert client.patch(endpoint, headers=request, json={**payload, 'notes': 'Other'}).status_code == 409
    with transaction() as db:
        assert db.get(PrintJob, original_id).ticket == old_ticket
        correction = db.get(PrintJob, updated['change_print_job_id'])
        assert correction.change_id and correction.routing_group == 'KITCHEN'
        assert correction.ticket['previous_items'][0]['quantity'] == 1
        assert correction.ticket['items'][0]['quantity'] == 2
        assert correction.ticket['order_type'] == 'UPDATE'
        text = '\n'.join(text for text, _ in ticket_lines(correction.ticket))
        assert '原内容（作废）' in text and '改为以下内容' in text and '少盐' in text and '打包' in text
        audit = db.get(AuditLog, correction.change_id)
        assert audit.details['before']['quantity'] == 1 and audit.details['after']['quantity'] == 2
        assert db.scalar(select(func.count()).select_from(PrintJob)) == 2
    assert client.get(f'/api/table-sessions/{session}/bill', headers=headers).json()['total'] == 1600


def test_revision_conflicts_prevent_overwriting_another_staff_edit(client, headers):
    food, _, batch, line = setup_item(client, headers)
    endpoint = f"/api/order-batches/{batch}/items/{line['id']}"
    payload = edit_payload(food, line, 2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda note: client.patch(endpoint, headers=key(headers), json={**payload, 'notes': note}), ['A', 'B']))
    assert sorted(response.status_code for response in responses) == [200, 409]
    with transaction() as db:
        assert db.get(OrderItem, line['id']).revision == 2
        assert db.scalar(select(func.count()).select_from(PrintJob)) == 2


def test_correction_waits_for_original_send_and_reprint_preserves_change_reference(client, headers):
    food, _, batch, line = setup_item(client, headers)
    with transaction() as db:
        original = db.scalar(select(PrintJob))
        original_id = original.id
        original.status = 'SENDING'
    changed = client.patch(f"/api/order-batches/{batch}/items/{line['id']}", headers=key(headers),
        json=edit_payload(food, line, 2)).json()
    assert not run_once()
    with transaction() as db:
        db.get(PrintJob, original_id).status = 'SENT'
    assert run_once()
    correction_id = changed['change_print_job_id']
    reprint = client.post(f'/api/print-jobs/{correction_id}/retry', headers=key(headers))
    assert reprint.status_code == 201
    assert reprint.json()['change_id'] == client.get(f'/api/print-jobs/{correction_id}', headers=headers).json()['change_id']
    assert run_once()


def test_edits_block_during_checkout_and_after_payment_but_lost_response_replays(client, headers):
    food, session, batch, line = setup_item(client, headers)
    endpoint = f"/api/order-batches/{batch}/items/{line['id']}"
    request = key(headers)
    payload = edit_payload(food, line, 2)
    saved = client.patch(endpoint, headers=request, json=payload).json()
    client.post(f'/api/table-sessions/{session}/checkout', headers=headers)
    assert client.patch(endpoint, headers=key(headers), json=payload).status_code == 409
    paid = client.post(f'/api/table-sessions/{session}/payments', headers=key(headers),
        json={'method': 'QR', 'received': 1600, 'expected_total': 1600})
    assert paid.status_code == 200
    assert client.patch(endpoint, headers=key(headers), json=payload).status_code == 409
    assert client.patch(endpoint, headers=request, json=payload).json() == saved


def test_failed_correction_outbox_rolls_back_item_modifiers_revision_and_audit(client, headers, monkeypatch):
    food, _, batch, line = setup_item(client, headers)
    def fail(**kwargs): raise RuntimeError('Injected correction failure')
    monkeypatch.setattr(order_edits, 'PrintJob', fail)
    with pytest.raises(RuntimeError, match='Injected correction failure'):
        client.patch(f"/api/order-batches/{batch}/items/{line['id']}", headers=key(headers),
            json=edit_payload(food, line, 2, ['打包']))
    with transaction() as db:
        assert db.get(OrderItem, line['id']).quantity == 1 and db.get(OrderItem, line['id']).revision == 1
        assert not db.scalar(select(AuditLog).where(AuditLog.action == 'EDIT_ITEM'))
        assert {entry.name for entry in db.scalars(select(OrderItemModifier).where(OrderItemModifier.item_id == line['id']))} == {entry['name'] for entry in line['modifiers']}


def test_beer_package_edit_updates_physical_bottles_and_price(client, headers):
    food, session, batch, line = setup_item(client, headers, 'CARLSBERG')
    result = client.patch(f"/api/order-batches/{batch}/items/{line['id']}", headers=key(headers),
        json=edit_payload(food, line, 2, ['3瓶', '打包'], price=6000))
    assert result.status_code == 200, result.text
    assert result.json()['physical_bottles'] == 6 and result.json()['line_total'] == 12000
    assert client.get(f'/api/table-sessions/{session}/bill', headers=headers).json()['total'] == 12000


def test_noop_does_not_print_and_stale_price_cannot_be_collected(client, headers):
    food, _, batch, line = setup_item(client, headers)
    endpoint = f"/api/order-batches/{batch}/items/{line['id']}"
    noop = client.patch(endpoint, headers=key(headers), json=edit_payload(food, line))
    assert noop.status_code == 200 and noop.json()['revision'] == 1
    with transaction() as db:
        assert db.scalar(select(func.count()).select_from(PrintJob)) == 1
        db.get(MenuItem, food['id']).base_price = 1200
    assert client.patch(endpoint, headers=key(headers), json=edit_payload(food, line, names=['加面'], price=1000)).status_code == 409


def test_other_staff_cannot_edit_private_draft_but_can_correct_a_submitted_order(client, headers):
    food, _, batch, line = setup_item(client, headers, submitted=False)
    token = client.post('/api/auth/login', json={'name': 'staff', 'pin': '654321'}).json()['token']
    staff = {'Authorization': f'Bearer {token}'}
    endpoint = f"/api/order-batches/{batch}/items/{line['id']}"
    payload = edit_payload(food, line, 2)
    assert client.patch(endpoint, headers=key(staff), json=payload).status_code == 403
    submit(client, headers, batch)
    result = client.patch(endpoint, headers=key(staff), json=payload)
    assert result.status_code == 200
    with transaction() as db:
        audit = db.scalar(select(AuditLog).where(AuditLog.action == 'EDIT_ITEM'))
        assert audit.user_id == 2


@pytest.mark.parametrize('sku', ['WANTAN_MEE', 'PLAIN_WATER'])
def test_sold_out_submitted_item_can_update_notes_but_cannot_increase_quantity(client, headers, sku):
    food, session, batch, line = setup_item(client, headers, sku)
    with transaction() as db:
        db.get(MenuItem, food['id']).sold_out = True
    endpoint = f"/api/order-batches/{batch}/items/{line['id']}"
    assert client.patch(endpoint, headers=key(headers), json=edit_payload(food, line, 2)).status_code == 409
    result = client.patch(endpoint, headers=key(headers), json=edit_payload(food, line, notes='新备注'))
    assert result.status_code == 200 and result.json()['unit_price'] == line['unit_price']
    bill = client.get(f'/api/table-sessions/{session}/bill', headers=headers).json()
    assert bill['total'] == line['unit_price']


def test_multiline_order_remarks_and_correction_notes_render_without_clipping(tmp_path):
    item = {'name': '云吞面', 'quantity': 1, 'printer_group': 'KITCHEN', 'modifiers': [], 'notes': '第一行\n第二行'}
    ticket = {'table': 'T05', 'batch_id': 1, 'time': '2026-11-07T10:00:00+00:00', 'order_type': 'UPDATE',
        'change_ref': 1, 'notes': '一起上菜\n先送饮料', 'previous_items': [item], 'items': [item]}
    multiline = render(ticket, False, 576, tmp_path / 'multiline.png')
    flat_item = {**item, 'notes': item['notes'].replace('\n', ' ')}
    flat = render({**ticket, 'notes': ticket['notes'].replace('\n', ' '), 'items': [flat_item], 'previous_items': [flat_item]}, False, 576, tmp_path / 'flat.png')
    assert multiline.width == 576 and multiline.height > flat.height
