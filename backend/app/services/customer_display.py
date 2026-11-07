"""Optional B1 numeric display; serial failures must never undo a payment."""
import json
import logging
from pathlib import Path
import threading

CONFIG_PATH = Path(__file__).resolve().parents[2] / 'data' / 'customer-display.json'
lock = threading.RLock()
logger = logging.getLogger('keke.customer_display')


def payload(amount):
    if type(amount) is not int or not 0 <= amount <= 99999999:
        raise ValueError('Display amount must fit eight digits including cents')
    return b'\x1b@\x1bQA' + f'{amount // 100}.{amount % 100:02d}'.encode('ascii') + b'\r'


def show_amount(amount):
    with lock:
        try:
            if not CONFIG_PATH.exists():
                return {'status': 'disabled'}
            settings = json.loads(CONFIG_PATH.read_text(encoding='utf-8-sig'))
            if not settings.get('enabled', False):
                return {'status': 'disabled'}
            import serial
            data = payload(amount)
            with serial.Serial(settings.get('port', 'COM2'), settings.get('baudrate', 2400),
                               bytesize=8, parity='N', stopbits=1, timeout=1, write_timeout=1) as port:
                if port.write(data) != len(data):
                    raise OSError('Incomplete customer display write')
                port.flush()
            return {'status': 'sent', 'amount': amount}
        except Exception:
            logger.exception('Customer display unavailable; checkout remains available')
            return {'status': 'unavailable'}
