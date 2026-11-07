"""Customer receipts use paid snapshots and never resend a payment on page reload."""
from sqlalchemy import select
from app.models.entities import Receipt, PrintJob, User, PrinterConfiguration
from app.printing.jobs import job_data


def build(db, payment):
    from app.services.orders import bill
    current = bill(db, payment.session_id)
    cashier = db.get(User, payment.user_id)
    return {'kind': 'RECEIPT', 'restaurant': '可可·南洋咖啡店', 'english_name': 'KE KE / KOPITIAM',
        'receipt_number': f'R{payment.id:06d}', 'payment_id': payment.id, 'session_id': payment.session_id,
        'table': current['table'], 'time': payment.created_at, 'cashier': cashier.name if cashier else '',
        'currency': 'MYR', 'items': current['items'], 'order_notes': current['order_notes'], 'table_notes': current['table_notes'], 'total': payment.total,
        'original_total': payment.original_total if payment.original_total is not None else payment.total,
        'offer_reason': payment.offer_reason,
        'received': payment.received, 'change': payment.change, 'method': payment.method,
        'dining_duration_seconds': current['dining_duration_seconds']}


def saved(db, payment, create=False):
    receipt = db.scalar(select(Receipt).where(Receipt.payment_id == payment.id))
    if receipt:
        return receipt.snapshot
    snapshot = build(db, payment)
    if create:
        db.add(Receipt(payment_id=payment.id, snapshot=snapshot))
    return snapshot


def queue_original(db, payment):
    original = db.scalar(select(PrintJob).where(PrintJob.payment_id == payment.id, PrintJob.reprint == False))
    if original:
        return original
    job = PrintJob(payment_id=payment.id, session_id=payment.session_id, routing_group='RECEIPT', ticket=saved(db, payment, create=True))
    db.add(job)
    db.flush()
    return job


def document(db, payment):
    jobs = list(db.scalars(select(PrintJob).where(PrintJob.payment_id == payment.id).order_by(PrintJob.id.desc())))
    config = db.get(PrinterConfiguration, 1).config
    return {**saved(db, payment), 'print_job': job_data(jobs[0]) if jobs else None,
        'print_history': [job_data(job) for job in jobs], 'configured_printer_mode': config.get('receipt_mode', 'mock'),
        'paper_width': config.get('receipt_width', 384),
        'paper_mm': config.get('receipt_paper_mm', 80 if config.get('receipt_width', 384) >= 500 else 58)}
