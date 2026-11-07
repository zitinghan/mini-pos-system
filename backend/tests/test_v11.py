"""v1.1 menu, immutable snapshots, routing, free orders and paid-session analytics."""
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4
import sys

import pytest
from sqlalchemy import select, func
from app.database.db import transaction
from app.database.seed import seed, DRINKS, SNACKS, BEERS
from app.models.entities import MenuItem, ModifierOption, OrderItem, TableSession, Payment, PrintJob
from app.printing.worker import run_once
from app.printing.tickets import ticket_lines
from app.services import orders
from test_workflows import key, open_session, draft, add, submit


def catalog(client, headers):
    return {item['sku']: item for item in client.get('/api/menu', headers=headers).json()}


def selections(food, *names):
    ids = [option['id'] for group in food['groups'] for option in group['options'] if option['is_default']]
    for name in names:
        group = next(group for group in food['groups'] if any(option['name'] == name for option in group['options']))
        if group['maximum'] == 1:
            ids = [identity for identity in ids if identity not in [option['id'] for option in group['options']]]
        ids.append(next(option['id'] for option in group['options'] if option['name'] == name))
    return ids


@pytest.mark.parametrize('sauce', ['黑酱', '白酱', '红酱'])
@pytest.mark.parametrize('spicy', ['辣', '不辣'])
@pytest.mark.parametrize('portion,price', [('普通', 800), ('加面', 1000)])
def test_wantan_all_combinations(client, headers, sauce, spicy, portion, price):
    food = catalog(client, headers)['WANTAN_MEE']
    batch = draft(client, headers, open_session(client, headers))
    response = add(client, headers, batch, food, selections(food, sauce, spicy, portion), 2)
    assert response.status_code == 201
    assert response.json()['line_total'] == price * 2


@pytest.mark.parametrize('preparation', ['汤', '干'])
@pytest.mark.parametrize('egg,price', [('不加蛋', 800), ('加蛋', 900)])
def test_kueh_options(client, headers, preparation, egg, price):
    food = catalog(client, headers)['MEE_HOON_KUEH']
    batch = draft(client, headers, open_session(client, headers))
    assert add(client, headers, batch, food, selections(food, preparation, egg)).json()['unit_price'] == price


@pytest.mark.parametrize('portion,price', [('普通', 800), ('大份', 1000)])
def test_curry_rice_portions(client, headers, portion, price):
    food = catalog(client, headers)['CURRY_RICE']
    batch = draft(client, headers, open_session(client, headers))
    assert add(client, headers, batch, food, selections(food, portion)).json()['unit_price'] == price


@pytest.mark.parametrize('sku,name,portion,price', SNACKS)
def test_all_snacks_and_kitchen_portions(client, headers, sku, name, portion, price):
    food = catalog(client, headers)[sku]
    assert food['groups'] == []
    batch = draft(client, headers, open_session(client, headers))
    result = add(client, headers, batch, food, [], 3).json()
    assert result['line_total'] == price * 3
    assert result['description'] == portion
    assert submit(client, headers, batch).status_code == 200
    with transaction() as db:
        ticket = db.scalar(select(PrintJob)).ticket
        assert ticket['items'][0]['printer_group'] == 'KITCHEN'
        assert portion in '\n'.join(line for line, _ in ticket_lines(ticket))


@pytest.mark.parametrize('sku,name,hot,iced', DRINKS)
def test_every_drink_explicit_hot_and_iced_prices(client, headers, sku, name, hot, iced):
    food = catalog(client, headers)[sku]
    batch = draft(client, headers, open_session(client, headers))
    for temperature, price in [('热 HOT', hot), ('冰 ICED', iced)]:
        result = add(client, headers, batch, food, selections(food, temperature), 2).json()
        assert result['line_total'] == 2 * price
        assert result['variant_name'] == temperature
        assert result['printer_group'] == 'BEVERAGE'
    both = [option['id'] for option in food['groups'][0]['options']]
    assert add(client, headers, batch, food, both).status_code == 422


def test_drink_price_edit_does_not_assume_thirty_sen_difference(client, headers):
    food = catalog(client, headers)['KOPI_O']
    iced = food['groups'][0]['options'][1]
    assert client.patch(f"/api/menu/options/{iced['id']}", headers=headers, json={'price': 450}).status_code == 200
    batch = draft(client, headers, open_session(client, headers))
    result = add(client, headers, batch, food, [iced['id']], 3)
    assert result.json()['line_total'] == 1350


