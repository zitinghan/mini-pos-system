import secrets
from datetime import datetime, timedelta, timezone, date, time
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from app.core import config
from app.core.security import current_user, admin, hash_pin, verify_pin, token_hash
from app.database.db import transaction
from app.models.entities import (User, AuthSession, LoginAttempt, RestaurantTable, TableSession, MenuItem, ModifierOption,
    OrderBatch, OrderItem, OrderItemModifier, Payment, PrintJob, PrinterConfiguration, AuditLog, now)
from app.schemas.requests import Setup, Credentials, NewUser, NewBatch, NewItem, PriceUpdate, Pay, PrinterSettings
from app.services import orders

router = APIRouter(prefix='/api')


def idempotency_key(value: str = Header(alias='Idempotency-Key', min_length=8, max_length=128)):
    return value


def job_data(job):
    return {k: getattr(job, k) for k in ('id', 'batch_id', 'status', 'attempts', 'reprint', 'error', 'preview', 'created_at', 'updated_at')}


@router.get('/auth/setup-status')
def setup_status():
    with transaction() as db:
        return {'setup_required': db.scalar(select(User.id).limit(1)) is None}


@router.post('/auth/setup', status_code=201)
def setup(data: Setup):
    if not config.SETUP_TOKEN or not secrets.compare_digest(data.setup_token.encode(), config.SETUP_TOKEN.encode()):
        raise HTTPException(403, 'Use the setup token configured on the server')
    with transaction() as db:
        if db.scalar(select(User.id).limit(1)):
            raise HTTPException(409, 'Administrator already configured')
        user = User(name=data.name, pin_hash=hash_pin(data.pin), role='ADMIN')
        db.add(user)
        db.flush()
        return {'id': user.id, 'name': user.name, 'role': user.role}


@router.post('/auth/login')
def login(data: Credentials, request: Request):
    failure = False
    with transaction() as db:
        # Persistent global attempt budget also throttles attempts for unknown user names.
        identity = token_hash(request.client.host if request.client else 'local')
        attempt = db.get(LoginAttempt, identity)
        timestamp = now()
        if not attempt:
            attempt = LoginAttempt(key=identity, count=0, expires_at=timestamp)
            db.add(attempt)
        if attempt.expires_at <= timestamp:
            attempt.count = 0
            attempt.expires_at = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        if attempt.count >= 20:
            raise HTTPException(429, 'Too many login attempts; wait five minutes')
        user = db.scalar(select(User).where(User.name == data.name))
        if user and user.locked_until and user.locked_until > timestamp:
            raise HTTPException(429, 'Account temporarily locked; wait five minutes')
        if not user or not verify_pin(data.pin, user.pin_hash):
            attempt.count += 1
            if user:
                user.failed_attempts += 1
                if user.failed_attempts >= 5:
                    user.locked_until = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
                    user.failed_attempts = 0
            failure = True
        else:
            user.failed_attempts, user.locked_until = 0, None
            attempt.count = 0
            token = secrets.token_urlsafe(32)
            expires = (datetime.now(timezone.utc) + timedelta(hours=config.SESSION_HOURS)).isoformat()
            db.add(AuthSession(user_id=user.id, token_hash=token_hash(token), expires_at=expires))
            result = {'token': token, 'expires_at': expires, 'user': {'id': user.id, 'name': user.name, 'role': user.role}}
    if failure:
        raise HTTPException(401, 'Incorrect name or PIN')
    return result


@router.get('/auth/me')
def me(user=Depends(current_user)):
    return user


@router.post('/auth/logout')
def logout(request: Request, user=Depends(current_user)):
    with transaction() as db:
        session = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash(request.headers.get('Authorization', '').removeprefix('Bearer '))))
        if session:
            db.delete(session)
    return {'ok': True}


@router.get('/users')
def users(user=Depends(admin)):
    with transaction() as db:
        return [{'id': u.id, 'name': u.name, 'role': u.role} for u in db.scalars(select(User))]


@router.post('/users', status_code=201)
def create_user(data: NewUser, user=Depends(admin)):
    with transaction() as db:
        if db.scalar(select(User.id).where(User.name == data.name)):
            raise HTTPException(409, 'User name already exists')
        created = User(name=data.name, role=data.role, pin_hash=hash_pin(data.pin))
        db.add(created)
        db.flush()
        db.add(AuditLog(user_id=user['id'], action='CREATE_USER', details={'user_id': created.id, 'role': created.role}))
        return {'id': created.id, 'name': created.name, 'role': created.role}


