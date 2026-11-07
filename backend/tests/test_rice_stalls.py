import pytest
from sqlalchemy import select

from app.database.db import transaction
from app.database.seed import seed
from app.models.entities import MenuItem, OrderItem, PrintJob
from app.printing.tickets import ticket_lines
from app.printing.worker import run_once
from test_v11 import catalog, selections
from test_workflows import open_session, draft, add, submit, key


@pytest.mark.parametrize('sku', ['CURRY_RICE', 'BRAISED_PORK_RICE', 'PLAIN_CURRY_RICE'])
@pytest.mark.parametrize('portion,price', [('普通', 800), ('大份', 1000)])
def test_rice_prices_portions_and_route(client, headers, sku, portion, price):
    food = catalog(client, headers)[sku]
    batch = draft(client, headers, open_session(client, headers))
    result = add(client, headers, batch, food, selections(food, portion), 2).json()
    assert result['unit_price'] == price and result['line_total'] == price * 2
    assert result['printer_group'] == food['printer_group'] == 'RICE'
    response = submit(client, headers, batch).json()
    assert [job['routing_group'] for job in response['print_jobs']] == ['RICE']


def test_new_sides_are_first_and_reseeding_preserves_edits(client, headers):
    foods = client.get('/api/menu', headers=headers).json()
    sides = [food for food in foods if food['category_code'] == 'SNACKS']
    assert [food['name'] for food in sides[:2]] == ['卤肉', '咖喱鸡']
    batch = draft(client, headers, open_session(client, headers))
    for food in sides[:2]:
        assert food['base_price'] == 800 and all(group['minimum'] == 0 for group in food['groups'])
        result = add(client, headers, batch, food, quantity=3).json()
        assert result['line_total'] == 2400 and result['printer_group'] == 'RICE'
    client.patch(f"/api/menu/items/{sides[0]['id']}", headers=headers, json={'price': 850})
    seed(); seed()
    again = catalog(client, headers)
    assert len(again) == 34 and again['BRAISED_PORK_SIDE']['base_price'] == 850
    assert again['BRAISED_PORK_SIDE']['id'] == sides[0]['id']


@pytest.mark.parametrize('separate', [False, True])
def test_three_stalls_print_disjoint_tickets_with_same_table_batch_and_safe_retry(client, headers, separate):
    settings = client.get('/api/printers/config', headers=headers).json()
    settings['separate_stations'] = separate
    assert client.put('/api/printers/config', headers=headers, json=settings).status_code == 200
    foods = catalog(client, headers)
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    skus = ['WANTAN_MEE', 'MEE_HOON_KUEH', 'CURRY_RICE', 'BRAISED_PORK_RICE',
            'PLAIN_CURRY_RICE', 'BRAISED_PORK_SIDE', 'CURRY_CHICKEN_SIDE', 'MILO']
    for sku in skus:
        food = foods[sku]
        assert add(client, headers, batch, food, selections(food)).status_code == 201
    first = submit(client, headers, batch, 'three-stall-submit').json()
    assert submit(client, headers, batch, 'three-stall-submit').json() == first
    assert first['total'] == 5900
    assert [job['routing_group'] for job in first['print_jobs']] == ['KITCHEN', 'RICE', 'BEVERAGE']
    with transaction() as db:
        jobs = list(db.scalars(select(PrintJob).order_by(PrintJob.id)))
        assert [len(job.ticket['items']) for job in jobs] == [2, 5, 1]
        assert all(job.ticket['table'] == 'T05' and job.ticket['batch_id'] == batch for job in jobs)
        ids = [item['id'] for job in jobs for item in job.ticket['items']]
        assert len(ids) == len(set(ids)) == len(skus)
        text = '\n'.join(line for line, _ in ticket_lines(jobs[1].ticket))
        assert '饭档' in text and '卤肉饭' in text and '咖喱鸡' in text and 'Milo' not in text
    assert run_once() and run_once() and run_once() and not run_once()
    rice_id = first['print_jobs'][1]['id']
    retry = client.post(f'/api/print-jobs/{rice_id}/retry', headers=key(headers)).json()
    assert retry['routing_group'] == 'RICE'
    assert run_once()
    extra = draft(client, headers, session)
    assert add(client, headers, extra, foods['PLAIN_CURRY_RICE'], selections(foods['PLAIN_CURRY_RICE'], '大份')).status_code == 201
    additional = submit(client, headers, extra).json()
    assert len(additional['print_jobs']) == 1 and additional['print_jobs'][0]['routing_group'] == 'RICE'
    with transaction() as db:
        job = db.scalar(select(PrintJob).where(PrintJob.batch_id == extra))
        assert job.ticket['order_type'] == 'ADD-ON' and len(job.ticket['items']) == 1


@pytest.mark.parametrize('rice_host,expected', [('192.168.1.202', '192.168.1.202'), ('', '192.168.1.200')])
def test_rice_network_destination_and_existing_two_printer_fallback(client, headers, monkeypatch, rice_host, expected):
    sent = []
    class Connection:
        def settimeout(self, seconds): pass
        def sendall(self, payload): assert payload
        def close(self): pass
    def connect(address, timeout):
        sent.append(address)
        return Connection()
    monkeypatch.setattr('app.printing.worker.socket.create_connection', connect)
    config = client.get('/api/printers/config', headers=headers).json()
    config.update(mode='network', print_mode='text', separate_stations=True, kitchen_host='192.168.1.200',
                  kitchen_port=9101, rice_host=rice_host, rice_port=9102, beverage_host='192.168.1.201')
    assert client.put('/api/printers/config', headers=headers, json=config).status_code == 200
    foods = catalog(client, headers)
    batch = draft(client, headers, open_session(client, headers))
    for sku in ['WANTAN_MEE', 'CURRY_RICE', 'MILO']:
        assert add(client, headers, batch, foods[sku], selections(foods[sku])).status_code == 201
    submit(client, headers, batch)
    assert run_once() and run_once() and run_once()
    assert sent == [('192.168.1.200', 9101), (expected, 9102 if rice_host else 9101), ('192.168.1.201', 9100)]


def test_changed_menu_stall_does_not_rewrite_submitted_snapshots(client, headers):
    food = catalog(client, headers)['CURRY_RICE']
    with transaction() as db:
        db.get(MenuItem, food['id']).printer_group = None
    session = open_session(client, headers)
    old = draft(client, headers, session)
    assert add(client, headers, old, food, selections(food)).status_code == 201
    original = submit(client, headers, old).json()
    with transaction() as db:
        db.get(MenuItem, food['id']).printer_group = 'RICE'
    new = draft(client, headers, session)
    assert add(client, headers, new, food, selections(food)).status_code == 201
    assert submit(client, headers, new).json()['print_jobs'][0]['routing_group'] == 'RICE'
    with transaction() as db:
        assert db.scalar(select(OrderItem).where(OrderItem.batch_id == old)).printer_group == 'KITCHEN'
        job = db.get(PrintJob, original['print_job_id'])
        assert job.routing_group == job.ticket['items'][0]['printer_group'] == 'KITCHEN'
