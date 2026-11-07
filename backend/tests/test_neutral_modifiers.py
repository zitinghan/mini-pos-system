from copy import deepcopy
from app.printing.tickets import ticket_lines
from app.printing.modifiers import visible_modifiers
from test_v11 import catalog, selections
from test_workflows import open_session, draft, add, submit


def test_neutral_defaults_are_omitted_from_kitchen_receipt_and_correction_without_mutating_snapshots():
    item = {'id': 1, 'name': '面粉粿', 'quantity': 1, 'unit_price': 800, 'line_total': 800,
        'printer_group': 'KITCHEN', 'notes': '请确认不加蛋', 'modifiers': [
            {'name': '汤', 'price': 0}, {'name': '不加蛋', 'price': 0},
            {'name': '普通', 'price': 0}, {'name': '堂食', 'price': 0}]}
    base = {'restaurant': '可可·南洋咖啡店', 'table': 'T05', 'batch_id': 1,
        'time': '2026-11-07T10:00:00+00:00', 'items': [item]}
    receipt = {**base, 'kind': 'RECEIPT', 'receipt_number': 'R000001', 'total': 800,
        'method': 'QR', 'received': 800, 'change': 0}
    correction = {**base, 'order_type': 'UPDATE', 'change_ref': 2, 'previous_items': [item]}
    for ticket in [base, receipt, correction]:
        original = deepcopy(ticket)
        for reprint in [False, True]:
            lines = [text.strip() for text, _ in ticket_lines(ticket, reprint)]
            assert not {'不加蛋', '普通', '堂食'} & set(lines)
            assert '汤' in lines and '备注 请确认不加蛋' in lines
        assert ticket == original
    changed = {**base, 'order_type': 'UPDATE', 'change_ref': 3, 'previous_items': [{**item, 'modifiers': [
        {'name': '加蛋', 'price': 100}, {'name': '加面', 'price': 200}, {'name': '打包', 'price': 0}]}]}
    lines = {text.strip() for text, _ in ticket_lines(changed)}
    assert {'不加蛋', '普通', '堂食'} <= lines  # Explicit reversals must be clear to the stall.
    assert [entry['name'] for entry in visible_modifiers([
        {'name': '普通', 'price': 100}, {'name': '加蛋', 'price': 100}, {'name': '加面', 'price': 200},
        {'name': '打包', 'price': 0}, {'name': '不辣', 'price': 0}, {'name': '冰 ICED', 'price': 0},
        {'name': 'Kao（加浓）', 'price': 0}])] == ['普通', '加蛋', '加面', '打包', '不辣', '冰 ICED', 'Kao（加浓）']


def test_no_egg_remains_in_order_snapshot_for_prices_and_editing(client, headers):
    food = catalog(client, headers)['MEE_HOON_KUEH']
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    assert add(client, headers, batch, food, selections(food)).json()['unit_price'] == 800
    assert submit(client, headers, batch).json()['total'] == 800
    line = client.get(f'/api/table-sessions/{session}/bill', headers=headers).json()['items'][0]
    assert '不加蛋' in [entry['name'] for entry in line['modifiers']]
    assert '不加蛋' not in [entry['name'] for entry in visible_modifiers(line['modifiers'])]
    assert line['unit_price'] == 800 and line['line_total'] == 800
