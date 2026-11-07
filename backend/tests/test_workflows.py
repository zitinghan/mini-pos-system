from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from app.database.db import transaction
from app.models.entities import TableSession, PrintJob, Payment, User, AuthSession
from app.printing.worker import run_once, recover_stale
from app.schemas.requests import PrinterSettings
from app.core.config import OUTPUT_DIR


def key(headers, value=None):
    return {**headers, 'Idempotency-Key': value or str(uuid4())}


def menu(client, headers):
    return client.get('/api/menu', headers=headers).json()


def open_session(client, headers, table=5):
    response = client.post(f'/api/tables/{table}/open', headers=headers)
    assert response.status_code == 200, response.text
    return response.json()['session_id']


def draft(client, headers, session):
    response = client.post('/api/order-batches', headers=headers, json={'session_id': session})
    assert response.status_code == 201, response.text
    return response.json()['id']


def add(client, headers, batch, food, options=None, quantity=1):
    ids = options if options is not None else [o['id'] for g in food['groups'] for o in g['options'] if o['is_default']]
    return client.post(f'/api/order-batches/{batch}/items', headers=key(headers), json={'menu_item_id': food['id'], 'quantity': quantity, 'option_ids': ids})


def submit(client, headers, batch, identity=None):
    return client.post(f'/api/order-batches/{batch}/submit', headers=key(headers, identity))


@pytest.mark.parametrize('index,extra,expected', [(0,False,800),(0,True,1000),(1,False,800),(1,True,900),(2,False,800),(2,True,1000)])
def test_menu_pricing(client, headers, index, extra, expected):
    food = menu(client, headers)[index]
    required = [g for g in food['groups'] if g['minimum'] > 0]
    selected = [g['options'][-1 if extra and n == len(required)-1 else 0]['id'] for n,g in enumerate(required)]
    batch = draft(client, headers, open_session(client, headers))
    response = add(client, headers, batch, food, selected)
    assert response.status_code == 201
    assert response.json()['unit_price'] == expected
    assert submit(client, headers, batch).json()['total'] == expected


def test_acceptance_a_b_c_and_price_snapshot(client, headers):
    foods = menu(client, headers)
    session = open_session(client, headers)
    first = draft(client, headers, session)
    ids = [foods[0]['groups'][0]['options'][0]['id'], foods[0]['groups'][1]['options'][1]['id'], foods[0]['groups'][2]['options'][1]['id']]
    assert add(client, headers, first, foods[0], ids, 2).status_code == 201
    response = submit(client, headers, first)
    assert response.json()['total'] == 2000
    assert run_once()
    first_job = client.get('/api/print-jobs', headers=headers).json()[0]
    assert first_job['status'] == 'SENT'
    ticket = (OUTPUT_DIR / f"job-{first_job['id']}.txt").read_text(encoding='utf-8')
    assert '2 x 云吞面' in ticket and '辣' in ticket and '加面' in ticket
    assert 'RM' not in ticket
    second = draft(client, headers, session)
    ids = [foods[1]['groups'][0]['options'][0]['id'],foods[1]['groups'][1]['options'][1]['id']]
    assert add(client, headers, second, foods[1], ids).status_code == 201
    assert submit(client, headers, second).json()['total'] == 900
    assert run_once()
    second_job = client.get('/api/print-jobs', headers=headers).json()[0]
    ticket = (OUTPUT_DIR / f"job-{second_job['id']}.txt").read_text(encoding='utf-8')
    assert '面粉粿' in ticket and '2 x 云吞面' not in ticket
    assert client.patch('/api/menu/items/1', headers=headers, json={'price': 1500}).status_code == 200
    bill = client.get(f'/api/table-sessions/{session}/bill', headers=headers).json()
    assert bill['total'] == 2900 and len(bill['items']) == 2
    response = client.post(f'/api/table-sessions/{session}/payments', headers=key(headers), json={'method':'CASH','received':5000,'expected_total':2900})
    assert response.status_code == 200, response.text
    assert response.json()['change'] == 2100
    assert client.get('/api/tables/5', headers=headers).json()['status'] == 'AVAILABLE'
    assert client.get('/api/reports/daily-sales', headers=headers).json()['total'] == 2900
    history = client.get('/api/reports/transactions', headers=headers).json()
    assert history[0]['bill']['total'] == 2900
    assert open_session(client, headers) != session