@router.get('/tables')
def tables(user=Depends(current_user)):
    with transaction() as db:
        result = []
        for table in db.scalars(select(RestaurantTable).order_by(RestaurantTable.id)):
            session = db.scalar(select(TableSession).where(TableSession.table_id == table.id, TableSession.status.in_(['OCCUPIED', 'PAYMENT_PENDING'])))
            current = orders.bill(db, session.id) if session else {'total': 0, 'item_count': 0}
            result.append({'id': table.id, 'name': table.name, 'status': session.status if session else 'AVAILABLE',
                'session_id': session.id if session else None, 'opened_at': session.created_at if session else None,
                'total': current['total'], 'item_count': current['item_count']})
        return result


@router.get('/tables/{table_id}')
def table_details(table_id: int, user=Depends(current_user)):
    found = next((t for t in tables(user) if t['id'] == table_id), None)
    if not found:
        raise HTTPException(404, 'Table not found')
    return found


@router.get('/tables/{table_id}/active-session')
def table_session(table_id: int, user=Depends(current_user)):
    return table_details(table_id, user)


@router.post('/tables/{table_id}/open')
def open_table(table_id: int, user=Depends(current_user)):
    with transaction() as db:
        orders.require(db, RestaurantTable, table_id)
        session = db.scalar(select(TableSession).where(TableSession.table_id == table_id, TableSession.status.in_(['OCCUPIED', 'PAYMENT_PENDING'])))
        if not session:
            session = TableSession(table_id=table_id)
            db.add(session)
            db.flush()
        return {'session_id': session.id, 'status': session.status}


@router.get('/menu')
@router.get('/menu/items')
def menu(user=Depends(current_user)):
    with transaction() as db:
        return orders.menu(db)


@router.patch('/menu/items/{item_id}')
def update_price(item_id: int, data: PriceUpdate, user=Depends(admin)):
    if data.price == 0:
        raise HTTPException(422, 'Base price must be positive; modifier surcharges may be zero')
    with transaction() as db:
        item = orders.require(db, MenuItem, item_id)
        old = item.base_price
        item.base_price = data.price
        db.add(AuditLog(user_id=user['id'], action='MENU_PRICE', details={'item_id': item_id, 'old': old, 'new': data.price}))
        return {'id': item.id, 'base_price': item.base_price}


@router.patch('/menu/options/{option_id}')
def update_option(option_id: int, data: PriceUpdate, user=Depends(admin)):
    with transaction() as db:
        option = orders.require(db, ModifierOption, option_id)
        old = option.price
        option.price = data.price
        db.add(AuditLog(user_id=user['id'], action='MODIFIER_PRICE', details={'option_id': option_id, 'old': old, 'new': data.price}))
        return {'id': option.id, 'price': option.price}


@router.post('/order-batches', status_code=201)
def create_batch(data: NewBatch, user=Depends(current_user)):
    with transaction() as db:
        session = orders.active_session(db, data.session_id)
        if session.status == 'PAYMENT_PENDING':
            raise HTTPException(409, 'Checkout in progress; cashier must resume ordering first')
        # Reuse this user's active draft, making reconnects safe.
        batch = db.scalar(select(OrderBatch).where(OrderBatch.session_id == data.session_id, OrderBatch.user_id == user['id'], OrderBatch.status == 'DRAFT'))
        if not batch:
            batch = OrderBatch(session_id=data.session_id, user_id=user['id'])
            db.add(batch)
            db.flush()
        return {'id': batch.id, 'status': batch.status}


@router.post('/order-batches/{identity}/items', status_code=201)
def add_item(identity: int, data: NewItem, key: str = Depends(idempotency_key), user=Depends(current_user)):
    with transaction() as db:
        batch = orders.editable_batch(db, identity, user)
        if orders.active_session(db, batch.session_id).status == 'PAYMENT_PENDING':
            raise HTTPException(409, 'Checkout in progress')
        # Store idempotent draft mutations in the audit log; key and payload are checked.
        details = {'key': key, 'batch_id': identity, **data.model_dump()}
        existing = db.scalar(select(AuditLog).where(AuditLog.action == 'ADD_ITEM', AuditLog.request_key == key))
        if existing:
            expected = {k: v for k, v in existing.details.items() if k != 'item_id'}
            if expected != details:
                raise HTTPException(409, 'Idempotency key reused with different draft item')
            return orders.item_data(db, db.get(OrderItem, existing.details['item_id']))
        source, options, unit = orders.price_item(db, data.menu_item_id, data.quantity, data.option_ids)
        item = OrderItem(batch_id=identity, menu_item_id=source.id, name=source.name, quantity=data.quantity,
            base_price=source.base_price, unit_price=unit, line_total=unit * data.quantity)
        db.add(item)
        db.flush()
        for option in options:
            db.add(OrderItemModifier(item_id=item.id, option_id=option.id, name=option.name, price=option.price))
        db.add(AuditLog(user_id=user['id'], action='ADD_ITEM', request_key=key, details={**details, 'item_id': item.id}))
        db.flush()
        return orders.item_data(db, item)


