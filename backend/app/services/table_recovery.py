"""Audited reversal of accidental unpaid table closures."""
from fastapi import HTTPException
from sqlalchemy import select, or_
from app.models.entities import TableSession, OrderBatch, OrderItem, OrderItemModifier, Payment, PaymentReversal, PrintJob, AuditLog, RestaurantTable, now
from app.services import orders, table_controls


def closure_record(db, session_id):
    return db.scalar(select(AuditLog).where(AuditLog.action.in_(['CANCEL_TABLE', 'CLOSE_EMPTY']), or_(
        AuditLog.details['before']['session_id'].as_integer() == session_id,
        AuditLog.details['session_id'].as_integer() == session_id)).order_by(AuditLog.id.desc()).limit(1))


def active_conflict(db, session):
    return db.scalar(select(TableSession).where(TableSession.table_id == session.table_id,
        TableSession.id != session.id, TableSession.status.in_(['OCCUPIED', 'PAYMENT_PENDING'])))


def empty_shell(db, session):
    return not session.first_order_at and not session.notes and not db.scalar(select(OrderBatch.id)
        .where(OrderBatch.session_id == session.id).limit(1)) and not db.scalar(select(Payment.id).where(Payment.session_id == session.id))


def preview(db, session):
    current = orders.bill(db, session.id)
    closure = closure_record(db, session.id)
    before = closure.details.get('before', {}) if closure else {}
    batches = before.get('batches', [])
    recoverable = [line for batch in batches if batch['status'] in ('DRAFT', 'SUBMITTED')
        for line in batch['items'] if line['status'] == batch['status']]
    known = bool(closure) and (bool(before) or not any(batch['items'] for batch in orders.batches(db, session.id)))
    conflict = active_conflict(db, session)
    blocked = '此桌已有新的客人或草稿，请先处理当前桌台。' if conflict and not empty_shell(db, conflict) else ''
    if not known:
        blocked = '这笔历史记录缺少关闭前的快照，无法自动恢复餐点。'
    if db.scalar(select(Payment.id).where(Payment.session_id == session.id)):
        blocked = '此桌已有收款记录，不能作为未付款取消单恢复。'
    payment = db.scalar(select(Payment).where(Payment.session_id == session.id))
    if session.status == 'PAID':
        recoverable = current['items']
        blocked = '此桌缺少付款或餐点记录，无法自动恢复。' if not payment or not recoverable else ''
        if conflict and not empty_shell(db, conflict): blocked = '此桌已有新的客人或草稿，请先处理当前桌台。'
        if payment and db.scalar(select(PaymentReversal.id).where(PaymentReversal.payment_id == payment.id)):
            blocked = '这笔收款已撤销并恢复，请使用恢复后的桌台。'
        if payment and db.scalar(select(PrintJob.id).where(PrintJob.payment_id == payment.id, PrintJob.status == 'SENDING')):
            blocked = '收银收据正在发送，请等待发送结束后再恢复。'
    return {'session_id': session.id, 'table': orders.require(db, RestaurantTable, session.table_id).name,
        'status': session.status, 'closed_at': session.closed_at, 'first_order_at': session.first_order_at,
        'items': recoverable, 'total': sum(line['line_total'] for line in recoverable), 'table_notes': session.notes,
        'expected_change_token': current['change_token'], 'can_restore': not blocked, 'blocked_reason': blocked,
        'closure_id': closure.id if closure else None, 'payment_total': payment.total if payment else None}


def recent_closed(db):
    return [preview(db, session) for session in db.scalars(select(TableSession)
        .where(TableSession.status.in_(['CANCELLED', 'PAID'])).order_by(TableSession.closed_at.desc(), TableSession.id.desc()).limit(100))]


def restore(db, session_id, data, key, user):
    session = orders.require(db, TableSession, session_id)
    if session.status == 'PAID': return restore_paid(db, session, data, key, user)
    return restore_cancelled(db, session_id, data, key, user)


