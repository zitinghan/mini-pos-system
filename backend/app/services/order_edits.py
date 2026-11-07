"""Atomic unpaid item edits with optimistic revisions and immutable correction tickets."""
import hashlib
import json
from fastapi import HTTPException
from sqlalchemy import select
from app.models.entities import (OrderBatch, OrderItem, OrderItemModifier, ModifierOption,
    MenuItemModifierGroup, MenuItem, PrintJob, AuditLog, RestaurantTable, now)
from app.services import orders


def priced_selection_unchanged(db, before, selected):
    options = list(db.scalars(select(ModifierOption).join(MenuItemModifierGroup,
        MenuItemModifierGroup.group_id == ModifierOption.group_id)
        .where(MenuItemModifierGroup.item_id == before['menu_item_id'])))
    old_prices = {entry['option_id']: entry['price'] for entry in before['modifiers']}
    priced_groups = {entry.group_id for entry in options
        if entry.unit_price is not None or entry.price > 0 or old_prices.get(entry.id, 0) > 0}
    priced_ids = {entry.id for entry in options if entry.group_id in priced_groups
        and not (entry.is_default and entry.price == 0 and entry.unit_price is None and old_prices.get(entry.id, 0) == 0)}
    return set(old_prices) & priced_ids == set(selected) & priced_ids


def edit(db, batch_id, item_id, data, key, user):
    fingerprint = hashlib.sha256(json.dumps({'batch_id': batch_id, 'item_id': item_id,
        **data.model_dump()}, sort_keys=True).encode()).hexdigest()
    replay = db.scalar(select(AuditLog).where(AuditLog.request_key == key))
    if replay:
        if replay.action != 'EDIT_ITEM' or replay.details.get('fingerprint') != fingerprint:
            raise HTTPException(409, 'Idempotency key reused with different item edit')
        return replay.details['result']
    batch = orders.require(db, OrderBatch, batch_id)
    session = orders.active_session(db, batch.session_id)
    if session.status == 'PAYMENT_PENDING':
        raise HTTPException(409, 'Checkout in progress; cashier must resume ordering first')
    item = orders.require(db, OrderItem, item_id)
    if item.batch_id != batch_id:
        raise HTTPException(404, 'Item not in this batch')
    if item.status != batch.status or batch.status not in ('DRAFT', 'SUBMITTED'):
        raise HTTPException(409, 'Item cannot be edited')
    if batch.status == 'DRAFT':
        orders.editable_batch(db, batch_id, user)
    if item.revision != data.expected_revision:
        raise HTTPException(409, 'Item changed; refresh before editing')
    if data.menu_item_id != item.menu_item_id:
        raise HTTPException(422, 'Edit this item options or quantity; add another dish separately')
    if len(data.option_ids) != len(set(data.option_ids)):
        raise HTTPException(422, 'Duplicate modifier selection')
    before = orders.item_data(db, item)
    old_ids = {entry['option_id'] for entry in before['modifiers']}
    same_choices = old_ids == set(data.option_ids)
    frozen_price = batch.status == 'SUBMITTED' and priced_selection_unchanged(db, before, data.option_ids)
    source = orders.require(db, MenuItem, item.menu_item_id)
    if batch.status == 'SUBMITTED' and same_choices:
        if data.quantity > item.quantity and (source.sold_out or not source.active):
            raise HTTPException(409, 'Item is unavailable; only reduce quantity or edit notes')
        unit = item.unit_price
        modifiers = before['modifiers']
        options = None
    else:
        source, options, quoted = orders.price_item(db, item.menu_item_id, data.quantity, data.option_ids,
            allow_unavailable=frozen_price and data.quantity <= item.quantity)
        unit = item.unit_price if frozen_price else quoted
        old_prices = {entry['option_id']: entry['price'] for entry in before['modifiers']}
        modifiers = [{'option_id': entry.id, 'name': entry.name,
            'price': old_prices.get(entry.id, entry.price) if frozen_price else entry.price} for entry in options]
    if unit != data.expected_unit_price:
        raise HTTPException(409, 'Item price changed; refresh before editing')
    notes = data.notes.strip()
    changed = not same_choices or data.quantity != item.quantity or notes != item.notes or unit != item.unit_price
    if changed:
        item.quantity, item.notes = data.quantity, notes
        item.unit_price, item.line_total = unit, unit * data.quantity
        if batch.status == 'DRAFT':
            item.name, item.base_price = source.name, source.base_price
            orders.snapshot_item(db, item, source, options)
        elif not frozen_price and options is not None:
            item.base_price = source.base_price
            variant = next((entry for entry in options if entry.unit_price is not None), None)
            item.variant_name = variant.name if variant else None
            item.bottles_per_unit = variant.bottles if variant else 0
        item.physical_bottles = item.quantity * item.bottles_per_unit
        for entry in list(db.scalars(select(OrderItemModifier).where(OrderItemModifier.item_id == item.id))):
            db.delete(entry)
        for entry in modifiers:
            db.add(OrderItemModifier(item_id=item.id, option_id=entry['option_id'], name=entry['name'], price=entry['price']))
        item.revision += 1
        db.flush()
    after = orders.item_data(db, item)
    audit = AuditLog(user_id=user['id'], action='EDIT_ITEM', request_key=key,
        details={'fingerprint': fingerprint, 'before': before, 'after': after, 'result': after})
    db.add(audit)
    db.flush()
    if changed and batch.status == 'SUBMITTED':
        job = PrintJob(batch_id=batch.id, session_id=session.id, change_id=audit.id, routing_group=before['printer_group'], ticket={
            'table': orders.require(db, RestaurantTable, session.table_id).name, 'batch_id': batch.id,
            'time': now(), 'order_type': 'UPDATE', 'notes': batch.notes, 'table_notes': session.notes, 'prepaid_label': batch.prepaid_label,
            'change_ref': audit.id, 'previous_items': [before], 'items': [after]})
        db.add(job)
        db.flush()
        after = {**after, 'change_print_job_id': job.id}
        audit.details = {**audit.details, 'result': after}
    return after
