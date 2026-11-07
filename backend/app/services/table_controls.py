"""Audited unpaid cancellations and editable table/round instructions."""
import hashlib
import json
from fastapi import HTTPException
from sqlalchemy import select
from app.models.entities import OrderBatch, OrderItem, TableSession, Payment, AuditLog, PrintJob, RestaurantTable, now
from app.printing.stations import STATIONS
from app.services import orders


def replay(db, action, key, identity, data):
    payload = data.model_dump()
    if 'prepaid_method' in payload and 'prepaid_method' not in data.model_fields_set:
        payload.pop('prepaid_method')  # Preserve retries sent before payment-method labels existed.
    if 'prepaid_amount' in payload and 'prepaid_amount' not in data.model_fields_set:
        payload.pop('prepaid_amount')
    fingerprint = hashlib.sha256(json.dumps({'identity': identity, **payload}, sort_keys=True).encode()).hexdigest()
    previous = db.scalar(select(AuditLog).where(AuditLog.request_key == key))
    if previous:
        if previous.action != action or previous.details.get('fingerprint') != fingerprint:
            raise HTTPException(409, 'Idempotency key reused with different table action')
        return fingerprint, previous.details['result']
    return fingerprint, None


def editable_session(db, identity):
    session = orders.active_session(db, identity)
    if session.status == 'PAYMENT_PENDING':
        raise HTTPException(409, 'Checkout in progress; cashier must resume ordering first')
    if db.scalar(select(Payment.id).where(Payment.session_id == identity)):
        raise HTTPException(409, 'Paid orders cannot be cancelled or changed')
    return session


def audit(db, user, action, key, fingerprint, before):
    record = AuditLog(user_id=user['id'], action=action, request_key=key,
        details={'fingerprint': fingerprint, 'before': before})
    db.add(record); db.flush()
    return record


def finish(record, after, result):
    record.details = {**record.details, 'after': after, 'result': result}
    return result


def print_notices(db, session, record, items, order_type, batch=None, reason='', note_scope=None):
    jobs = []
    for station, _ in STATIONS:
        relevant = [item for item in items if item['printer_group'] == station]
        if not relevant:
            continue
        ticket = {'table': orders.require(db, RestaurantTable, session.table_id).name,
            'session_id': session.id, 'scope': 'BATCH' if batch else 'TABLE', 'station': station,
            'time': now(), 'order_type': order_type, 'change_ref': record.id,
            'table_notes': session.notes, 'notes': batch.notes if batch else '',
            'reason': reason, 'note_scope': note_scope, 'items': relevant if order_type in ('CANCEL', 'RESTORE') else []}
        if batch:
            ticket.update(batch_id=batch.id, prepaid_label=batch.prepaid_label, prepaid_method=batch.prepaid_method, prepaid_amount=batch.prepaid_amount)
        job = PrintJob(batch_id=batch.id if batch else None, session_id=session.id,
            change_id=record.id, routing_group=station, ticket=ticket)
        db.add(job); db.flush()
        jobs.append({'id': job.id, 'routing_group': station})
    return jobs


def cancel_item(db, batch_id, item_id, data, key, user):
    fingerprint, old = replay(db, 'CANCEL_ITEM', key, [batch_id, item_id], data)
    if old is not None: return old
    batch = orders.require(db, OrderBatch, batch_id)
    session = editable_session(db, batch.session_id)
    item = orders.require(db, OrderItem, item_id)
    if item.batch_id != batch_id:
        raise HTTPException(404, 'Item not in this batch')
    if item.status != batch.status or item.status not in ('DRAFT', 'SUBMITTED'):
        raise HTTPException(409, 'Item already cancelled or unavailable')
    if batch.status == 'DRAFT': orders.editable_batch(db, batch_id, user)
    if item.revision != data.expected_revision:
        raise HTTPException(409, 'Item changed; refresh before editing')
    reason = data.reason.strip()
    if not reason: raise HTTPException(422, 'Cancellation reason is required')
    before = orders.item_data(db, item)
    record = audit(db, user, 'CANCEL_ITEM', key, fingerprint, before)
    item.status, item.cancellation_reason = 'CANCELLED', reason
    item.revision += 1
    db.flush()
    jobs = print_notices(db, session, record, [before], 'CANCEL', batch, reason) if batch.status == 'SUBMITTED' else []
    after = orders.item_data(db, item)
    return finish(record, after, {**after, 'print_jobs': jobs, 'reason': reason})