def test_duplicate_submission_and_conflicting_key(client, headers):
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    assert add(client, headers, batch, menu(client, headers)[0]).status_code == 201
    identity = str(uuid4())
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: submit(client, headers, batch, identity), range(4)))
    assert all(r.status_code == 200 for r in results)
    with transaction() as db:
        assert db.scalar(select(func.count()).select_from(PrintJob)) == 1
    other = draft(client, headers, session)
    assert submit(client, headers, other, identity).status_code == 409


def test_concurrent_open_and_database_constraint(client, headers):
    with ThreadPoolExecutor(max_workers=5) as pool:
        identities = list(pool.map(lambda _: open_session(client, headers), range(5)))
    assert len(set(identities)) == 1
    with pytest.raises(IntegrityError):
        with transaction() as db:
            db.add(TableSession(table_id=5, status='PAYMENT_PENDING'))


def test_invalid_modifiers_and_draft_not_billed(client, headers):
    foods = menu(client, headers)
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    assert add(client, headers, batch, foods[0], []).status_code == 422
    ids = [g['options'][0]['id'] for g in foods[0]['groups']]
    assert add(client, headers, batch, foods[0], ids+[ids[0]]).status_code == 422
    assert add(client, headers, batch, foods[0], ids+[foods[1]['groups'][0]['options'][0]['id']]).status_code == 422
    assert add(client, headers, batch, foods[0]).status_code == 201
    assert client.get(f'/api/table-sessions/{session}/bill', headers=headers).json()['total'] == 0
    assert client.get('/api/print-jobs', headers=headers).json() == []


def test_insufficient_cash_draft_guard_and_concurrent_payment(client, headers):
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    add(client, headers, batch, menu(client, headers)[0])
    submit(client, headers, batch)
    endpoint = f'/api/table-sessions/{session}/payments'
    data = {'method':'CASH','received':700,'expected_total':800}
    assert client.post(endpoint, headers=key(headers), json=data).status_code == 422
    data['received'] = 1000
    other = draft(client, headers, session)
    assert client.post(endpoint, headers=key(headers), json=data).status_code == 409
    data['discard_drafts'] = True
    identity = str(uuid4())
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: client.post(endpoint, headers=key(headers, identity), json=data), range(4)))
    assert all(r.status_code == 200 for r in results)
    assert len({r.json()['id'] for r in results}) == 1
    changed = {**data, 'received': 2000}
    assert client.post(endpoint, headers=key(headers,identity), json=changed).status_code == 409
    assert client.post(endpoint, headers=key(headers), json=data).status_code == 409
    with transaction() as db:
        assert db.scalar(select(func.count()).select_from(Payment)) == 1
    assert client.get(f'/api/table-sessions/{session}/orders', headers=headers).json()[-1]['status'] == 'CANCELLED'


@pytest.mark.parametrize('simulation,status',[('connection_failure','FAILED'),('timeout','UNKNOWN'),('uncertain','UNKNOWN')])
def test_printer_failures_and_manual_reprint(client, headers, simulation, status):
    settings = PrinterSettings(simulation=simulation).model_dump()
    assert client.put('/api/printers/config',headers=headers,json=settings).status_code == 200
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    add(client, headers, batch, menu(client, headers)[0])
    result = submit(client, headers, batch).json()
    assert run_once()
    job_id = result['print_job_id']
    assert client.get(f'/api/print-jobs/{job_id}', headers=headers).json()['status'] == status
    assert client.get(f'/api/table-sessions/{session}/bill', headers=headers).json()['total'] == 800
    assert not run_once()  # No automatic resend, especially after uncertain delivery.
    settings['simulation'] = 'success'
    client.put('/api/printers/config',headers=headers,json=settings)
    retry = client.post(f'/api/print-jobs/{job_id}/retry',headers=key(headers))
    assert retry.status_code == 201
    assert client.post(f'/api/print-jobs/{job_id}/retry',headers=key(headers)).status_code == 409
    assert run_once()
    ticket = (OUTPUT_DIR / f"job-{retry.json()['id']}.txt").read_text(encoding='utf-8')
    assert ticket.startswith('REPRINT / 重印')
    assert client.get(f'/api/print-jobs/{job_id}', headers=headers).json()['status'] == status


