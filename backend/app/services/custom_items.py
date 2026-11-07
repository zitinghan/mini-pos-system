"""Audited, open-priced order snapshots using a single hidden catalog reference."""
import hashlib
import json
from fastapi import HTTPException
from sqlalchemy import select
from app.database.seed import CUSTOM_ITEM_SKU
from app.models.entities import MenuItem, OrderBatch, OrderItem, AuditLog
from app.schemas.requests import CustomItem
from app.services import orders, order_edits


def identity(data, batch_id, item_id=None):
    return hashlib.sha256(json.dumps({'batch_id': batch_id, 'item_id': item_id,
        **data.model_dump()}, sort_keys=True).encode()).hexdigest()


def replay(db, key, action, fingerprint):
    old = db.scalar(select(AuditLog).where(AuditLog.request_key == key))
    if old:
        if old.action != action or old.details.get('fingerprint') != fingerprint:
            raise HTTPException(409, 'Idempotency key reused with different custom item')
        return old.details['result']


def apply(item, data):
    item.name, item.quantity = data.name, data.quantity
    item.base_price = item.unit_price = data.unit_price
    item.line_total = data.unit_price * data.quantity
    item.category_code, item.printer_group = data.category_code, data.printer_group
    item.notes, item.description = data.notes, '打包' if data.takeaway else ''
    item.bottles_per_unit = data.bottles_per_unit
    item.physical_bottles = data.quantity * data.bottles_per_unit


def validate_snapshot(db, item):
    source = orders.require(db, MenuItem, item.menu_item_id)
    if source.sku != CUSTOM_ITEM_SKU:
        raise HTTPException(422, 'Invalid custom item reference')
    CustomItem(name=item.name, quantity=item.quantity, unit_price=item.unit_price,
        category_code=item.category_code, printer_group=item.printer_group,
        notes=item.notes, takeaway=item.description == '打包', bottles_per_unit=item.bottles_per_unit)


def add(db, batch_id, data, key, user):
    fingerprint = identity(data, batch_id)
    batch = orders.require(db, OrderBatch, batch_id)
    if batch.user_id != user['id'] and user['role'] != 'ADMIN':
        raise HTTPException(403, 'This draft belongs to another staff member')
    old = replay(db, key, 'ADD_CUSTOM_ITEM', fingerprint)
    if old is not None: return old
    orders.editable_batch(db, batch_id, user)
    if orders.active_session(db, batch.session_id).status == 'PAYMENT_PENDING':
        raise HTTPException(409, 'Checkout in progress; cashier must resume ordering first')
    source = db.scalar(select(MenuItem).where(MenuItem.sku == CUSTOM_ITEM_SKU))
    if source is None:
        raise HTTPException(503, '请重启服务器以完成自定义餐点设置')
    item = OrderItem(batch_id=batch.id, menu_item_id=source.id, sku=CUSTOM_ITEM_SKU, status='DRAFT')
    apply(item, data)
    db.add(item); db.flush()
    result = orders.item_data(db, item)
    db.add(AuditLog(user_id=user['id'], action='ADD_CUSTOM_ITEM', request_key=key,
        details={'fingerprint': fingerprint, 'after': result, 'result': result}))
    return result


def edit(db, batch_id, item_id, data, key, user):
    fingerprint = identity(data, batch_id, item_id)
    batch = orders.require(db, OrderBatch, batch_id)
    if batch.status == 'DRAFT' and batch.user_id != user['id'] and user['role'] != 'ADMIN':
        raise HTTPException(403, 'This draft belongs to another staff member')
    old = replay(db, key, 'EDIT_ITEM', fingerprint)
    if old is not None: return old
    session = orders.active_session(db, batch.session_id)
    if session.status == 'PAYMENT_PENDING':
        raise HTTPException(409, 'Checkout in progress; cashier must resume ordering first')
    item = orders.require(db, OrderItem, item_id)
    if item.batch_id != batch_id:
        raise HTTPException(404, 'Item not in this batch')
    if item.sku != CUSTOM_ITEM_SKU:
        raise HTTPException(422, 'Only custom items can use this editor')
    if batch.status not in ('DRAFT', 'SUBMITTED') or item.status != batch.status:
        raise HTTPException(409, 'Item cannot be edited')
    if item.revision != data.expected_revision:
        raise HTTPException(409, 'Item changed; refresh before editing')
    if batch.status == 'SUBMITTED' and (data.printer_group != item.printer_group or data.category_code != item.category_code):
        raise HTTPException(422, '已送档口后如需更改分类或档口，请先取消此项再重新加入')
    before = orders.item_data(db, item)
    apply(item, data)
    after = orders.item_data(db, item)
    changed = before != after
    if changed:
        item.revision += 1
        db.flush()
        after = orders.item_data(db, item)
    return order_edits.record_change(db, batch, session, before, after, changed, fingerprint, key, user)
