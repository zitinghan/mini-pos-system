from copy import deepcopy
from sqlalchemy import select
from app.database.db import transaction
from app.database.seed import seed
from app.models.entities import MenuItem, ModifierOption, PrintJob
from app.printing.tickets import ticket_lines
from test_v11 import catalog, selections
from test_workflows import open_session, draft, add, submit, key


def test_existing_wantan_receives_soup_once_without_resetting_menu_or_history(client, headers):
    food = catalog(client, headers)['WANTAN_MEE']
    sauce = next(group for group in food['groups'] if group['name'] == '酱汁')
    batch = draft(client, headers, open_session(client, headers))
    assert add(client, headers, batch, food).status_code == 201
    submit(client, headers, batch)
    before = client.get('/api/print-jobs', headers=headers).json()
    with transaction() as db:
        item = db.get(MenuItem, food['id'])
        item.base_price, item.sold_out = 850, True
        for option in sauce['options']:
            row = db.get(ModifierOption, option['id'])
            if row.name == '汤':
                db.delete(row)  # Recreate an existing database with only the original sauces.
            else:
                row.is_default = row.name == '白酱'
                row.enabled = row.name != '红酱'
    seed(); seed()
    after = catalog(client, headers)['WANTAN_MEE']
    assert after['id'] == food['id'] and after['base_price'] == 850 and after['sold_out']
    group = next(group for group in after['groups'] if group['name'] == '酱汁')
    assert group['id'] == sauce['id'] and group['minimum'] == group['maximum'] == 1
    assert len(group['options']) == 4
    for option in group['options']:
        assert option['is_default'] == (option['name'] == '白酱')
        assert option['enabled'] == (option['name'] != '红酱')
        if option['name'] != '汤':
            assert option['id'] == next(old['id'] for old in sauce['options'] if old['name'] == option['name'])
        else:
            assert option['price'] == 0
    assert client.get('/api/print-jobs', headers=headers).json() == before


def test_soup_replaces_sauce_and_is_preserved_on_bill_stall_ticket_and_receipt(client, headers):
    food = catalog(client, headers)['WANTAN_MEE']
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    options = selections(food, '汤', '辣', '加面', '打包')
    result = add(client, headers, batch, food, options, 2)
    assert result.status_code == 201 and result.json()['line_total'] == 2000
    names = [entry['name'] for entry in result.json()['modifiers']]
    assert '汤' in names and all(name not in names for name in ['黑酱', '白酱', '红酱'])
    black = next(option['id'] for group in food['groups'] for option in group['options'] if option['name'] == '黑酱')
    assert add(client, headers, batch, food, [*options, black]).status_code == 422
    assert submit(client, headers, batch).status_code == 200
    bill = client.get(f'/api/table-sessions/{session}/bill', headers=headers).json()
    assert bill['total'] == 2000 and bill['items'][0]['modifiers'] == result.json()['modifiers']
    with transaction() as db:
        job = db.scalar(select(PrintJob).where(PrintJob.batch_id == batch))
        assert job.routing_group == 'KITCHEN'
        ticket = deepcopy(job.ticket)
        text = '\n'.join(line for line, _ in ticket_lines(ticket))
        assert '汤' in text and '辣' in text and '加面' in text and '打包' in text
        assert all(name not in text for name in ['黑酱', '白酱', '红酱'])
    payment = client.post(f'/api/table-sessions/{session}/payments', headers=key(headers),
        json={'method': 'QR', 'received': 2000, 'expected_total': 2000})
    assert payment.status_code == 200, payment.text
    receipt = client.get(f"/api/payments/{payment.json()['id']}/receipt", headers=headers).json()
    assert receipt['items'][0]['modifiers'] == result.json()['modifiers']
    seed()
    with transaction() as db:
        assert db.scalar(select(PrintJob).where(PrintJob.batch_id == batch)).ticket == ticket
