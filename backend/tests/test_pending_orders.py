from test_v11 import catalog
from test_workflows import open_session, draft, add, submit, key


def test_pending_draft_badge_is_shared_requires_real_items_and_does_not_book_table(client, headers):
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    token = client.post('/api/auth/login', json={'name':'staff','pin':'654321'}).json()['token']
    staff = {'Authorization':f'Bearer {token}'}
    def table():
        return client.get('/api/tables/5', headers=staff).json()
    assert not table()['ordering_in_progress'] and table()['status'] == 'AVAILABLE'
    food = catalog(client, headers)['WANTAN_MEE']
    item = add(client, headers, batch, food).json()
    assert table()['ordering_in_progress'] and table()['status'] == 'AVAILABLE'
    assert table()['total'] == 0 and table()['item_count'] == 0
    client.delete(f"/api/order-batches/{batch}/items/{item['id']}", headers=headers)
    assert not table()['ordering_in_progress']
    add(client, headers, batch, food)
    submit(client, headers, batch)
    assert not table()['ordering_in_progress'] and table()['status'] == 'OCCUPIED'
    extra = draft(client, staff, session)
    add(client, staff, extra, food)
    assert client.get('/api/tables/5', headers=headers).json()['ordering_in_progress']
    assert table()['total'] == 800 and table()['item_count'] == 1
    assert client.delete(f'/api/order-batches/{extra}', headers=staff).status_code == 200
    assert not table()['ordering_in_progress']
    result = client.post(f'/api/table-sessions/{session}/payments', headers=key(headers), json={
        'method':'QR','received':800,'expected_total':800})
    assert result.status_code == 200
    assert not table()['ordering_in_progress'] and table()['status'] == 'AVAILABLE'