def test_concurrent_workers_and_stale_claim(client, headers):
    client.post('/api/printers/test-print', headers=headers)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: run_once(),range(4)))
    assert results.count(True) == 3
    with transaction() as db:
        jobs = list(db.scalars(select(PrintJob)))
        assert len(jobs) == 3 and all(job.attempts == 1 and job.status == 'SENT' for job in jobs)
        job = jobs[0]
        job_id = job.id
        assert job.attempts == 1
        job.status, job.claimed_at = 'SENDING', '2020-01-01T00:00:00+00:00'
    recover_stale()
    assert client.get(f'/api/print-jobs/{job_id}',headers=headers).json()['status'] == 'UNKNOWN'
    assert not run_once()


def test_auth_roles_logout_and_hashed_secrets(client, headers):
    assert client.get('/api/menu').status_code == 401
    response = client.post('/api/auth/login', json={'name':'staff','pin':'654321'})
    staff = {'Authorization': 'Bearer '+response.json()['token']}
    for path in ['/api/reports/daily-sales','/api/reports/transactions','/api/printers/config','/api/users']:
        assert client.get(path,headers=staff).status_code == 403
    assert client.patch('/api/menu/items/1',headers=staff,json={'price':1}).status_code == 403
    assert client.post('/api/auth/setup',json={'name':'x','pin':'123456','setup_token':'bad'}).status_code == 403
    with transaction() as db:
        assert db.scalar(select(User).where(User.name=='staff')).pin_hash != '654321'
        assert db.scalar(select(AuthSession)).token_hash != response.json()['token']
    assert client.post('/api/auth/logout',headers=staff).status_code == 200
    assert client.get('/api/menu',headers=staff).status_code == 401


def test_idempotent_draft_add(client, headers):
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    food = menu(client, headers)[0]
    data = {'menu_item_id':food['id'],'quantity':1,'option_ids':[g['options'][0]['id'] for g in food['groups']]}
    request_headers = key(headers)
    first = client.post(f'/api/order-batches/{batch}/items',headers=request_headers,json=data)
    second = client.post(f'/api/order-batches/{batch}/items',headers=request_headers,json=data)
    assert first.json()['id'] == second.json()['id']
    assert client.post(f'/api/order-batches/{batch}/items',headers=request_headers,json={**data,'quantity':2}).status_code == 409


def test_setup_once_and_session_expiry(client, headers):
    assert client.post('/api/auth/setup',json={'name':'owner','pin':'777777','setup_token':'test-only-setup-token-not-a-pin'}).status_code == 409
    with transaction() as db:
        for session in db.scalars(select(AuthSession)):
            session.expires_at = '2020-01-01T00:00:00+00:00'
    assert client.get('/api/menu',headers=headers).status_code == 401


def test_login_lockout(client):
    for _ in range(5):
        assert client.post('/api/auth/login', json={'name':'cashier','pin':'999999'}).status_code == 401
    assert client.post('/api/auth/login', json={'name':'cashier','pin':'123456'}).status_code == 429


def test_checkout_blocks_new_orders_and_empty_release(client, headers):
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    add(client, headers, batch, menu(client, headers)[0])
    assert client.post(f'/api/table-sessions/{session}/checkout', headers=headers).status_code == 200
    assert submit(client, headers, batch).status_code == 409
    assert client.post('/api/order-batches', headers=headers, json={'session_id':session}).status_code == 409
    assert client.post(f'/api/table-sessions/{session}/resume', headers=headers).status_code == 200
    assert client.post(f'/api/table-sessions/{session}/close-empty', headers=headers).status_code == 200
    assert client.get('/api/tables/5', headers=headers).json()['status'] == 'AVAILABLE'


