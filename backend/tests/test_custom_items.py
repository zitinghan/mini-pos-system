from copy import deepcopy
import pytest
from sqlalchemy import select, func
from app.database.db import transaction
from app.database.seed import seed, CUSTOM_ITEM_SKU
from app.models.entities import MenuItem, PrintJob, OrderItem, Payment, AuditLog
from app.printing.tickets import ticket_lines
from test_v11 import catalog
from test_workflows import open_session, draft, add, submit, key

def custom(**changes):
    return {'name': '特别餐点', 'unit_price': 875, 'quantity': 2, 'category_code': 'SNACKS',
        'printer_group': 'KITCHEN', 'takeaway': True, 'notes': '现做，少盐', **changes}

def add_custom(client, headers, batch, **changes):
    return client.post(f'/api/order-batches/{batch}/custom-items', headers=key(headers), json=custom(**changes))


@pytest.mark.parametrize('station', ['KITCHEN', 'RICE', 'BEVERAGE'])
def test_staff_custom_items_keep_manual_prices_and_share_existing_stall_workflow(client, headers, station):
    token = client.post('/api/auth/login', json={'name': 'staff', 'pin': '654321'}).json()['token']
    staff = {'Authorization': f'Bearer {token}'}
    session = open_session(client, staff)
    batch = draft(client, staff, session)
    request = key(staff)
    body = custom(printer_group=station)
    endpoint = f'/api/order-batches/{batch}/custom-items'
    result = client.post(endpoint, headers=request, json=body)
    assert result.status_code == 201, result.text
    item = result.json()
    assert item['is_custom'] and item['line_total'] == 1750 and item['description'] == '打包'
    assert client.post(endpoint, headers=request, json=body).json() == item
    assert client.post(endpoint, headers=request, json={**body, 'unit_price': 900}).status_code == 409
    assert len(catalog(client, staff)) == 34 and CUSTOM_ITEM_SKU not in catalog(client, staff)
    assert add(client, staff, batch, catalog(client, staff)['WANTAN_MEE']).status_code == 201
    response = submit(client, staff, batch)
    assert response.json()['total'] == 2550
    with transaction() as db:
        tickets = list(db.scalars(select(PrintJob).where(PrintJob.batch_id == batch)))
        selected = [entry for job in tickets for entry in job.ticket['items'] if entry['is_custom']]
        assert len(selected) == 1 and selected[0]['printer_group'] == station
        text = '\n'.join(line for job in tickets for line, _ in ticket_lines(job.ticket))
        assert '特别餐点' in text and '打包' in text and '现做，少盐' in text
        original = deepcopy([job.ticket for job in tickets])
    seed(); seed()
    assert client.get(f'/api/table-sessions/{session}/bill', headers=headers).json()['total'] == 2550
    paid = client.post(f'/api/table-sessions/{session}/payments', headers=key(headers),
        json={'method': 'QR', 'expected_total': 2550, 'received': 2500, 'final_total': 2500})
    assert paid.status_code == 200
    receipt = client.get(f"/api/payments/{paid.json()['id']}/receipt", headers=headers).json()
    assert receipt['print_job'] is None and receipt['total'] == 2500
    saved = next(line for line in receipt['items'] if line['is_custom'])
    assert saved['name'] == body['name'] and saved['unit_price'] == 875 and saved['line_total'] == 1750
    report = client.get('/api/reports/daily-sales', headers=headers).json()
    assert sum(report['category_sales'].values()) == report['total'] == 2500
    with transaction() as db:
        assert [job.ticket for job in db.scalars(select(PrintJob).where(PrintJob.batch_id == batch))] == original
        assert db.scalar(select(func.count()).select_from(MenuItem).where(MenuItem.sku == CUSTOM_ITEM_SKU)) == 1


