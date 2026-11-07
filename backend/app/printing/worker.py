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
from app.printing.stations import STATIONS

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
        identity, ticket, reprint = job.id, {**job.ticket, 'ticket_number': job.id}, job.reprint
        config = db.get(PrinterConfiguration, 1).config.copy()
        if job.routing_group == 'RECEIPT':
            config.update(mode=config.get('receipt_mode', 'mock'), host=config.get('receipt_host', ''),
                port=config.get('receipt_port', 9100), width=config.get('receipt_width', 384),
                cutter=config.get('receipt_cutter', False), simulation=config.get('receipt_simulation', 'success'),
                printer_name=config.get('receipt_printer_name', ''), print_mode='raster', profile='default',
                raster_command='bitImageRaster')
        elif job.routing_group in dict(STATIONS) and config.get('separate_stations', False):
            station = job.routing_group.lower()
            if station == 'rice' and not config.get('rice_host'):
                station = 'kitchen'
            config['host'] = config.get(f'{station}_host') or config.get('host', '')
            config['port'] = config.get(f'{station}_port', config.get('port', 9100))
        job.printer_mode = config['mode']
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
            if config['mode'] == 'windows':
                from app.printing.windows import WindowsRawPrinter
                connection = WindowsRawPrinter(config['printer_name'])
            else:
                connection = socket.create_connection((config['host'], config['port']), timeout=5)
                connection.settimeout(10)
            write_started = True
            connection.sendall(payload)
    except Exception as exc:
        status = 'UNKNOWN' if write_started else 'FAILED'
        error = str(exc)[:1000]
    finally:
        if connection:
            try:
                connection.close()
            except Exception as exc:
                status = 'UNKNOWN' if write_started else 'FAILED'
                error = str(exc)[:1000]
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
