import secrets
from datetime import datetime, timedelta, timezone, date, time
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from fastapi.responses import FileResponse
from sqlalchemy import select, func, and_, or_
from app.core import config
from app.core.security import current_user, admin, hash_pin, verify_pin, token_hash
from app.database.db import transaction
from app.models.entities import (User, AuthSession, LoginAttempt, RestaurantTable, TableSession, MenuItem, ModifierOption,
    OrderBatch, OrderItem, OrderItemModifier, MenuItemModifierGroup, ModifierGroup, MenuPromotion, Payment, PrintJob, PrinterConfiguration, AuditLog, now)
from app.schemas.requests import Setup, Credentials, NewUser, NewBatch, NewItem, EditItem, SubmitBatch, PriceUpdate, Pay, PrinterSettings, OptionConfiguration, AvailabilityUpdate, PromotionUpdate
from app.services import orders
from app.services import promotions
from app.services import receipts
from app.services import order_edits
from app.printing.jobs import job_data
from app.printing.stations import STATIONS

router = APIRouter(prefix='/api')


def idempotency_key(value: str = Header(alias='Idempotency-Key', min_length=8, max_length=128)):
    return value


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
            visible_status = session.status if session else 'AVAILABLE'
            if session and session.status == 'OCCUPIED' and not session.first_order_at and not current['item_count']:
                visible_status = 'AVAILABLE'
            result.append({'id': table.id, 'name': table.name, 'status': visible_status,
                'session_id': session.id if session else None, 'opened_at': session.opened_at if session else None,
                'first_order_at': session.first_order_at if session else None,
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
        current = orders.bill(db, session.id)
        return {'session_id': session.id, 'status': 'AVAILABLE' if session.status == 'OCCUPIED' and not session.first_order_at and not current['item_count'] else session.status}


@router.get('/menu')
@router.get('/menu/items')
def menu(user=Depends(current_user)):
    with transaction() as db:
        return orders.menu(db)


@router.patch('/menu/items/{item_id}/availability')
def update_availability(item_id: int, data: AvailabilityUpdate, user=Depends(admin)):
    with transaction() as db:
        item = orders.require(db, MenuItem, item_id)
        previous = item.sold_out
        item.sold_out = data.sold_out
        db.add(AuditLog(user_id=user['id'], action='MENU_AVAILABILITY', details={
            'item_id': item.id, 'name': item.name, 'old_sold_out': previous, 'sold_out': item.sold_out}))
        return {'id': item.id, 'sold_out': item.sold_out}


@router.get('/menu/promotions')
def list_promotions(user=Depends(admin)):
    with transaction() as db:
        return [promotions.data(promotion) for promotion in db.scalars(select(MenuPromotion).order_by(MenuPromotion.id.desc()))]


@router.put('/menu/promotions/kopi-teh')
def update_kopi_teh_promotion(data: PromotionUpdate, user=Depends(admin)):
    with transaction() as db:
        promotion = db.scalar(select(MenuPromotion).where(MenuPromotion.code == promotions.KOPI_TEH_CODE))
        if promotion is None:
            promotion = MenuPromotion(code=promotions.KOPI_TEH_CODE, name='Kopi / Teh 限时优惠', skus=promotions.KOPI_TEH_SKUS)
            db.add(promotion)
        promotion.starts_on, promotion.ends_on = data.starts_on, data.ends_on
        promotion.unit_price, promotion.enabled = data.unit_price, data.enabled
        db.flush()
        db.add(AuditLog(user_id=user['id'], action='MENU_PROMOTION', details={'code': promotion.code, **data.model_dump()}))
        return promotions.data(promotion)


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
        old = option.unit_price if option.unit_price is not None else option.price
        if option.unit_price is not None:
            parent = db.scalar(select(MenuItem).join(MenuItemModifierGroup, MenuItemModifierGroup.item_id == MenuItem.id).where(MenuItemModifierGroup.group_id == option.group_id))
            if data.price == 0 and not parent.complimentary:
                raise HTTPException(422, 'Only complimentary items may have a zero price')
            if parent.complimentary and data.price != 0:
                raise HTTPException(422, 'Plain water must remain complimentary')
            option.unit_price = data.price
        else:
            group = db.get(ModifierGroup, option.group_id)
            if group.minimum == 0 and data.price != 0:
                raise HTTPException(422, 'Complimentary customizations must remain free')
            option.price = data.price
        db.add(AuditLog(user_id=user['id'], action='MODIFIER_PRICE', details={'option_id': option_id, 'old': old, 'new': data.price}))
        return {'id': option.id, 'price': option.price, 'unit_price': option.unit_price}


@router.patch('/menu/options/{option_id}/configuration')
def configure_option(option_id: int, data: OptionConfiguration, user=Depends(admin)):
    with transaction() as db:
        option = orders.require(db, ModifierOption, option_id)
        group = db.get(ModifierGroup, option.group_id)
        if group.minimum != 0:
            raise HTTPException(422, 'Only optional customizations can be configured here')
        peers = set(db.scalars(select(ModifierOption.id).where(ModifierOption.group_id == option.group_id)))
        if option.id in data.incompatible_with or not set(data.incompatible_with) <= peers:
            raise HTTPException(422, 'Conflicts must refer to other customizations of this item')
        option.enabled, option.incompatible_with = data.enabled, sorted(set(data.incompatible_with))
        db.add(AuditLog(user_id=user['id'], action='OPTION_CONFIGURATION', details={'option_id': option_id, **data.model_dump()}))
        return data


@router.post('/menu/items/{item_id}/verify')
def verify_menu_item(item_id: int, user=Depends(admin)):
    with transaction() as db:
        item = orders.require(db, MenuItem, item_id)
        item.verification_required = False
        db.add(AuditLog(user_id=user['id'], action='MENU_VERIFIED', details={'item_id': item.id}))
        return {'id': item.id, 'verification_required': False}


@router.post('/order-batches', status_code=201)
def create_batch(data: NewBatch, user=Depends(current_user)):
    with transaction() as db:
        session = orders.active_session(db, data.session_id)
        if session.status == 'PAYMENT_PENDING':
            raise HTTPException(409, 'Checkout in progress; cashier must resume ordering first')
        # Reuse this user's active draft, making reconnects safe.
        batch = db.scalar(select(OrderBatch).where(OrderBatch.session_id == data.session_id, OrderBatch.user_id == user['id'], OrderBatch.status == 'DRAFT'))
        if not batch:
            batch = OrderBatch(session_id=data.session_id, user_id=user['id'], notes=data.notes.strip())
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
            expected.setdefault('notes', '')  # Reconnect safely across a v1.0 -> v1.1 upgrade.
            if expected != details:
                raise HTTPException(409, 'Idempotency key reused with different draft item')
            return orders.item_data(db, db.get(OrderItem, existing.details['item_id']))
        source, options, unit = orders.price_item(db, data.menu_item_id, data.quantity, data.option_ids)
        item = OrderItem(batch_id=identity, menu_item_id=source.id, name=source.name, quantity=data.quantity,
            base_price=source.base_price, unit_price=unit, line_total=unit * data.quantity, notes=data.notes.strip())
        orders.snapshot_item(db, item, source, options)
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


@router.patch('/order-batches/{identity}/items/{item_id}')
def edit_item(identity: int, item_id: int, data: EditItem, key: str = Depends(idempotency_key), user=Depends(current_user)):
    with transaction() as db:
        return order_edits.edit(db, identity, item_id, data, key, user)


@router.delete('/order-batches/{identity}')
def cancel_draft(identity: int, user=Depends(current_user)):
    with transaction() as db:
        batch = orders.editable_batch(db, identity, user)
        batch.status = 'CANCELLED'
        for item in db.scalars(select(OrderItem).where(OrderItem.batch_id == identity)):
            item.status = 'CANCELLED'
        return {'ok': True}


@router.post('/order-batches/{identity}/submit')
def submit(identity: int, data: SubmitBatch | None = None, key: str = Depends(idempotency_key), user=Depends(current_user)):
    with transaction() as db:
        return orders.submit(db, identity, key, user, data.notes if data else None)


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
def print_jobs(completed: bool | None = None, user=Depends(current_user)):
    with transaction() as db:
        finished = func.coalesce(or_(TableSession.status.in_(['PAID', 'CANCELLED']), and_(
            PrintJob.batch_id.is_(None), PrintJob.payment_id.is_(None), PrintJob.status == 'SENT')), False)
        query = (select(PrintJob, TableSession.id, TableSession.status, finished)
            .outerjoin(OrderBatch, PrintJob.batch_id == OrderBatch.id)
            .outerjoin(Payment, PrintJob.payment_id == Payment.id)
            .outerjoin(TableSession, TableSession.id == func.coalesce(OrderBatch.session_id, Payment.session_id))
            .order_by(PrintJob.id.desc()))
        if completed is not None:
            query = query.where(finished == completed)
        if completed is not False:
            query = query.limit(100)
        if user['role'] != 'ADMIN':
            query = query.where(PrintJob.payment_id.is_(None))
        return [{**job_data(job), 'session_id': session_id, 'session_status': session_status,
                 'completed': bool(is_completed)} for job, session_id, session_status, is_completed in db.execute(query)]


@router.get('/payments/{payment_id}/receipt')
def payment_receipt(payment_id: int, user=Depends(admin)):
    with transaction() as db:
        return receipts.document(db, orders.require(db, Payment, payment_id))


@router.post('/payments/{payment_id}/receipt/print', status_code=201)
def print_receipt(payment_id: int, key: str = Depends(idempotency_key), user=Depends(admin)):
    with transaction() as db:
        payment = orders.require(db, Payment, payment_id)
        existing = db.scalar(select(AuditLog).where(AuditLog.request_key == key))
        if existing:
            if existing.action != 'RECEIPT_PRINT' or existing.details['payment_id'] != payment_id:
                raise HTTPException(409, 'Idempotency key reused for another print request')
            return job_data(orders.require(db, PrintJob, existing.details['job_id']))
        job = receipts.queue_original(db, payment)
        db.add(AuditLog(user_id=user['id'], action='RECEIPT_PRINT', request_key=key, details={'payment_id': payment_id, 'job_id': job.id}))
        return job_data(job)


@router.get('/print-jobs/{identity}')
def print_job(identity: int, user=Depends(current_user)):
    with transaction() as db:
        job = orders.require(db, PrintJob, identity)
        if job.payment_id is not None and user['role'] != 'ADMIN':
            raise HTTPException(403, 'Cashier/admin permission required')
        return job_data(job)


@router.get('/print-jobs/{identity}/preview')
def preview(identity: int, user=Depends(current_user)):
    with transaction() as db:
        job = orders.require(db, PrintJob, identity)
        if job.payment_id is not None and user['role'] != 'ADMIN':
            raise HTTPException(403, 'Cashier/admin permission required')
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
        if source.change_id is not None:
            descendants = list(db.scalars(select(PrintJob).where(PrintJob.change_id == source.change_id, PrintJob.routing_group == source.routing_group)))
        elif source.payment_id is not None:
            descendants = list(db.scalars(select(PrintJob).where(PrintJob.payment_id == source.payment_id)))
        else:
            descendants = list(db.scalars(select(PrintJob).where(PrintJob.batch_id == source.batch_id, PrintJob.routing_group == source.routing_group))) if source.batch_id else []
        if any(j.status in ('PENDING', 'SENDING') for j in descendants):
            raise HTTPException(409, 'Another attempt for this batch is already queued')
        job = PrintJob(batch_id=source.batch_id, payment_id=source.payment_id, change_id=source.change_id, routing_group=source.routing_group, ticket=source.ticket, reprint=True, attempts=source.attempts)
        db.add(job)
        db.flush()
        db.add(AuditLog(user_id=user['id'], action='REPRINT', request_key=key, details={'source_job_id': identity, 'new_job_id': job.id, 'previous_status': source.status}))
        return job_data(job)


@router.get('/printers/config')
def printer_config(user=Depends(admin)):
    with transaction() as db:
        return PrinterSettings(**db.get(PrinterConfiguration, 1).config).model_dump()


@router.get('/printers/windows')
def windows_printers(user=Depends(admin)):
    from app.printing.windows import installed_printers
    return {'printers': installed_printers()}


@router.put('/printers/config')
def update_printer(data: PrinterSettings, user=Depends(admin)):
    import ipaddress
    import codecs
    hosts = []
    if data.mode == 'network':
        hosts.extend([data.kitchen_host, data.rice_host or data.kitchen_host, data.beverage_host] if data.separate_stations else [data.host])
    if data.receipt_mode == 'network':
        hosts.append(data.receipt_host)
    if hosts:
        try:
            for host in hosts:
                address = ipaddress.ip_address(host)
                if not address.is_private or address.is_loopback or address.is_link_local or address.is_unspecified or address.is_multicast:
                    raise ValueError()
        except ValueError:
            raise HTTPException(422, 'Printer must use a private LAN IP address')
    if data.receipt_mode == 'windows':
        from app.printing.windows import installed_printers
        if not data.receipt_printer_name or data.receipt_printer_name not in installed_printers():
            raise HTTPException(422, 'Select an installed Windows receipt printer')
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
        ticket = {'table': 'TEST', 'time': now(), 'order_type': 'NEW', 'items': [
            {'name': '打印测试', 'quantity': 1, 'printer_group': 'KITCHEN', 'modifiers': [{'name': '黑酱 / 不辣 / 加面'}]},
            {'name': '饭档打印测试', 'quantity': 1, 'printer_group': 'RICE', 'modifiers': [{'name': '大份'}]},
            {'name': 'Kopi O', 'quantity': 1, 'printer_group': 'BEVERAGE', 'modifiers': [{'name': '冰 ICED'}]}]}
        jobs = [PrintJob(routing_group=station, ticket={**ticket, 'items': [item for item in ticket['items'] if item['printer_group'] == station]})
                for station, _ in STATIONS]
        db.add_all(jobs)
        db.flush()
        db.add(AuditLog(user_id=user['id'], action='TEST_PRINT', details={'job_ids': [job.id for job in jobs]}))
        return {**job_data(jobs[0]), 'print_jobs': [job_data(job) for job in jobs]}


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
        sessions = [db.get(TableSession, payment.session_id) for payment in payments]
        durations = [value for session in sessions if (value := orders.dining_duration(session)) is not None]
        breakdown = {code: 0 for code in ('MAINS', 'SNACKS', 'DRINKS', 'BEER')}
        bottles, beer_units = 0, 0
        for payment in payments:
            for item in orders.bill(db, payment.session_id)['items']:
                breakdown[item['category_code']] = breakdown.get(item['category_code'], 0) + item['line_total']
                bottles += item['physical_bottles']
                if item['category_code'] == 'BEER':
                    beer_units += item['quantity']
        total = sum(p.total for p in payments)
        return {'date': day.isoformat(), 'timezone': 'Asia/Kuala_Lumpur', 'total': total,
            'transactions': len(payments), 'completed_sessions': len(payments), 'category_sales': breakdown,
            'average_spending': (total + len(payments) // 2) // len(payments) if payments else 0,
            'dining_duration': {'count': len(durations), 'average_seconds': sum(durations) / len(durations) if durations else None,
                'minimum_seconds': min(durations) if durations else None, 'maximum_seconds': max(durations) if durations else None},
            'beer_units': beer_units, 'beer_bottles': bottles,
            'methods': {method: sum(p.total for p in payments if p.method == method) for method in ('CASH', 'QR', 'OTHER')}}


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
