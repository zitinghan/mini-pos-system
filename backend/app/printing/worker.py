import json
import logging
import socket
import time
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from app.core.config import OUTPUT_DIR
from app.database.db import transaction
from app.models.entities import PrintJob, PrinterConfiguration, now
from app.printing.tickets import render, ticket_lines

logger = logging.getLogger('keke.printing')


def recover_stale():
    # Never resend a claimed job after a crash: bytes may already have reached the printer.
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    with transaction() as db:
        for job in db.scalars(select(PrintJob).where(PrintJob.status == 'SENDING', PrintJob.claimed_at < cutoff)):
            job.status = 'UNKNOWN'
            job.error = 'Worker interrupted or delivery timed out; verify with kitchen before reprinting'


def run_once():
    with transaction() as db:
        job = db.scalar(select(PrintJob).where(PrintJob.status == 'PENDING').order_by(PrintJob.id).limit(1))
        if not job:
            return False
        job.status, job.claimed_at, job.attempts = 'SENDING', now(), job.attempts + 1
        identity, ticket, reprint = job.id, job.ticket, job.reprint
        config = db.get(PrinterConfiguration, 1).config.copy()
    # Connection, rendering and all writes happen after the claim transaction commits.
    status, error, preview = 'SENT', None, None
    connection = None
    write_started = False
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output = OUTPUT_DIR / f'job-{identity}.png'
        image = render(ticket, reprint, config['width'], output)
        preview = output.name
        (OUTPUT_DIR / f'job-{identity}.txt').write_text('\n'.join(t for t, _ in ticket_lines(ticket, reprint)), encoding='utf-8')
        if config['mode'] == 'mock':
            simulation = config['simulation']
            if simulation == 'connection_failure':
                raise ConnectionRefusedError('Simulated connection failure; no bytes sent')
            if simulation in ('timeout', 'uncertain'):
                write_started = True
                raise TimeoutError('Simulated uncertain delivery; verify with kitchen')
        else:
            from escpos.printer import Dummy
            device = Dummy(profile=config['profile'])
            device._raw(b'\x1b\x40')
            if config['print_mode'] == 'raster':
                device.image(image, impl=config['raster_command'])
            else:
                for line, size in ticket_lines(ticket, reprint):
                    device._raw(b'\x1d\x21' + (b'\x11' if size >= 30 else b'\x00'))
                    device._raw((line + '\n').encode(config['encoding'], errors='strict'))
            device._raw(b'\x1d\x21\x00' + b'\n' * config['feed'])
            if config['cutter']:
                device.cut()
            payload = device.output
            connection = socket.create_connection((config['host'], config['port']), timeout=5)
            connection.settimeout(10)
            write_started = True
            connection.sendall(payload)
    except Exception as exc:
        status = 'UNKNOWN' if write_started else 'FAILED'
        error = str(exc)[:1000]
    finally:
        if connection:
            connection.close()
    with transaction() as db:
        job = db.get(PrintJob, identity)
        # Do not overwrite a watchdog UNKNOWN result with a delayed success.
        if job.status == 'SENDING':
            job.status, job.error, job.preview = status, error, preview
    logger.info(json.dumps({'event': 'print_result', 'job_id': identity, 'status': status, 'error': error}))
    return True


def main():
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    while True:
        try:
            recover_stale()
            if not run_once():
                time.sleep(1)
        except Exception as exc:
            logger.error(json.dumps({'event': 'worker_error', 'error': str(exc)}))
            time.sleep(2)

if __name__ == '__main__':
    main()