@router.delete('/order-batches/{identity}/items/{item_id}')
def cancel_draft_item(identity: int, item_id: int, user=Depends(current_user)):
    with transaction() as db:
        orders.editable_batch(db, identity, user)
        item = orders.require(db, OrderItem, item_id)
        if item.batch_id != identity:
            raise HTTPException(404, 'Item not in this batch')
        item.status = 'CANCELLED'
        return {'ok': True}


@router.delete('/order-batches/{identity}')
def cancel_draft(identity: int, user=Depends(current_user)):
    with transaction() as db:
        batch = orders.editable_batch(db, identity, user)
        batch.status = 'CANCELLED'
        for item in db.scalars(select(OrderItem).where(OrderItem.batch_id == identity)):
            item.status = 'CANCELLED'
        return {'ok': True}


@router.post('/order-batches/{identity}/submit')
def submit(identity: int, key: str = Depends(idempotency_key), user=Depends(current_user)):
    with transaction() as db:
        return orders.submit(db, identity, key, user)


@router.get('/table-sessions/{identity}/orders')
def session_orders(identity: int, user=Depends(current_user)):
    with transaction() as db:
        session = orders.require(db, TableSession, identity)
        if session.status in ('PAID', 'CANCELLED') and user['role'] != 'ADMIN':
            raise HTTPException(403, 'Cashier/admin permission required')
        return orders.batches(db, identity)


@router.get('/table-sessions/{identity}/bill')
def session_bill(identity: int, user=Depends(current_user)):
    with transaction() as db:
        session = orders.require(db, TableSession, identity)
        if session.status in ('PAID', 'CANCELLED') and user['role'] != 'ADMIN':
            raise HTTPException(403, 'Cashier/admin permission required')
        return orders.bill(db, identity)


@router.post('/table-sessions/{identity}/checkout')
def checkout(identity: int, user=Depends(admin)):
    with transaction() as db:
        session = orders.active_session(db, identity)
        session.status = 'PAYMENT_PENDING'
        return orders.bill(db, identity)


@router.post('/table-sessions/{identity}/resume')
def resume(identity: int, user=Depends(admin)):
    with transaction() as db:
        orders.active_session(db, identity).status = 'OCCUPIED'
        return {'ok': True}


@router.post('/table-sessions/{identity}/payments')
def payment(identity: int, data: Pay, key: str = Depends(idempotency_key), user=Depends(admin)):
    with transaction() as db:
        return orders.pay(db, identity, data, key, user)


@router.get('/print-jobs')
def print_jobs(user=Depends(current_user)):
    with transaction() as db:
        return [job_data(job) for job in db.scalars(select(PrintJob).order_by(PrintJob.id.desc()).limit(100))]


@router.get('/print-jobs/{identity}')
def print_job(identity: int, user=Depends(current_user)):
    with transaction() as db:
        return job_data(orders.require(db, PrintJob, identity))


@router.get('/print-jobs/{identity}/preview')
def preview(identity: int, user=Depends(current_user)):
    with transaction() as db:
        job = orders.require(db, PrintJob, identity)
        if not job.preview:
            raise HTTPException(404, 'Preview not generated yet')
        path = config.OUTPUT_DIR / job.preview
    if not path.exists():
        raise HTTPException(404, 'Preview file is unavailable')
    return FileResponse(path, media_type='image/png')


