"""Acknowledge long dining sessions without changing ordering/payment state."""
from datetime import datetime
from fastapi import HTTPException
from app.models.entities import AuditLog, now
from app.services import orders


def is_due(session):
    if not session or session.status not in ('OCCUPIED', 'PAYMENT_PENDING') or not session.first_order_at:
        return False
    try:
        first = datetime.fromisoformat(session.first_order_at)
        return first.utcoffset() is not None and (datetime.fromisoformat(now()) - first).total_seconds() > 45 * 60
    except (TypeError, ValueError):
        return False


def acknowledge(db, session_id, user):
    session = orders.active_session(db, session_id)
    if not is_due(session):
        raise HTTPException(409, '此桌尚未超过 45 分钟，请刷新桌台。')
    if not session.wait_alert_acknowledged_at:
        session.wait_alert_acknowledged_at = now()
        db.add(AuditLog(user_id=user['id'], action='ACKNOWLEDGE_TABLE_WAIT', details={
            'session_id': session.id, 'acknowledged_at': session.wait_alert_acknowledged_at}))
    return {'session_id': session.id, 'wait_alert_acknowledged_at': session.wait_alert_acknowledged_at}