def cancel_table(db, session_id, data, key, user):
    fingerprint, old = replay(db, 'CANCEL_TABLE', key, session_id, data)
    if old is not None: return old
    session = editable_session(db, session_id)
    current = orders.bill(db, session_id)
    if data.expected_change_token != current['change_token']:
        raise HTTPException(409, 'Table changed; refresh before cancelling')
    reason = data.reason.strip()
    if not reason: raise HTTPException(422, 'Cancellation reason is required')
    before = {**current, 'batches': orders.batches(db, session_id)}
    record = audit(db, user, 'CANCEL_TABLE', key, fingerprint, before)
    for batch in db.scalars(select(OrderBatch).where(OrderBatch.session_id == session_id)):
        if batch.status not in ('DRAFT', 'SUBMITTED'): continue
        for item in db.scalars(select(OrderItem).where(OrderItem.batch_id == batch.id, OrderItem.status.in_(['DRAFT', 'SUBMITTED']))):
            item.status, item.cancellation_reason = 'CANCELLED', reason
            item.revision += 1
        batch.status = 'CANCELLED'
    session.status, session.closed_at = 'CANCELLED', now()
    jobs = print_notices(db, session, record, current['items'], 'CANCEL', reason=reason)
    db.flush()
    result = {'session_id': session_id, 'status': 'CANCELLED', 'reason': reason,
        'cancelled_quantity': current['item_count'], 'print_jobs': jobs}
    return finish(record, result, result)


def table_notes(db, session_id, data, key, user):
    fingerprint, old = replay(db, 'TABLE_NOTES', key, session_id, data)
    if old is not None: return old
    session = editable_session(db, session_id)
    if session.metadata_revision != data.expected_revision:
        raise HTTPException(409, 'Remarks changed; refresh before saving')
    before = {'notes': session.notes, 'metadata_revision': session.metadata_revision}
    record = audit(db, user, 'TABLE_NOTES', key, fingerprint, before)
    changed = session.notes != data.notes.strip()
    if changed:
        session.notes = data.notes.strip()
        session.metadata_revision += 1
    current = orders.bill(db, session_id)
    jobs = print_notices(db, session, record, current['items'], 'NOTE', note_scope='TABLE') if changed else []
    result = {'notes': session.notes, 'metadata_revision': session.metadata_revision, 'print_jobs': jobs}
    return finish(record, result, result)


def batch_details(db, batch_id, data, key, user):
    fingerprint, old = replay(db, 'BATCH_DETAILS', key, batch_id, data)
    if old is not None: return old
    batch = orders.require(db, OrderBatch, batch_id)
    session = editable_session(db, batch.session_id)
    if batch.status == 'DRAFT': orders.editable_batch(db, batch_id, user)
    elif batch.status != 'SUBMITTED': raise HTTPException(409, 'Order already cancelled')
    if batch.info_revision != data.expected_revision:
        raise HTTPException(409, 'Remarks changed; refresh before saving')
    before = {'notes': batch.notes, 'prepaid_label': batch.prepaid_label, 'prepaid_method': batch.prepaid_method, 'prepaid_amount': batch.prepaid_amount, 'info_revision': batch.info_revision}
    record = audit(db, user, 'BATCH_DETAILS', key, fingerprint, before)
    method = data.prepaid_method if 'prepaid_method' in data.model_fields_set else batch.prepaid_method
    if not data.prepaid_label: method = None
    amount = batch.prepaid_amount
    if not data.prepaid_label:
        amount = None
    elif 'prepaid_amount' in data.model_fields_set and data.prepaid_amount is not None:
        amount = data.prepaid_amount
    elif not batch.prepaid_label:
        amount = sum(item.line_total for item in db.scalars(select(OrderItem).where(
            OrderItem.batch_id == batch.id, OrderItem.status == batch.status)))
    changed = (batch.notes != data.notes.strip() or batch.prepaid_label != data.prepaid_label
        or batch.prepaid_method != method or batch.prepaid_amount != amount)
    if changed:
        batch.notes, batch.prepaid_label = data.notes.strip(), data.prepaid_label
        batch.prepaid_method = method
        batch.prepaid_amount = amount
        batch.info_revision += 1
    items = [orders.item_data(db, item) for item in db.scalars(select(OrderItem).where(OrderItem.batch_id == batch.id, OrderItem.status == 'SUBMITTED'))]
    jobs = print_notices(db, session, record, items, 'NOTE', batch, note_scope='BATCH') if changed else []
    result = {'notes': batch.notes, 'prepaid_label': batch.prepaid_label, 'prepaid_method': batch.prepaid_method, 'prepaid_amount': batch.prepaid_amount, 'info_revision': batch.info_revision, 'print_jobs': jobs}
    return finish(record, result, result)
