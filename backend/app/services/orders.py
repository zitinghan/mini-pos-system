import hashlib
import json
from fastapi import HTTPException
from sqlalchemy import select
from app.services.pricing import SelectionGroup, PriceValidationError, calculate_price
from app.models.entities import (MenuItem, ModifierGroup, ModifierOption, MenuItemModifierGroup,
    TableSession, RestaurantTable, OrderBatch, OrderItem, OrderItemModifier, PrintJob, Payment, AuditLog, now)


def require(db, model, identity):
    value = db.get(model, identity)
    if value is None:
        raise HTTPException(404, f'{model.__name__} not found')
    return value


def active_session(db, identity):
    session = require(db, TableSession, identity)
    if session.status not in ('OCCUPIED', 'PAYMENT_PENDING'):
        raise HTTPException(409, 'Table session is closed')
    return session


def menu(db):
    result = []
    for item in db.scalars(select(MenuItem).where(MenuItem.active == True).order_by(MenuItem.id)):
        groups = list(db.scalars(select(ModifierGroup).join(MenuItemModifierGroup, MenuItemModifierGroup.group_id == ModifierGroup.id).where(MenuItemModifierGroup.item_id == item.id).order_by(ModifierGroup.display_order)))
        result.append({'id': item.id, 'name': item.name, 'category_id': item.category_id, 'base_price': item.base_price,
            'groups': [{'id': g.id, 'name': g.name, 'minimum': g.minimum, 'maximum': g.maximum, 'required': g.minimum > 0,
                'options': [{'id': o.id, 'name': o.name, 'price': o.price, 'is_default': o.is_default} for o in db.scalars(select(ModifierOption).where(ModifierOption.group_id == g.id).order_by(ModifierOption.display_order))]} for g in groups]})
    return result


def price_item(db, item_id, quantity, option_ids):
    item = require(db, MenuItem, item_id)
    if not item.active:
        raise HTTPException(422, 'Item is unavailable')
    groups = list(db.scalars(
        select(ModifierGroup)
        .join(MenuItemModifierGroup, MenuItemModifierGroup.group_id == ModifierGroup.id)
        .where(MenuItemModifierGroup.item_id == item.id)
    ))
    options = list(db.scalars(
        select(ModifierOption).where(ModifierOption.group_id.in_([g.id for g in groups]))
    ))
    selection_groups = [
        SelectionGroup(
            id=group.id,
            name=group.name,
            minimum=group.minimum,
            maximum=group.maximum,
            option_prices={o.id: o.price for o in options if o.group_id == group.id},
        )
        for group in groups
    ]
    try:
        quote = calculate_price(item.base_price, quantity, selection_groups, option_ids)
    except PriceValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    selected = [option for option in options if option.id in option_ids]
    return item, selected, quote.unit_price


def item_data(db, item):
    return {'id': item.id, 'name': item.name, 'quantity': item.quantity, 'base_price': item.base_price,
        'unit_price': item.unit_price, 'line_total': item.line_total, 'status': item.status,
        'modifiers': [{'name': m.name, 'price': m.price, 'option_id': m.option_id} for m in db.scalars(select(OrderItemModifier).where(OrderItemModifier.item_id == item.id))]}


def batches(db, session_id):
    return [{'id': b.id, 'status': b.status, 'created_at': b.created_at, 'submitted_at': b.submitted_at,
             'user_id': b.user_id,
             'items': [item_data(db, i) for i in db.scalars(select(OrderItem).where(OrderItem.batch_id == b.id).order_by(OrderItem.id))]}
        for b in db.scalars(select(OrderBatch).where(OrderBatch.session_id == session_id).order_by(OrderBatch.id))]


def bill(db, session_id):
    session = require(db, TableSession, session_id)
    items = list(db.scalars(select(OrderItem).join(OrderBatch).where(OrderBatch.session_id == session_id, OrderBatch.status == 'SUBMITTED', OrderItem.status == 'SUBMITTED')))
    return {'session_id': session.id, 'table': require(db, RestaurantTable, session.table_id).name,
        'status': session.status, 'items': [item_data(db, i) for i in items],
        'total': sum(i.line_total for i in items), 'item_count': sum(i.quantity for i in items),
        'has_drafts': db.scalar(select(OrderBatch.id).where(OrderBatch.session_id == session_id, OrderBatch.status == 'DRAFT').limit(1)) is not None}