def restore_paid(db, session, data, key, user):
    fingerprint, old = table_controls.replay(db, 'RESTORE_TABLE', key, session.id, data)
    if old is not None: return old
    details = preview(db, session)
    if details['expected_change_token'] != data.expected_change_token:
        raise HTTPException(409, '桌台记录已变动，请重新核对后恢复。')
    if not details['can_restore']: raise HTTPException(409, details['blocked_reason'])
    reason = data.reason.strip()
    if not reason: raise HTTPException(422, '请填写恢复原因。')
    payment = db.scalar(select(Payment).where(Payment.session_id == session.id))
    before = {**orders.bill(db, session.id), 'payment': orders.payment_data(payment)}
    audit = table_controls.audit(db, user, 'RESTORE_TABLE', key, fingerprint, before)
    conflict = active_conflict(db, session)
    retired = None
    if conflict:
        retired = conflict.id
        conflict.status, conflict.closed_at = 'CANCELLED', now()
        db.flush()
    restored = TableSession(table_id=session.table_id, opened_at=session.opened_at, first_order_at=session.first_order_at,
        notes=session.notes, wait_alert_acknowledged_at=session.wait_alert_acknowledged_at)
    db.add(restored); db.flush()
    mapping = []
    for old_batch in db.scalars(select(OrderBatch).where(OrderBatch.session_id == session.id, OrderBatch.status == 'SUBMITTED').order_by(OrderBatch.id)):
        old_items = list(db.scalars(select(OrderItem).where(OrderItem.batch_id == old_batch.id, OrderItem.status == 'SUBMITTED').order_by(OrderItem.id)))
        if not old_items: continue
        batch = OrderBatch(session_id=restored.id, user_id=old_batch.user_id, status='SUBMITTED', submitted_at=old_batch.submitted_at,
            notes=old_batch.notes, prepaid_label=False)
        db.add(batch); db.flush()
        for old_item in old_items:
            fields = ('menu_item_id','name','quantity','base_price','unit_price','line_total','sku','category_code','printer_group',
                'description','variant_name','bottles_per_unit','physical_bottles','notes')
            item = OrderItem(batch_id=batch.id, status='SUBMITTED', **{field:getattr(old_item,field) for field in fields})
            db.add(item); db.flush()
            for modifier in db.scalars(select(OrderItemModifier).where(OrderItemModifier.item_id == old_item.id).order_by(OrderItemModifier.id)):
                db.add(OrderItemModifier(item_id=item.id, option_id=modifier.option_id, name=modifier.name, price=modifier.price))
            mapping.append({'original_item_id':old_item.id,'restored_item_id':item.id})
    reversal = PaymentReversal(payment_id=payment.id, restored_session_id=restored.id, user_id=user['id'], reason=reason)
    db.add(reversal); db.flush()
    stopped_jobs = []
    for job in db.scalars(select(PrintJob).where(PrintJob.payment_id == payment.id, PrintJob.status == 'PENDING')):
        job.status, job.error = 'FAILED', '收款已撤销，收据未发送。'
        stopped_jobs.append(job.id)
    result = {'session_id':restored.id,'status':'OCCUPIED','print_jobs':[], 'voided_payment_id':payment.id,
        'voided_amount':payment.total,'reversal_id':reversal.id,'retired_empty_session_id':retired,
        'total':orders.bill(db, restored.id)['total']}
    return table_controls.finish(audit, {**result,'item_mapping':mapping,'stopped_receipt_jobs':stopped_jobs,'reason':reason}, result)


def restore_cancelled(db, session_id, data, key, user):
    fingerprint, old = table_controls.replay(db, 'RESTORE_TABLE', key, session_id, data)
    if old is not None: return old
    session = orders.require(db, TableSession, session_id)
    if session.status != 'CANCELLED':
        raise HTTPException(409, '此桌已恢复或当前不能恢复，请刷新查看。')
    current = orders.bill(db, session_id)
    if current['change_token'] != data.expected_change_token:
        raise HTTPException(409, '桌台记录已变动，请重新核对后恢复。')
    details = preview(db, session)
    if not details['can_restore']:
        raise HTTPException(409, details['blocked_reason'])
    reason = data.reason.strip()
    if not reason: raise HTTPException(422, '请填写恢复原因。')
    closure = closure_record(db, session_id)
    snapshot = closure.details.get('before', {})
    before = {**current, 'closed_at': session.closed_at, 'batches': orders.batches(db, session_id), 'closure_id': closure.id}
    audit = table_controls.audit(db, user, 'RESTORE_TABLE', key, fingerprint, before)
    conflict = active_conflict(db, session)
    retired = None
    if conflict:
        retired = conflict.id
        conflict.status, conflict.closed_at = 'CANCELLED', now()
        db.flush()  # Release the active-table uniqueness slot before reopening the original.
    restored_items = []
    for old_batch in snapshot.get('batches', []):
        if old_batch['status'] not in ('DRAFT', 'SUBMITTED'): continue
        batch = orders.require(db, OrderBatch, old_batch['id'])
        if batch.session_id != session_id or batch.status != 'CANCELLED':
            raise HTTPException(409, '订单记录已变动，无法恢复。')
        batch.status = old_batch['status']
        batch.info_revision += 1
        for old_item in old_batch['items']:
            if old_item['status'] != old_batch['status']: continue
            item = orders.require(db, OrderItem, old_item['id'])
            if item.batch_id != batch.id or item.status != 'CANCELLED':
                raise HTTPException(409, '餐点记录已变动，无法恢复。')
            item.status = old_item['status']
            item.cancellation_reason = old_item.get('cancellation_reason', '')
            item.revision += 1
            if item.status == 'SUBMITTED': restored_items.append(orders.item_data(db, item))
    session.status, session.closed_at = 'OCCUPIED', None
    session.metadata_revision += 1
    db.flush()
    jobs = table_controls.print_notices(db, session, audit, restored_items, 'RESTORE', reason=reason)
    result = {'session_id': session_id, 'status': session.status, 'print_jobs': jobs,
        'retired_empty_session_id': retired, 'total': orders.bill(db, session_id)['total']}
    return table_controls.finish(audit, {**result, 'reason': reason}, result)