@pytest.mark.parametrize('temperature', ['冷', '热'])
def test_free_water_independent_order_and_zero_payment(client, headers, temperature):
    foods = catalog(client, headers)
    assert foods['PLAIN_WATER']['id'] != foods['MINERAL_WATER']['id']
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    water = foods['PLAIN_WATER']
    assert add(client, headers, batch, water, selections(water, temperature), 3).json()['line_total'] == 0
    assert submit(client, headers, batch).json()['total'] == 0
    response = client.post(f'/api/table-sessions/{session}/payments', headers=key(headers), json={'method': 'CASH', 'received': 0, 'expected_total': 0})
    assert response.status_code == 200, response.text
    assert response.json()['total'] == 0
    assert client.get('/api/tables/5', headers=headers).json()['status'] == 'AVAILABLE'
    bill = client.get(f'/api/table-sessions/{session}/bill', headers=headers).json()
    assert bill['items'][0]['modifiers'][0]['name'] == temperature


@pytest.mark.parametrize('sku,name,single,triple', BEERS)
def test_beer_units_packages_and_physical_bottles(client, headers, sku, name, single, triple):
    food = catalog(client, headers)[sku]
    batch = draft(client, headers, open_session(client, headers))
    for package, price, bottles in [('单瓶', single, 1), ('3瓶', triple, 3)]:
        result = add(client, headers, batch, food, selections(food, package), 2).json()
        assert result['line_total'] == 2 * price
        assert result['bottles_per_unit'] == bottles
        assert result['physical_bottles'] == 2 * bottles
        assert result['variant_name'] == package


def test_customization_rules_are_per_item_and_remain_complimentary(client, headers):
    foods = catalog(client, headers)
    food = foods['WANTAN_MEE']
    batch = draft(client, headers, open_session(client, headers))
    extras = food['groups'][-1]['options']
    selected = selections(food, *[option['name'] for option in extras])
    assert add(client, headers, batch, food, selected).json()['unit_price'] == 800
    result = client.patch(f"/api/menu/options/{extras[0]['id']}/configuration", headers=headers, json={'enabled': True, 'incompatible_with': [extras[1]['id']]})
    assert result.status_code == 200
    assert add(client, headers, batch, food, selected).status_code == 422
    assert client.patch(f"/api/menu/options/{extras[0]['id']}", headers=headers, json={'price': 100}).status_code == 422
    assert add(client, headers, batch, foods['FRIES'], [extras[0]['id']]).status_code == 422
    assert client.patch(f"/api/menu/options/{extras[0]['id']}/configuration", headers=headers, json={'enabled': False, 'incompatible_with': []}).status_code == 200
    assert add(client, headers, batch, food, selections(food, extras[0]['name'])).status_code == 422
    assert foods['CURRY_RICE']['groups'][-1]['options'][0]['id'] != extras[0]['id']


def test_repeat_seed_preserves_admin_edits_and_verification(client, headers):
    foods = catalog(client, headers)
    drink = foods['MINERAL_WATER']
    assert drink['verification_required']
    option = drink['groups'][0]['options'][1]
    client.patch(f"/api/menu/options/{option['id']}", headers=headers, json={'price': 345})
    client.post(f"/api/menu/items/{drink['id']}/verify", headers=headers)
    seed()
    again = catalog(client, headers)
    assert len(again) == 29
    assert again.keys() == foods.keys()
    assert not again['MINERAL_WATER']['verification_required']
    assert again['MINERAL_WATER']['groups'][0]['options'][1]['unit_price'] == 345
    assert {item['category_code'] for item in again.values()} == {'MAINS', 'SNACKS', 'DRINKS', 'BEER'}


def mixed_batch(client, headers, session, foods):
    batch = draft(client, headers, session)
    for sku, quantity, names in [('WANTAN_MEE', 2, ['辣', '加面']), ('MEE_HOON_KUEH', 1, ['加蛋']), ('KOPI_O', 2, ['冰 ICED']), ('FRIED_WANTAN', 1, []), ('PLAIN_WATER', 1, ['冷'])]:
        food = foods[sku]
        assert add(client, headers, batch, food, selections(food, *names), quantity).status_code == 201
    return batch


