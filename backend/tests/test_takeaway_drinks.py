import pytest
from sqlalchemy import select, func

from app.database.db import transaction
from app.database.seed import seed, DRINKS
from app.models.entities import ModifierGroup, ModifierOption, PrintJob
from app.services.orders import price_item
from app.printing.tickets import ticket_lines
from test_v11 import catalog, selections
from test_workflows import open_session, draft, add, submit, key


def option(food, group, prefix):
    return next(entry for section in food['groups'] if section['name'] == group
                for entry in section['options'] if entry['name'].startswith(prefix))


def test_every_product_has_free_mutually_exclusive_takeaway_and_legacy_default(client, headers):
    foods = catalog(client, headers)
    assert len(foods) == 33
    with transaction() as db:
        for food in foods.values():
            pack = next(group for group in food['groups'] if group['name'] == '用餐方式')
            assert pack['minimum'] == 0 and pack['maximum'] == 1
            assert [(entry['name'], entry['price'], entry['is_default']) for entry in pack['options']] == [('堂食', 0, True), ('打包', 0, False)]
            legacy = [identity for identity in selections(food) if identity not in [entry['id'] for entry in pack['options']]]
            _, _, original = price_item(db, food['id'], 2, legacy)
            _, _, takeaway = price_item(db, food['id'], 2, selections(food, '打包'))
            assert takeaway == original


def test_taste_and_ice_options_apply_only_to_prepared_drinks(client, headers):
    prepared = {sku for sku, *_ in DRINKS} - {'MINERAL_WATER', 'CANNED'}
    for sku, food in catalog(client, headers).items():
        groups = {group['name']: group for group in food['groups']}
        for name in ['甜度', '浓度', '冰量']:
            assert (name in groups) == (sku in prepared)
        if sku in prepared:
            assert groups['甜度']['maximum'] == groups['冰量']['maximum'] == 1
            assert all(entry['price'] == 0 and entry['unit_price'] is None
                for name in ['甜度', '浓度', '冰量'] for entry in groups[name]['options'])


@pytest.mark.parametrize('temperature,sweetness,ice,price', [
    ('冰 ICED', 'Kosong', '少冰', 260), ('冰 ICED', 'Siu Dai', '去冰', 260), ('热 HOT', 'Siu Dai', None, 230),
])
def test_drink_choices_preserve_price_printing_and_paid_snapshot(client, headers, temperature, sweetness, ice, price):
    food = catalog(client, headers)['KOPI_O']
    names = [temperature, option(food, '甜度', sweetness)['name'], 'Kao（加浓）', '打包']
    if ice:
        names.append(option(food, '冰量', ice)['name'])
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    result = add(client, headers, batch, food, selections(food, *names), 3)
    assert result.status_code == 201, result.text
    assert result.json()['line_total'] == price * 3
    submitted = submit(client, headers, batch).json()
    assert [job['routing_group'] for job in submitted['print_jobs']] == ['BEVERAGE']
    with transaction() as db:
        ticket = db.scalar(select(PrintJob)).ticket
        text = '\n'.join(line for line, _ in ticket_lines(ticket))
        assert all(name in text for name in names)
    payment = client.post(f'/api/table-sessions/{session}/payments', headers=key(headers),
        json={'method': 'QR', 'received': price * 3, 'expected_total': price * 3}).json()
    receipt = client.get(f"/api/payments/{payment['id']}/receipt", headers=headers).json()
    assert {entry['name'] for entry in receipt['items'][0]['modifiers']} >= set(names)
    with transaction() as db:
        db.get(ModifierOption, option(food, '甜度', sweetness)['id']).name = 'Changed later'
    assert client.get(f"/api/payments/{payment['id']}/receipt", headers=headers).json()['items'] == receipt['items']


def test_server_rejects_double_sweetness_double_ice_hot_ice_and_foreign_modifiers(client, headers):
    foods = catalog(client, headers)
    food = foods['KOPI_O']
    batch = draft(client, headers, open_session(client, headers))
    sugar = [option(food, '甜度', prefix)['id'] for prefix in ['Kosong', 'Siu Dai']]
    ice = [option(food, '冰量', prefix)['id'] for prefix in ['少冰', '去冰']]
    dine = option(food, '用餐方式', '堂食')['id']
    takeaway = option(food, '用餐方式', '打包')['id']
    for ids in [selections(food, '冰 ICED') + sugar, selections(food, '冰 ICED') + ice,
                selections(food) + [ice[0]], selections(food) + [takeaway],
                selections(food) + [option(foods['TEH'], '用餐方式', '打包')['id']]]:
        assert add(client, headers, batch, food, ids).status_code == 422
    assert dine in selections(food)


def test_takeaway_reaches_each_stall_without_duplicates(client, headers):
    foods = catalog(client, headers)
    batch = draft(client, headers, open_session(client, headers))
    for sku in ['WANTAN_MEE', 'BRAISED_PORK_RICE', 'CURRY_CHICKEN_SIDE', 'MILO', 'PLAIN_WATER', 'CARLSBERG']:
        food = foods[sku]
        assert add(client, headers, batch, food, selections(food, '打包')).status_code == 201
    result = submit(client, headers, batch).json()
    assert len(result['print_jobs']) == 3
    with transaction() as db:
        items = [item for job in db.scalars(select(PrintJob)) for item in job.ticket['items']]
        assert len(items) == 6 and len({item['id'] for item in items}) == 6
        assert all('打包' in [entry['name'] for entry in item['modifiers']] for item in items)


def test_repeated_seed_does_not_duplicate_groups_or_reset_option_edits(client, headers):
    food = catalog(client, headers)['KOPI_O']
    identity = option(food, '浓度', 'Kao')['id']
    with transaction() as db:
        before = (db.scalar(select(func.count()).select_from(ModifierGroup)), db.scalar(select(func.count()).select_from(ModifierOption)))
        db.get(ModifierOption, identity).enabled = False
    seed(); seed()
    with transaction() as db:
        assert before == (db.scalar(select(func.count()).select_from(ModifierGroup)), db.scalar(select(func.count()).select_from(ModifierOption)))
        assert db.get(ModifierOption, identity).enabled is False