def test_custom_edits_corrections_cancellations_and_stale_revisions_preserve_history(client, headers):
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    item = add_custom(client, headers, batch).json()
    endpoint = f"/api/order-batches/{batch}/custom-items/{item['id']}"
    draft_edit = client.patch(endpoint, headers=key(headers), json={**custom(unit_price=900), 'expected_revision': 1})
    assert draft_edit.status_code == 200 and draft_edit.json()['line_total'] == 1800
    submit(client, headers, batch)
    with transaction() as db: original = deepcopy(db.scalar(select(PrintJob)).ticket)
    body = {**custom(name='特别餐点（改）', unit_price=950, quantity=3, takeaway=False), 'expected_revision': 2}
    request = key(headers)
    changed = client.patch(endpoint, headers=request, json=body)
    assert changed.status_code == 200 and changed.json()['line_total'] == 2850
    assert client.patch(endpoint, headers=request, json=body).json() == changed.json()
    assert client.patch(endpoint, headers=key(headers), json=body).status_code == 409
    assert client.patch(endpoint, headers=key(headers), json={**body, 'expected_revision': 3, 'printer_group':'RICE'}).status_code == 422
    with transaction() as db:
        assert db.scalar(select(PrintJob)).ticket == original
        correction = db.get(PrintJob, changed.json()['change_print_job_id'])
        text = '\n'.join(line for line, _ in ticket_lines(correction.ticket))
        assert '原内容（作废）' in text and '打包' in text and '堂食' in text and '特别餐点（改）' in text
    cancelled = client.post(f"/api/order-batches/{batch}/items/{item['id']}/cancel", headers=key(headers),
        json={'expected_revision':3,'reason':'等候太久'})
    assert cancelled.status_code == 200
    assert client.get(f'/api/table-sessions/{session}/bill', headers=headers).json()['total'] == 0
    assert client.patch(endpoint, headers=key(headers), json={**body,'expected_revision':4}).status_code == 409
    with transaction() as db:
        assert db.get(OrderItem,item['id']).unit_price == 950
        assert db.get(OrderItem,item['id']).cancellation_reason == '等候太久'


def test_custom_validation_ownership_checkout_and_paid_lock(client, headers):
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    for invalid in [{'name':'  '},{'name':'bad\x1bname'},{'unit_price':-1},{'unit_price':1.2},{'quantity':0},
                    {'printer_group':'UNKNOWN'},{'category_code':'UNKNOWN'},{'category_code':'BEER'},{'bottles_per_unit':1}]:
        assert add_custom(client, headers, batch, **invalid).status_code == 422
    token = client.post('/api/auth/login',json={'name':'staff','pin':'654321'}).json()['token']
    staff = {'Authorization':f'Bearer {token}'}
    assert add_custom(client, staff, batch).status_code == 403
    item = add_custom(client, headers, batch).json()
    assert client.post(f'/api/table-sessions/{session}/checkout',headers=headers).status_code == 200
    assert add_custom(client, headers, batch).status_code == 409
    client.post(f'/api/table-sessions/{session}/resume',headers=headers)
    submit(client, headers, batch)
    normal = client.patch(f"/api/order-batches/{batch}/items/{item['id']}",headers=key(headers),json={
        'menu_item_id':item['menu_item_id'],'quantity':1,'option_ids':[],'expected_revision':1,'expected_unit_price':875})
    assert normal.status_code == 422
    assert client.post(f'/api/table-sessions/{session}/payments',headers=key(headers),
        json={'method':'QR','expected_total':1750,'received':1750}).status_code == 200
    assert client.patch(f"/api/order-batches/{batch}/custom-items/{item['id']}",headers=key(headers),
        json={**custom(),'expected_revision':1}).status_code == 409


def test_free_custom_item_and_custom_beer_bottle_quantities(client, headers):
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    free = add_custom(client, headers, batch, unit_price=0).json()
    assert free['line_total'] == 0
    beer = add_custom(client, headers, batch, name='其他啤酒三瓶装', unit_price=5000, category_code='BEER',
        printer_group='BEVERAGE', bottles_per_unit=3).json()
    assert beer['physical_bottles'] == 6 and beer['line_total'] == 10000
    assert submit(client,headers,batch).json()['total'] == 10000