def editable_batch(db, identity, user):
    batch = require(db, OrderBatch, identity)
    active_session(db, batch.session_id)
    if batch.status != 'DRAFT':
        raise HTTPException(409, 'Batch is no longer a draft')
    if batch.user_id != user['id'] and user['role'] != 'ADMIN':
        raise HTTPException(403, 'This draft belongs to another staff member')
    return batch


def submit(db, identity, key, user):
    batch = require(db, OrderBatch, identity)
    if batch.user_id != user['id'] and user['role'] != 'ADMIN':
        raise HTTPException(403, 'This draft belongs to another staff member')
    previous = db.scalar(select(OrderBatch).where(OrderBatch.submission_key == key))
    if previous:
        if previous.id != identity:
            raise HTTPException(409, 'Idempotency key already used for another batch')
        return submission_result(db, previous)
    editable_batch(db, identity, user)
    if active_session(db, batch.session_id).status == 'PAYMENT_PENDING':
        raise HTTPException(409, 'Checkout in progress; cashier must resume ordering first')
    items = list(db.scalars(select(OrderItem).where(OrderItem.batch_id == identity, OrderItem.status == 'DRAFT')))
    if not items:
        raise HTTPException(422, 'Cannot submit an empty order')
    # Revalidate current menu and snapshot final authoritative prices at submission.
    for item in items:
        modifiers = list(db.scalars(select(OrderItemModifier).where(OrderItemModifier.item_id == item.id)))
        source, options, unit = price_item(db, item.menu_item_id, item.quantity, [m.option_id for m in modifiers])
        item.name, item.base_price, item.unit_price = source.name, source.base_price, unit
        item.line_total, item.status = unit * item.quantity, 'SUBMITTED'
        for modifier in modifiers:
            option = next(o for o in options if o.id == modifier.option_id)
            modifier.name, modifier.price = option.name, option.price
    batch.status, batch.submission_key, batch.submitted_at = 'SUBMITTED', key, now()
    db.flush()
    session = require(db, TableSession, batch.session_id)
    session.status = 'OCCUPIED'
    ticket = {'table': require(db, RestaurantTable, session.table_id).name, 'batch_id': batch.id,
        'time': batch.submitted_at, 'items': [item_data(db, i) for i in items]}
    db.add(PrintJob(batch_id=batch.id, ticket=ticket))
    db.flush()
    return submission_result(db, batch)


def submission_result(db, batch):
    job = db.scalar(select(PrintJob).where(PrintJob.batch_id == batch.id).order_by(PrintJob.id))
    return {'batch_id': batch.id, 'status': batch.status, 'print_job_id': job.id, 'print_status': job.status,
        'total': sum(i.line_total for i in db.scalars(select(OrderItem).where(OrderItem.batch_id == batch.id, OrderItem.status == 'SUBMITTED')))}


def payment_data(payment):
    return {k: getattr(payment, k) for k in ('id', 'session_id', 'method', 'total', 'received', 'change', 'created_at')}


def pay(db, session_id, data, key, user):
    fingerprint = hashlib.sha256(json.dumps({'session_id': session_id, **data.model_dump()}, sort_keys=True).encode()).hexdigest()
    previous = db.scalar(select(Payment).where(Payment.idempotency_key == key))
    if previous:
        if previous.request_hash != fingerprint:
            raise HTTPException(409, 'Idempotency key reused with different payment details')
        return payment_data(previous)
    session = active_session(db, session_id)
    current = bill(db, session_id)
    if current['total'] != data.expected_total:
        raise HTTPException(409, 'Bill changed; refresh before collecting payment')
    if current['has_drafts'] and not data.discard_drafts:
        raise HTTPException(409, 'Unsubmitted drafts exist; submit or explicitly discard them')
    if data.method == 'CASH' and data.received < current['total']:
        raise HTTPException(422, 'Insufficient cash')
    if current['has_drafts']:
        for draft in db.scalars(select(OrderBatch).where(OrderBatch.session_id == session_id, OrderBatch.status == 'DRAFT')):
            draft.status = 'CANCELLED'
            for item in db.scalars(select(OrderItem).where(OrderItem.batch_id == draft.id)):
                item.status = 'CANCELLED'
    received = data.received if data.method == 'CASH' else current['total']
    payment = Payment(session_id=session_id, user_id=user['id'], idempotency_key=key, request_hash=fingerprint,
        method=data.method, total=current['total'], received=received, change=received-current['total'])
    db.add(payment)
    session.status, session.closed_at = 'PAID', now()
    db.add(AuditLog(user_id=user['id'], action='PAYMENT', details={'session_id': session_id, 'method': data.method, 'total': current['total']}))
    db.flush()
    return payment_data(payment)
