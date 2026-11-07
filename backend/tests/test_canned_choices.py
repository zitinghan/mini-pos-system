from sqlalchemy import select
from app.database.db import transaction
from app.database.seed import seed
from app.models.entities import PrintJob, ModifierGroup
from app.printing.tickets import ticket_lines
from test_v11 import catalog, selections
from test_workflows import open_session, draft, add, submit


def test_all_seven_canned_choices_preserve_prices_and_print_selected_brand(client, headers):
    food = catalog(client, headers)['CANNED']
    group = next(group for group in food['groups'] if group['name'] == '品牌 / 口味')
    assert [entry['name'] for entry in group['options']] == ['Sprite','Coke','Fanta','100 PLUS','菊花茶','7UP','Passion Fruit']
    assert group['minimum'] == 0 and group['maximum'] == 1
    assert all(entry['price'] == 0 and not entry['is_default'] and entry['unit_price'] is None for entry in group['options'])
    batch = draft(client, headers, open_session(client, headers))
    for entry in group['options']:
        result = add(client, headers, batch, food, selections(food, '冰 ICED', entry['name']), 2)
        assert result.status_code == 201 and result.json()['line_total'] == 660
    legacy = add(client, headers, batch, food, selections(food, '热 HOT'))
    assert legacy.status_code == 201 and legacy.json()['unit_price'] == 300
    assert not any(entry['name'] in [option['name'] for option in legacy.json()['modifiers']] for entry in group['options'])
    both = selections(food, '冰 ICED') + [group['options'][0]['id'],group['options'][1]['id']]
    assert add(client, headers, batch, food, both).status_code == 422
    submit(client, headers, batch)
    with transaction() as db:
        ticket = db.scalar(select(PrintJob)).ticket
        assert all(entry['name'] in '\n'.join(text for text,_ in ticket_lines(ticket)) for entry in group['options'])
    seed(); seed()
    again = catalog(client, headers)['CANNED']
    assert len([section for section in again['groups'] if section['name'] == '品牌 / 口味']) == 1
    assert len(next(section for section in again['groups'] if section['name'] == '品牌 / 口味')['options']) == 7