def test_mixed_4120_bill_rounds_snapshots_and_combined_printing(client, headers, monkeypatch):
    foods = catalog(client, headers)
    session = open_session(client, headers)
    monkeypatch.setattr(orders, 'now', lambda: '2026-11-07T04:00:00+00:00')
    batch = mixed_batch(client, headers, session, foods)
    identity = str(uuid4())
    first = submit(client, headers, batch, identity).json()
    assert first['total'] == 4120
    assert submit(client, headers, batch, identity).json() == first
    with transaction() as db:
        record = db.get(TableSession, session)
        assert record.first_order_at == '2026-11-07T04:00:00+00:00'
        ticket = db.scalar(select(PrintJob)).ticket
        assert ticket['order_type'] == 'NEW'
        text = '\n'.join(line for line, _ in ticket_lines(ticket))
        assert '厨房' in text and '饮料' in text
        assert text.count('2 x Kopi O') == 1 and '冰 ICED' in text and '冷' in text
    assert run_once()
    monkeypatch.setattr(orders, 'now', lambda: '2026-11-07T04:10:00+00:00')
    extra = draft(client, headers, session)
    beer = foods['CARLSBERG']
    assert add(client, headers, extra, beer, selections(beer, '3瓶'), 2).json()['physical_bottles'] == 6
    submit(client, headers, extra)
    with transaction() as db:
        assert db.get(TableSession, session).first_order_at == '2026-11-07T04:00:00+00:00'
        job = db.scalar(select(PrintJob).where(PrintJob.batch_id == extra))
        assert job.ticket['order_type'] == 'ADD-ON' and len(job.ticket['items']) == 1
    client.patch(f"/api/menu/options/{beer['groups'][0]['options'][1]['id']}", headers=headers, json={'price': 7000})
    monkeypatch.setattr(orders, 'now', lambda: '2026-11-07T04:42:00+00:00')
    paid = client.post(f'/api/table-sessions/{session}/payments', headers=key(headers), json={'method': 'CASH', 'received': 20000, 'expected_total': 16120})
    assert paid.status_code == 200, paid.text
    bill = client.get(f'/api/table-sessions/{session}/bill', headers=headers).json()
    assert bill['dining_duration_seconds'] == 2520
    assert bill['items'][-1]['unit_price'] == 6000
    report = client.get('/api/reports/daily-sales?day=2026-11-07', headers=headers).json()
    assert report['category_sales'] == {'MAINS': 2900, 'SNACKS': 700, 'DRINKS': 520, 'BEER': 12000}
    assert report['average_spending'] == 16120
    assert report['beer_bottles'] == 6 and report['beer_units'] == 2
    assert report['dining_duration']['average_seconds'] == 2520


def test_separate_stations_have_disjoint_jobs_and_safe_independent_reprint(client, headers):
    settings = client.get('/api/printers/config', headers=headers).json()
    settings['separate_stations'] = True
    assert client.put('/api/printers/config', headers=headers, json=settings).status_code == 200
    foods = catalog(client, headers)
    batch = mixed_batch(client, headers, open_session(client, headers), foods)
    result = submit(client, headers, batch).json()
    assert len(result['print_jobs']) == 2
    with transaction() as db:
        jobs = list(db.scalars(select(PrintJob)))
        item_ids = []
        for job in jobs:
            assert all(item['printer_group'] == job.routing_group for item in job.ticket['items'])
            item_ids.extend(item['id'] for item in job.ticket['items'])
        assert len(item_ids) == len(set(item_ids)) == 5
    assert run_once()
    first_id = result['print_jobs'][0]['id']
    response = client.post(f'/api/print-jobs/{first_id}/retry', headers=key(headers))
    assert response.status_code == 201  # Other station still pending must not block this retry.
    assert run_once() and run_once() and not run_once()


def test_network_station_hosts_and_large_text_commands_without_hardware(client, headers, monkeypatch):
    sent = []
    class Printer:
        def __init__(self, **kwargs): self.output = b''
        def _raw(self, data): self.output += data
    class Connection:
        def settimeout(self, seconds): pass
        def sendall(self, payload): sent[-1].append(payload)
        def close(self): pass
    def connect(address, timeout):
        sent.append([address])
        return Connection()
    monkeypatch.setitem(sys.modules, 'escpos.printer', SimpleNamespace(Dummy=Printer))
    monkeypatch.setattr('app.printing.worker.socket.create_connection', connect)
    settings = client.get('/api/printers/config', headers=headers).json()
    settings.update(mode='network', print_mode='text', separate_stations=True, kitchen_host='192.168.1.200', beverage_host='192.168.1.201')
    assert client.put('/api/printers/config', headers=headers, json=settings).status_code == 200
    foods = catalog(client, headers)
    batch = mixed_batch(client, headers, open_session(client, headers), foods)
    submit(client, headers, batch)
    assert run_once() and run_once()
    assert [entry[0][0] for entry in sent] == ['192.168.1.200', '192.168.1.201']
    assert b'\x1d\x21\x11' in sent[1][1]
    assert 'Kopi O'.encode() in sent[1][1] and 'Kopi O'.encode() not in sent[0][1]


