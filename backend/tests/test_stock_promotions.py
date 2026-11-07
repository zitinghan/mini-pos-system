from datetime import datetime, timezone
import pytest
from sqlalchemy import select, func

from app.database.db import transaction
from app.database.seed import seed
from app.models.entities import MenuItem, MenuPromotion, OrderItem, PrintJob, OrderBatch, TableSession, AuditLog
from app.services import promotions
from test_workflows import key, open_session, draft, add, submit
from test_v11 import catalog, selections


@pytest.fixture
def campaign(client, headers, monkeypatch):
    monkeypatch.setattr(promotions, 'current_day', lambda: '2026-11-07')
    response = client.put('/api/menu/promotions/kopi-teh', headers=headers, json={
        'starts_on': '2026-11-07', 'ends_on': '2026-12-01', 'unit_price': 100, 'enabled': True})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize('sku', promotions.KOPI_TEH_SKUS)
@pytest.mark.parametrize('temperature', ['热 HOT', '冰 ICED'])
def test_all_six_kopi_teh_hot_iced_cost_rm1(client, headers, campaign, sku, temperature):
    food = catalog(client, headers)[sku]
    assert food['base_price'] == 100
    assert food['regular_base_price'] > 100
    assert food['promotion']['ends_on'] == '2026-12-01'
    assert all(option['unit_price'] == 100 for option in food['groups'][0]['options'])
    assert all(option['regular_unit_price'] > 100 for option in food['groups'][0]['options'])
    batch = draft(client, headers, open_session(client, headers))
    result = add(client, headers, batch, food, selections(food, temperature), 3)
    assert result.status_code == 201
    assert result.json()['unit_price'] == 100 and result.json()['line_total'] == 300
    assert submit(client, headers, batch).json()['total'] == 300


@pytest.mark.parametrize('sku,hot,iced', [('WHITE_COFFEE', 350, 380), ('THREE_LAYER_TEA', 330, 360), ('MILO', 300, 330), ('MINERAL_WATER', 180, 210)])
def test_excluded_drinks_keep_regular_prices(client, headers, campaign, sku, hot, iced):
    food = catalog(client, headers)[sku]
    assert food['promotion'] is None
    assert [option['unit_price'] for option in food['groups'][0]['options']] == [hot, iced]
    batch = draft(client, headers, open_session(client, headers))
    assert add(client, headers, batch, food, selections(food, '冰 ICED')).json()['unit_price'] == iced


@pytest.mark.parametrize('day,price', [('2026-11-06', 260), ('2026-11-07', 100), ('2026-12-01', 100), ('2026-12-02', 260)])
def test_inclusive_promotion_dates_restore_regular_price(client, headers, campaign, monkeypatch, day, price):
    monkeypatch.setattr(promotions, 'current_day', lambda: day)
    food = catalog(client, headers)['KOPI_O']
    batch = draft(client, headers, open_session(client, headers))
    assert food['groups'][0]['options'][1]['unit_price'] == price
    assert add(client, headers, batch, food, selections(food, '冰 ICED')).json()['unit_price'] == price


def test_malaysia_midnight_boundary():
    assert promotions.current_day(datetime(2026, 12, 1, 15, 59, 59, tzinfo=timezone.utc)) == '2026-12-01'
    assert promotions.current_day(datetime(2026, 12, 1, 16, 0, 0, tzinfo=timezone.utc)) == '2026-12-02'


def test_promotion_prices_snapshot_and_regular_edits_survive_expiry(client, headers, campaign, monkeypatch):
    food = catalog(client, headers)['KOPI_O']
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    add(client, headers, batch, food, selections(food, '冰 ICED'), 2)
    submit(client, headers, batch)
    iced_id = food['groups'][0]['options'][1]['id']
    assert client.patch(f'/api/menu/options/{iced_id}', headers=headers, json={'price': 460}).status_code == 200
    assert catalog(client, headers)['KOPI_O']['groups'][0]['options'][1]['unit_price'] == 100
    monkeypatch.setattr(promotions, 'current_day', lambda: '2026-12-02')
    assert catalog(client, headers)['KOPI_O']['groups'][0]['options'][1]['unit_price'] == 460
    bill = client.get(f'/api/table-sessions/{session}/bill', headers=headers).json()
    assert bill['total'] == 200 and bill['items'][0]['unit_price'] == 100
    payment = client.post(f'/api/table-sessions/{session}/payments', headers=key(headers), json={'method': 'CASH', 'received': 500, 'expected_total': 200})
    assert payment.status_code == 200 and payment.json()['change'] == 300
    seed()
    with transaction() as db:
        assert db.scalar(select(func.count()).select_from(MenuPromotion)) == 1