def test_stale_bill_and_manual_qr_record(client, headers):
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    add(client, headers, batch, menu(client, headers)[0])
    submit(client, headers, batch)
    endpoint = f'/api/table-sessions/{session}/payments'
    assert client.post(endpoint,headers=key(headers),json={'method':'QR','received':0,'expected_total':900}).status_code == 409
    result = client.post(endpoint,headers=key(headers),json={'method':'QR','received':0,'expected_total':800})
    assert result.status_code == 200
    assert result.json()['received'] == 800 and result.json()['change'] == 0
    assert client.get('/api/reports/daily-sales',headers=headers).json()['methods']['QR'] == 800


def test_submission_and_outbox_roll_back_together(client, headers, monkeypatch):
    from app.services import orders as order_service
    from app.models.entities import OrderBatch
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    add(client, headers, batch, menu(client, headers)[0])

    def failing_job(**kwargs):
        raise RuntimeError('Injected outbox failure')

    monkeypatch.setattr(order_service, 'PrintJob', failing_job)
    with pytest.raises(RuntimeError, match='Injected outbox failure'):
        with transaction() as db:
            user = db.scalar(select(User).where(User.name == 'cashier'))
            order_service.submit(db, batch, str(uuid4()), {'id':user.id, 'role':'ADMIN'})
    with transaction() as db:
        assert db.get(OrderBatch, batch).status == 'DRAFT'
        assert db.scalar(select(func.count()).select_from(PrintJob)) == 0
    assert client.get(f'/api/table-sessions/{session}/bill', headers=headers).json()['total'] == 0


def test_daily_report_uses_kuala_lumpur_midnight(client, headers):
    times = ['2026-11-02T15:59:59+00:00', '2026-11-02T16:00:00+00:00', '2026-11-03T15:59:59+00:00', '2026-11-03T16:00:00+00:00']
    with transaction() as db:
        user = db.scalar(select(User).where(User.name == 'cashier'))
        for timestamp in times:
            session = TableSession(table_id=5, status='PAID', closed_at=timestamp)
            db.add(session)
            db.flush()
            db.add(Payment(session_id=session.id, user_id=user.id, idempotency_key=str(uuid4()), request_hash='test',
                method='CASH', total=800, received=800, change=0, created_at=timestamp))
    result = client.get('/api/reports/daily-sales?day=2026-11-03', headers=headers).json()
    assert result['transactions'] == 2 and result['total'] == 1600


def test_staff_cannot_read_completed_financial_history(client, headers):
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    add(client, headers, batch, menu(client, headers)[0])
    submit(client, headers, batch)
    client.post(f'/api/table-sessions/{session}/payments',headers=key(headers),json={'method':'CASH','received':800,'expected_total':800})
    token = client.post('/api/auth/login',json={'name':'staff','pin':'654321'}).json()['token']
    staff = {'Authorization':'Bearer '+token}
    assert client.get(f'/api/table-sessions/{session}/bill',headers=staff).status_code == 403
    assert client.get(f'/api/table-sessions/{session}/orders',headers=staff).status_code == 403


def test_lost_reprint_response_cannot_send_a_second_ticket(client, headers):
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    add(client, headers, batch, menu(client, headers)[0])
    original = submit(client, headers, batch).json()['print_job_id']
    assert run_once()
    endpoint = f'/api/print-jobs/{original}/retry'
    retry_headers = key(headers)
    first = client.post(endpoint, headers=retry_headers)
    assert first.status_code == 201
    assert run_once()
    # Even after the reprint has finished, repeating an ambiguous HTTP request is a replay.
    replay = client.post(endpoint, headers=retry_headers)
    assert replay.status_code == 201
    assert replay.json()['id'] == first.json()['id']
    assert replay.json()['status'] == 'SENT'
    assert not run_once()
    with transaction() as db:
        assert db.scalar(select(func.count()).select_from(PrintJob)) == 2


def test_unicode_setup_token_rejected_without_server_error(client):
    result = client.post('/api/auth/setup', json={'name':'owner','pin':'928461','setup_token':'invalid-令牌'})
    assert result.status_code == 403


def test_zero_base_price_rejected_but_zero_modifier_price_allowed(client, headers):
    assert client.patch('/api/menu/items/1', headers=headers, json={'price':0}).status_code == 422
    assert client.patch('/api/menu/options/1', headers=headers, json={'price':0}).status_code == 200
