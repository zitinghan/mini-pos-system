from copy import deepcopy
from pathlib import Path
import runpy
from sqlalchemy import select
from app.database.db import transaction
from app.database.seed import seed
from app.models.entities import PrintJob, ModifierGroup, ModifierOption, MenuItemModifierGroup, MenuItem, Payment
from app.printing.tickets import ticket_lines
from test_v11 import catalog, selections
from test_workflows import open_session, draft, add, submit, key


def test_all_seven_canned_choices_preserve_prices_and_print_selected_brand(client, headers):
    food = catalog(client, headers)['CANNED']
    assert food['base_price'] == 300 and not food['verification_required']
    assert not any(group['name'] == '温度' for group in food['groups'])
    group = next(group for group in food['groups'] if group['name'] == '品牌 / 口味')
    assert [entry['name'] for entry in group['options']] == ['Sprite','Coke','Fanta','100 PLUS','菊花茶','7UP','Passion Fruit']
    assert group['minimum'] == 0 and group['maximum'] == 1
    assert all(entry['price'] == 0 and not entry['is_default'] and entry['unit_price'] is None for entry in group['options'])
    batch = draft(client, headers, open_session(client, headers))
    for entry in group['options']:
        result = add(client, headers, batch, food, selections(food, entry['name'], '打包'), 2)
        assert result.status_code == 201 and result.json()['line_total'] == 600
        assert result.json()['variant_name'] is None
    legacy = add(client, headers, batch, food, selections(food))
    assert legacy.status_code == 201 and legacy.json()['unit_price'] == 300
    assert not any(entry['name'] in [option['name'] for option in legacy.json()['modifiers']] for entry in group['options'])
    both = selections(food) + [group['options'][0]['id'],group['options'][1]['id']]
    assert add(client, headers, batch, food, both).status_code == 422
    submit(client, headers, batch)
    with transaction() as db:
        ticket = db.scalar(select(PrintJob)).ticket
        assert all(entry['name'] in '\n'.join(text for text,_ in ticket_lines(ticket)) for entry in group['options'])
    seed(); seed()
    again = catalog(client, headers)['CANNED']
    assert len([section for section in again['groups'] if section['name'] == '品牌 / 口味']) == 1
    assert len(next(section for section in again['groups'] if section['name'] == '品牌 / 口味')['options']) == 7


def test_canned_upgrade_preserves_iced_receipts_prices_options_and_allows_old_draft_to_be_updated(client, headers, monkeypatch):
    item_id = catalog(client, headers)['CANNED']['id']
    with transaction() as db:
        group = ModifierGroup(name='温度', minimum=1, maximum=1, display_order=0)
        db.add(group); db.flush()
        iced = ModifierOption(group_id=group.id, name='冰 ICED', price=0, unit_price=330, is_default=True)
        db.add_all([iced, MenuItemModifierGroup(item_id=item_id, group_id=group.id)])
        db.get(MenuItem, item_id).verification_required = True
        db.flush(); old_option_id = iced.id
    old_food = catalog(client, headers)['CANNED']
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    add(client, headers, batch, old_food, selections(old_food, '冰 ICED', 'Coke'), 2)
    submit(client, headers, batch)
    payment = client.post(f'/api/table-sessions/{session}/payments', headers=key(headers), json={
        'method':'QR','received':660,'expected_total':660}).json()
    receipt = client.get(f"/api/payments/{payment['id']}/receipt", headers=headers).json()
    old_orders = client.get(f'/api/table-sessions/{session}/orders', headers=headers).json()
    with transaction() as db: original_ticket = deepcopy(db.scalar(select(PrintJob)).ticket)
    next_session = open_session(client, headers)
    old_batch = draft(client, headers, next_session)
    old_item = add(client, headers, old_batch, old_food, selections(old_food, '冰 ICED', 'Coke')).json()
    submit(client, headers, old_batch)
    next_batch = draft(client, headers, next_session)
    pending = add(client, headers, next_batch, old_food, selections(old_food, '冰 ICED', 'Sprite')).json()
    upgrade = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'alembic/versions/0013_canned_fixed_price.py'))
    with transaction() as db:
        monkeypatch.setattr(upgrade['op'], 'get_bind', lambda: db.connection())
        upgrade['upgrade']()
    seed(); seed()
    food = catalog(client, headers)['CANNED']
    assert food['id'] == item_id and food['base_price'] == 300
    assert not food['verification_required'] and not any(group['name']=='温度' for group in food['groups'])
    assert client.get(f'/api/table-sessions/{session}/orders', headers=headers).json() == old_orders
    assert client.get(f"/api/payments/{payment['id']}/receipt", headers=headers).json() == receipt
    with transaction() as db:
        assert db.get(ModifierOption, old_option_id).unit_price == 330
        assert db.scalar(select(PrintJob)).ticket == original_ticket
        assert db.get(Payment, payment['id']).total == 660
    updated = client.patch(f"/api/order-batches/{next_batch}/items/{pending['id']}", headers=key(headers), json={
        'menu_item_id':item_id,'quantity':1,'option_ids':selections(food, 'Sprite'),
        'expected_revision':1,'expected_unit_price':300})
    assert updated.status_code == 200, updated.text
    assert updated.json()['unit_price'] == 300 and updated.json()['variant_name'] is None
    assert submit(client, headers, next_batch).json()['total'] == 300
    revised = client.patch(f"/api/order-batches/{old_batch}/items/{old_item['id']}", headers=key(headers), json={
        'menu_item_id':item_id,'quantity':1,'option_ids':selections(food, 'Coke'),'notes':'已核实',
        'expected_revision':1,'expected_unit_price':330})
    assert revised.status_code == 200 and revised.json()['unit_price'] == 330