def test_only_admin_can_change_availability_or_campaign(client, headers):
    food = catalog(client, headers)['WANTAN_MEE']
    token = client.post('/api/auth/login', json={'name': 'staff', 'pin': '654321'}).json()['token']
    staff = {'Authorization': 'Bearer ' + token}
    assert client.patch(f"/api/menu/items/{food['id']}/availability", headers=staff, json={'sold_out': True}).status_code == 403
    assert client.put('/api/menu/promotions/kopi-teh', headers=staff, json={'starts_on': '2026-11-07', 'ends_on': '2026-12-01', 'unit_price': 100}).status_code == 403
    assert client.get('/api/menu/promotions', headers=staff).status_code == 403


def test_sold_out_sync_blocks_cached_clients_and_restores_supply(client, headers):
    food = catalog(client, headers)['WANTAN_MEE']
    batch = draft(client, headers, open_session(client, headers))
    response = client.patch(f"/api/menu/items/{food['id']}/availability", headers=headers, json={'sold_out': True})
    assert response.status_code == 200
    staff_token = client.post('/api/auth/login', json={'name': 'staff', 'pin': '654321'}).json()['token']
    staff = {'Authorization': 'Bearer ' + staff_token}
    assert catalog(client, staff)['WANTAN_MEE']['sold_out']
    response = add(client, headers, batch, food, selections(food))
    assert response.status_code == 409 and '已售罄' in response.json()['detail']
    seed()
    assert catalog(client, headers)['WANTAN_MEE']['sold_out']
    assert client.patch(f"/api/menu/items/{food['id']}/availability", headers=headers, json={'sold_out': False}).status_code == 200
    assert add(client, headers, batch, food, selections(food)).status_code == 201
    with transaction() as db:
        changes = list(db.scalars(select(AuditLog).where(AuditLog.action == 'MENU_AVAILABILITY')))
        assert [change.details['sold_out'] for change in changes] == [True, False]


def test_sold_out_draft_rejects_entire_submission_without_partial_print(client, headers):
    foods = catalog(client, headers)
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    add(client, headers, batch, foods['FRIES'], [], 1)
    add(client, headers, batch, foods['WANTAN_MEE'], selections(foods['WANTAN_MEE']), 1)
    client.patch(f"/api/menu/items/{foods['WANTAN_MEE']['id']}/availability", headers=headers, json={'sold_out': True})
    response = submit(client, headers, batch)
    assert response.status_code == 409
    with transaction() as db:
        assert db.scalar(select(func.count()).select_from(PrintJob)) == 0
        assert db.get(OrderBatch, batch).status == 'DRAFT'
        assert db.get(TableSession, session).first_order_at is None
        assert all(item.status == 'DRAFT' for item in db.scalars(select(OrderItem)))


def test_marking_sold_out_preserves_submitted_bill_payment_and_replay(client, headers):
    food = catalog(client, headers)['WANTAN_MEE']
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    add(client, headers, batch, food, selections(food))
    identity = 'submitted-before-stock-change'
    first = submit(client, headers, batch, identity)
    client.patch(f"/api/menu/items/{food['id']}/availability", headers=headers, json={'sold_out': True})
    replay = submit(client, headers, batch, identity)
    assert replay.status_code == 200 and replay.json() == first.json()
    bill = client.get(f'/api/table-sessions/{session}/bill', headers=headers).json()
    assert bill['total'] == 800
    assert client.post(f'/api/table-sessions/{session}/payments', headers=key(headers), json={'method': 'CASH', 'received': 1000, 'expected_total': 800}).status_code == 200


def test_promotion_upsert_is_idempotent_and_invalid_dates_are_rejected(client, headers, campaign):
    payload = {'starts_on': '2026-11-07', 'ends_on': '2026-12-01', 'unit_price': 100}
    repeat = client.put('/api/menu/promotions/kopi-teh', headers=headers, json=payload)
    assert repeat.status_code == 200 and repeat.json()['id'] == campaign['id']
    assert repeat.json()['skus'] == promotions.KOPI_TEH_SKUS
    assert client.put('/api/menu/promotions/kopi-teh', headers=headers, json={**payload, 'ends_on': '2026-10-01'}).status_code == 422
    assert client.put('/api/menu/promotions/kopi-teh', headers=headers, json={**payload, 'ends_on': 'not-a-date'}).status_code == 422
    assert client.put('/api/menu/promotions/kopi-teh', headers=headers, json={**payload, 'unit_price': 0}).status_code == 422