@pytest.mark.parametrize('status,first,paid,expected', [
    ('PAID', '2026-11-07T04:00:00+00:00', '2026-11-07T04:42:00+00:00', 2520),
    ('OCCUPIED', '2026-11-07T04:00:00+00:00', '2026-11-07T04:42:00+00:00', None),
    ('PAID', None, '2026-11-07T04:42:00+00:00', None),
    ('PAID', 'invalid', '2026-11-07T04:42:00+00:00', None),
    ('PAID', '2026-11-07T05:00:00+00:00', '2026-11-07T04:42:00+00:00', None),
    ('PAID', '2026-11-07T04:00:00', '2026-11-07T04:42:00+00:00', None),
])
def test_dining_duration_validity(status, first, paid, expected):
    assert orders.dining_duration(SimpleNamespace(status=status, first_order_at=first, paid_at=paid)) == expected


def test_daily_duration_average_excludes_unpaid_and_invalid(client, headers):
    with transaction() as db:
        for table_id, first, status, paid in [
            (1, '2026-11-06T16:00:00+00:00', 'PAID', '2026-11-06T16:10:00+00:00'),
            (2, '2026-11-06T16:00:00+00:00', 'PAID', '2026-11-06T16:30:00+00:00'),
            (3, 'invalid', 'PAID', '2026-11-06T17:00:00+00:00'),
            (4, '2026-11-06T16:00:00+00:00', 'OCCUPIED', None),
        ]:
            session = TableSession(table_id=table_id, status=status, first_order_at=first, paid_at=paid)
            db.add(session); db.flush()
            if paid:
                db.add(Payment(session_id=session.id, user_id=1, idempotency_key=str(uuid4()), request_hash='test', method='QR', total=800, received=800, change=0, created_at=paid))
    report = client.get('/api/reports/daily-sales?day=2026-11-07', headers=headers).json()
    assert report['completed_sessions'] == 3
    assert report['dining_duration'] == {'count': 2, 'average_seconds': 1200, 'minimum_seconds': 600, 'maximum_seconds': 1800}
    assert report['total'] == 2400 and report['methods']['QR'] == 2400

@pytest.mark.parametrize('separate,job_count', [(False, 1), (True, 2)])
def test_printer_test_routes_to_configured_stations(client, headers, separate, job_count):
    settings = client.get('/api/printers/config', headers=headers).json()
    settings['separate_stations'] = separate
    client.put('/api/printers/config', headers=headers, json=settings)
    response = client.post('/api/printers/test-print', headers=headers)
    assert response.status_code == 201
    assert len(response.json()['print_jobs']) == job_count
    for _ in range(job_count):
        assert run_once()
    assert not run_once()


def test_notes_and_beer_snapshots_survive_later_menu_edits(client, headers):
    food = catalog(client, headers)['TIGER']
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    payload = {'menu_item_id': food['id'], 'quantity': 2, 'option_ids': selections(food, '3瓶'), 'notes': '先上三瓶'}
    result = client.post(f'/api/order-batches/{batch}/items', headers=key(headers), json=payload)
    assert result.status_code == 201
    submit(client, headers, batch)
    with transaction() as db:
        item = db.get(MenuItem, food['id'])
        item.name = 'Changed beer name'
        option = db.get(ModifierOption, payload['option_ids'][0])
        option.bottles, option.unit_price, option.name = 5, 10000, 'Changed package'
    bill = client.get(f'/api/table-sessions/{session}/bill', headers=headers).json()
    line = bill['items'][0]
    assert line['name'] == 'Tiger' and line['variant_name'] == '3瓶'
    assert line['physical_bottles'] == 6 and line['line_total'] == 11400
    assert line['notes'] == '先上三瓶'
    assert line['modifiers'][0]['name'] == '3瓶'


def test_draft_add_replays_legacy_audit_without_notes_field(client, headers):
    from app.models.entities import AuditLog
    food = catalog(client, headers)['WANTAN_MEE']
    batch = draft(client, headers, open_session(client, headers))
    payload = {'menu_item_id': food['id'], 'quantity': 1, 'option_ids': selections(food)}
    request_headers = key(headers)
    first = client.post(f'/api/order-batches/{batch}/items', headers=request_headers, json=payload)
    assert first.status_code == 201
    with transaction() as db:
        audit = db.scalar(select(AuditLog).where(AuditLog.action == 'ADD_ITEM'))
        details = audit.details.copy()
        details.pop('notes')
        audit.details = details
    replay = client.post(f'/api/order-batches/{batch}/items', headers=request_headers, json=payload)
    assert replay.status_code == 201
    assert replay.json()['id'] == first.json()['id']
    with transaction() as db:
        assert db.scalar(select(func.count()).select_from(OrderItem)) == 1
