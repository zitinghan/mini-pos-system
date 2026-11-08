from sqlalchemy import select
from app.database.db import transaction
from app.models.entities import OrderBatch, PrintJob
from app.services import orders
from app.printing.tickets import ticket_lines
from test_workflows import open_session, draft, add, submit, key, menu


def test_noon_rollover_retry_and_continuous_receipts(client, headers, monkeypatch):
    food = menu(client, headers)[0]
    numbers, ids, receipt_ids = [], [], []
    timestamps = ['2026-11-08T03:59:59+00:00', '2026-11-08T04:00:00+00:00',
                  '2026-11-08T16:00:00+00:00', '2026-11-09T04:00:00+00:00']
    for index, timestamp in enumerate(timestamps):
        session = open_session(client, headers, table=5+index)
        batch = draft(client, headers, session)
        assert add(client, headers, batch, food).status_code == 201
        monkeypatch.setattr(orders, 'now', lambda: timestamp)
        submit_key = f'numbering-submit-{index}'
        response = submit(client, headers, batch, submit_key)
        assert response.status_code == 200, response.text
        data = response.json()
        numbers.append(data['order_number']); ids.append(data['batch_id'])
        assert submit(client, headers, batch, submit_key).json()['order_number'] == data['order_number']
        with transaction() as db:
            jobs = list(db.scalars(select(PrintJob).where(PrintJob.batch_id == batch)))
            assert all(job.ticket['order_number'] == data['order_number'] for job in jobs)
            assert f"订单 #{data['order_number']}" in [text for text, _ in ticket_lines(jobs[0].ticket)]
        paid = client.post(f'/api/table-sessions/{session}/payments', headers=key(headers),
            json={'method':'OTHER', 'received':data['total'], 'expected_total':data['total']})
        assert paid.status_code == 200, paid.text
        payment = paid.json()
        receipt = client.get(f"/api/payments/{payment['id']}/receipt", headers=headers).json()
        assert receipt['receipt_number'] == f"R{payment['id']:06d}"
        receipt_ids.append(payment['id'])
    assert numbers == [1,1,2,1]  # Midnight is not a reset; noon is.
    assert ids == sorted(set(ids))
    assert receipt_ids == sorted(set(receipt_ids))


def test_existing_numbers_continue_and_cancelled_numbers_are_not_reused(client, headers, monkeypatch):
    food = menu(client, headers)[0]
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    assert add(client, headers, batch, food).status_code == 201
    monkeypatch.setattr(orders, 'now', lambda: '2026-11-08T05:00:00+00:00')
    with transaction() as db:
        old = db.get(OrderBatch, batch)
        old.business_day, old.order_number = '2026-11-08', 400
    assert submit(client, headers, batch).json()['order_number'] == 400
    with transaction() as db:
        db.get(OrderBatch, batch).status = 'CANCELLED'
    next_batch = draft(client, headers, session)
    assert add(client, headers, next_batch, food).status_code == 201
    assert submit(client, headers, next_batch).json()['order_number'] == 401