@router.post('/print-jobs/{identity}/retry', status_code=201)
def retry(identity: int, key: str = Depends(idempotency_key), user=Depends(admin)):
    with transaction() as db:
        source = orders.require(db, PrintJob, identity)
        previous = db.scalar(select(AuditLog).where(AuditLog.request_key == key))
        if previous:
            if previous.action != 'REPRINT' or previous.details['source_job_id'] != identity:
                raise HTTPException(409, 'Idempotency key reused for another print request')
            return job_data(orders.require(db, PrintJob, previous.details['new_job_id']))
        if source.status in ('PENDING', 'SENDING'):
            raise HTTPException(409, 'Job is already queued or sending')
        # New history row; never erase the outcome of a previous attempt.
        descendants = list(db.scalars(select(PrintJob).where(PrintJob.batch_id == source.batch_id))) if source.batch_id else []
        if any(j.status in ('PENDING', 'SENDING') for j in descendants):
            raise HTTPException(409, 'Another attempt for this batch is already queued')
        job = PrintJob(batch_id=source.batch_id, ticket=source.ticket, reprint=True, attempts=source.attempts)
        db.add(job)
        db.flush()
        db.add(AuditLog(user_id=user['id'], action='REPRINT', request_key=key, details={'source_job_id': identity, 'new_job_id': job.id, 'previous_status': source.status}))
        return job_data(job)


@router.get('/printers/config')
def printer_config(user=Depends(admin)):
    with transaction() as db:
        return db.get(PrinterConfiguration, 1).config


@router.put('/printers/config')
def update_printer(data: PrinterSettings, user=Depends(admin)):
    import ipaddress
    import codecs
    if data.mode == 'network':
        try:
            address = ipaddress.ip_address(data.host)
            if not address.is_private or address.is_loopback or address.is_link_local or address.is_unspecified:
                raise ValueError()
        except ValueError:
            raise HTTPException(422, 'Printer must use a private LAN IP address')
    try:
        codecs.lookup(data.encoding)
    except LookupError:
        raise HTTPException(422, 'Unknown text encoding')
    with transaction() as db:
        db.get(PrinterConfiguration, 1).config = data.model_dump()
        db.add(AuditLog(user_id=user['id'], action='PRINTER_CONFIG', details=data.model_dump()))
    return data


@router.post('/printers/test-print', status_code=201)
def test_print(user=Depends(admin)):
    with transaction() as db:
        job = PrintJob(ticket={'table': 'TEST', 'time': now(), 'items': [{'name': '打印测试', 'quantity': 1, 'modifiers': [{'name': '黑酱 / 不辣 / 加面'}]}]})
        db.add(job)
        db.flush()
        db.add(AuditLog(user_id=user['id'], action='TEST_PRINT', details={'job_id': job.id}))
        return job_data(job)


def day_payments(db, day):
    zone = ZoneInfo('Asia/Kuala_Lumpur')
    start = datetime.combine(day, time.min, zone).astimezone(timezone.utc).isoformat()
    end = datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(timezone.utc).isoformat()
    return list(db.scalars(select(Payment).where(Payment.created_at >= start, Payment.created_at < end).order_by(Payment.id.desc())))


@router.get('/reports/daily-sales')
def daily_sales(day: date | None = None, user=Depends(admin)):
    day = day or datetime.now(ZoneInfo('Asia/Kuala_Lumpur')).date()
    with transaction() as db:
        payments = day_payments(db, day)
        return {'date': day.isoformat(), 'timezone': 'Asia/Kuala_Lumpur', 'total': sum(p.total for p in payments),
            'transactions': len(payments), 'methods': {method: sum(p.total for p in payments if p.method == method) for method in ('CASH', 'QR', 'OTHER')}}


@router.get('/reports/transactions')
def transactions(day: date | None = None, user=Depends(admin)):
    with transaction() as db:
        payments = day_payments(db, day) if day else list(db.scalars(select(Payment).order_by(Payment.id.desc()).limit(200)))
        return [{**orders.payment_data(p), 'bill': orders.bill(db, p.session_id)} for p in payments]


@router.get('/audit-logs')
def audit_logs(user=Depends(admin)):
    with transaction() as db:
        return [{'id': a.id, 'user_id': a.user_id, 'action': a.action, 'details': a.details, 'created_at': a.created_at} for a in db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(200))]


@router.post('/table-sessions/{identity}/close-empty')
def close_empty(identity: int, user=Depends(admin)):
    with transaction() as db:
        session = orders.active_session(db, identity)
        if orders.bill(db, identity)['item_count']:
            raise HTTPException(409, 'Submitted items must be paid before closing')
        for draft in db.scalars(select(OrderBatch).where(OrderBatch.session_id == identity, OrderBatch.status == 'DRAFT')):
            draft.status = 'CANCELLED'
            for item in db.scalars(select(OrderItem).where(OrderItem.batch_id == draft.id)):
                item.status = 'CANCELLED'
        session.status, session.closed_at = 'CANCELLED', now()
        db.add(AuditLog(user_id=user['id'], action='CLOSE_EMPTY', details={'session_id': identity}))
        return {'ok': True}
