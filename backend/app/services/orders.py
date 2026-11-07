import hashlib
import json
from fastapi import HTTPException
from sqlalchemy import select
from app.services.pricing import SelectionGroup, PriceValidationError, calculate_price
from app.services import promotions
from app.models.entities import (MenuItem, MenuCategory, ModifierGroup, ModifierOption, MenuItemModifierGroup,
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
    campaigns = promotions.active_promotions(db)
    for item in db.scalars(select(MenuItem).where(MenuItem.active == True).order_by(MenuItem.id)):
        promotion = promotions.for_sku(campaigns, item.sku)
        category = db.get(MenuCategory, item.category_id)
        groups = list(db.scalars(select(ModifierGroup).join(MenuItemModifierGroup, MenuItemModifierGroup.group_id == ModifierGroup.id).where(MenuItemModifierGroup.item_id == item.id).order_by(ModifierGroup.display_order)))
        result.append({'id': item.id, 'name': item.name, 'category_id': item.category_id,
            'base_price': promotion.unit_price if promotion else item.base_price, 'regular_base_price': item.base_price,
            'sold_out': item.sold_out, 'promotion': promotions.data(promotion) if promotion else None,
            'sku': item.sku, 'category_code': category.code or 'MAINS', 'category_name': category.name,
            'printer_group': category.printer_group, 'description': item.description,
            'complimentary': item.complimentary, 'verification_required': item.verification_required,
            'verification_note': item.verification_note,
            'groups': [{'id': g.id, 'name': g.name, 'minimum': g.minimum, 'maximum': g.maximum, 'required': g.minimum > 0,
                'options': [{'id': o.id, 'name': o.name, 'price': o.price,
                             'unit_price': promotion.unit_price if promotion and o.unit_price is not None else o.unit_price,
                             'regular_unit_price': o.unit_price, 'bottles': o.bottles,
                             'enabled': o.enabled, 'incompatible_with': o.incompatible_with, 'is_default': o.is_default}
                            for o in db.scalars(select(ModifierOption).where(ModifierOption.group_id == g.id).order_by(ModifierOption.display_order))]} for g in groups]})
    return result


def price_item(db, item_id, quantity, option_ids, *, campaigns=None):
    item = require(db, MenuItem, item_id)
    if not item.active:
        raise HTTPException(422, 'Item is unavailable')
    if item.sold_out:
        raise HTTPException(409, f'{item.name} 已售罄，请移除或改选其他项目。')
    groups = list(db.scalars(
        select(ModifierGroup)
        .join(MenuItemModifierGroup, MenuItemModifierGroup.group_id == ModifierGroup.id)
        .where(MenuItemModifierGroup.item_id == item.id)
    ))
    options = list(db.scalars(
        select(ModifierOption).where(ModifierOption.group_id.in_([g.id for g in groups]), ModifierOption.enabled == True).order_by(ModifierOption.display_order, ModifierOption.id)
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
    if any(set(option.incompatible_with) & set(option_ids) for option in selected):
        raise HTTPException(422, 'Incompatible modifier selections')
    variants = [option for option in selected if option.unit_price is not None]
    if len(variants) > 1:
        raise HTTPException(422, 'Choose only one price variant')
    unit = (variants[0].unit_price + sum(option.price for option in selected)) if variants else quote.unit_price
    promotion = promotions.for_sku(promotions.active_promotions(db) if campaigns is None else campaigns, item.sku)
    if promotion:
        unit = promotion.unit_price
    if unit < 0 or (unit == 0 and not item.complimentary):
        raise HTTPException(422, 'Only complimentary items may have a zero price')
    return item, selected, unit


def snapshot_item(db, item, source, options):
    category = db.get(MenuCategory, source.category_id)
    variant = next((option for option in options if option.unit_price is not None), None)
    item.sku, item.category_code, item.printer_group = source.sku, category.code or 'MAINS', category.printer_group
    item.description = source.description
    item.variant_name = variant.name if variant else None
    item.bottles_per_unit = variant.bottles if variant else 0
    item.physical_bottles = item.quantity * item.bottles_per_unit


def item_data(db, item):
    return {'id': item.id, 'name': item.name, 'quantity': item.quantity, 'base_price': item.base_price,
        'menu_item_id': item.menu_item_id,
        'unit_price': item.unit_price, 'line_total': item.line_total, 'status': item.status,
        'sku': item.sku, 'category_code': item.category_code, 'printer_group': item.printer_group,
        'description': item.description, 'variant_name': item.variant_name, 'bottles_per_unit': item.bottles_per_unit,
        'physical_bottles': item.physical_bottles, 'notes': item.notes,
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
        'opened_at': session.opened_at, 'first_order_at': session.first_order_at, 'paid_at': session.paid_at,
        'closed_at': session.closed_at, 'dining_duration_seconds': dining_duration(session),
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
    campaigns = promotions.active_promotions(db)
    for item in items:
        modifiers = list(db.scalars(select(OrderItemModifier).where(OrderItemModifier.item_id == item.id)))
        source, options, unit = price_item(db, item.menu_item_id, item.quantity, [m.option_id for m in modifiers], campaigns=campaigns)
        item.name, item.base_price, item.unit_price = source.name, source.base_price, unit
        item.line_total, item.status = unit * item.quantity, 'SUBMITTED'
        snapshot_item(db, item, source, options)
        for modifier in modifiers:
            option = next(o for o in options if o.id == modifier.option_id)
            modifier.name, modifier.price = option.name, option.price
    batch.status, batch.submission_key, batch.submitted_at = 'SUBMITTED', key, now()
    db.flush()
    session = require(db, TableSession, batch.session_id)
    order_type = 'ADD-ON' if session.first_order_at else 'NEW'
    if session.first_order_at is None:
        session.first_order_at = batch.submitted_at
    session.status = 'OCCUPIED'
    ticket = {'table': require(db, RestaurantTable, session.table_id).name, 'batch_id': batch.id,
        'time': batch.submitted_at, 'order_type': order_type, 'restaurant': '可可·南洋咖啡店',
        'items': [item_data(db, i) for i in items]}
    for station in ('KITCHEN', 'BEVERAGE'):
        station_items = [item for item in ticket['items'] if item['printer_group'] == station]
        if station_items:
            db.add(PrintJob(batch_id=batch.id, routing_group=station, ticket={**ticket, 'items': station_items}))
    db.flush()
    return submission_result(db, batch)


def submission_result(db, batch):
    jobs = list(db.scalars(select(PrintJob).where(PrintJob.batch_id == batch.id).order_by(PrintJob.id)))
    job = jobs[0]
    return {'batch_id': batch.id, 'status': batch.status, 'print_job_id': job.id, 'print_status': job.status,
        'print_jobs': [{'id': job.id, 'routing_group': job.routing_group, 'status': job.status} for job in jobs if not job.reprint],
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
    if not current['items']:
        raise HTTPException(422, 'Cannot pay an empty table')
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
    timestamp = now()
    payment.created_at = timestamp
    session.status, session.closed_at, session.paid_at = 'PAID', timestamp, timestamp
    db.add(AuditLog(user_id=user['id'], action='PAYMENT', details={'session_id': session_id, 'method': data.method, 'total': current['total']}))
    db.flush()
    # Receipt and print outbox commit with payment, never after a successful response.
    from app.services.receipts import queue_original
    queue_original(db, payment)
    return payment_data(payment)


def dining_duration(session):
    from datetime import datetime
    if session.status != 'PAID' or not session.first_order_at or not session.paid_at:
        return None
    try:
        first, paid = datetime.fromisoformat(session.first_order_at), datetime.fromisoformat(session.paid_at)
        if first.tzinfo is None or paid.tzinfo is None:
            return None
        seconds = (paid - first).total_seconds()
        return int(seconds) if seconds >= 0 else None
    except (ValueError, TypeError, OverflowError):
        return None
