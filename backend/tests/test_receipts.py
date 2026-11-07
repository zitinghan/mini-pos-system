from concurrent.futures import ThreadPoolExecutor
import ctypes
from ctypes import wintypes
import pytest
from sqlalchemy import select, func

from app.database.db import transaction
from app.database.seed import seed
from app.models.entities import Payment, Receipt, PrintJob, MenuItem, TableSession, RestaurantTable
from app.printing.tickets import ticket_lines, render
from app.printing.worker import run_once
from app.printing.windows import WindowsRawPrinter
from app.services import receipts
from test_workflows import key, open_session, draft, add, submit
from test_v11 import catalog, selections


def submitted(client, headers, sku='WANTAN_MEE'):
    food = catalog(client, headers)[sku]
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    result = add(client, headers, batch, food, selections(food))
    assert result.status_code == 201
    total = submit(client, headers, batch).json()['total']
    return session, total


def paid(client, headers, method='CASH'):
    session, total = submitted(client, headers)
    result = client.post(f'/api/table-sessions/{session}/payments', headers=key(headers), json={
        'method': method, 'received': 1000 if method == 'CASH' else total, 'expected_total': total})
    assert result.status_code == 200, result.text
    return result.json()


@pytest.mark.parametrize('method', ['CASH', 'QR', 'OTHER'])
def test_payment_clears_table_and_atomically_saves_receipt_and_print(client, headers, method):
    payment = paid(client, headers, method)
    with transaction() as db:
        assert db.get(TableSession, payment['session_id']).status == 'PAID'
        receipt = db.scalar(select(Receipt).where(Receipt.payment_id == payment['id']))
        assert receipt.snapshot['total'] == 800
        assert receipt.snapshot['method'] == method
        assert receipt.snapshot['items'][0]['name'] == '云吞面'
        job = db.scalar(select(PrintJob).where(PrintJob.payment_id == payment['id']))
        assert job.routing_group == 'RECEIPT' and job.batch_id is None
        assert job.ticket == receipt.snapshot and job.status == 'PENDING'
    assert client.get('/api/tables/5', headers=headers).json()['status'] == 'AVAILABLE'


def test_payment_retries_and_receipt_refresh_do_not_duplicate_jobs(client, headers):
    session, total = submitted(client, headers)
    request_headers = key(headers)
    payload = {'method': 'QR', 'received': total, 'expected_total': total}
    endpoint = f'/api/table-sessions/{session}/payments'
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda _: client.post(endpoint, headers=request_headers, json=payload), range(3)))
    assert all(result.status_code == 200 for result in results)
    payment_id = results[0].json()['id']
    for _ in range(3):
        response = client.get(f'/api/payments/{payment_id}/receipt', headers=headers)
        assert response.status_code == 200
        assert response.json()['receipt_number'] == f'R{payment_id:06d}'
    with transaction() as db:
        assert db.scalar(select(func.count()).select_from(Payment)) == 1
        assert db.scalar(select(func.count()).select_from(Receipt)) == 1
        assert db.scalar(select(func.count()).select_from(PrintJob).where(PrintJob.payment_id == payment_id)) == 1


def test_receipt_print_outbox_failure_rolls_back_payment_and_table_release(client, headers, monkeypatch):
    session, total = submitted(client, headers)
    def fail(*args): raise RuntimeError('Injected receipt queue failure')
    monkeypatch.setattr(receipts, 'queue_original', fail)
    with pytest.raises(RuntimeError, match='Injected receipt queue failure'):
        client.post(f'/api/table-sessions/{session}/payments', headers=key(headers), json={'method': 'QR', 'received': total, 'expected_total': total})
    with transaction() as db:
        assert db.scalar(select(func.count()).select_from(Payment)) == 0
        assert db.scalar(select(func.count()).select_from(Receipt)) == 0
        assert db.get(TableSession, session).status == 'OCCUPIED'


def test_receipt_snapshot_keeps_paid_prices_after_menu_and_table_rename(client, headers):
    payment = paid(client, headers)
    endpoint = f"/api/payments/{payment['id']}/receipt"
    original = client.get(endpoint, headers=headers).json()
    with transaction() as db:
        db.get(MenuItem, 1).name = 'New menu name'
        db.get(MenuItem, 1).base_price = 2000
        db.get(RestaurantTable, 5).name = 'New table name'
    after = client.get(endpoint, headers=headers).json()
    assert after['items'] == original['items']
    assert after['table'] == 'T05' and after['total'] == 800


def test_legacy_payment_receipt_is_read_only_until_explicit_print(client, headers):
    payment = paid(client, headers)
    with transaction() as db:
        for job in list(db.scalars(select(PrintJob).where(PrintJob.payment_id == payment['id']))): db.delete(job)
        for receipt in list(db.scalars(select(Receipt).where(Receipt.payment_id == payment['id']))): db.delete(receipt)
    endpoint = f"/api/payments/{payment['id']}/receipt"
    assert client.get(endpoint, headers=headers).json()['print_job'] is None
    with transaction() as db:
        assert db.scalar(select(func.count()).select_from(Receipt)) == 0
    response = client.post(endpoint + '/print', headers=key(headers))
    assert response.status_code == 201
    second = client.post(endpoint + '/print', headers=key(headers))
    assert second.json()['id'] == response.json()['id']


def test_staff_cannot_read_customer_receipts_or_their_print_previews(client, headers):
    payment = paid(client, headers)
    document = client.get(f"/api/payments/{payment['id']}/receipt", headers=headers).json()
    token = client.post('/api/auth/login', json={'name': 'staff', 'pin': '654321'}).json()['token']
    staff = {'Authorization': 'Bearer ' + token}
    job_id = document['print_job']['id']
    assert client.get(f"/api/payments/{payment['id']}/receipt", headers=staff).status_code == 403
    assert client.get(f'/api/print-jobs/{job_id}', headers=staff).status_code == 403
    assert client.get(f'/api/print-jobs/{job_id}/preview', headers=staff).status_code == 403
    assert all(job['payment_id'] is None for job in client.get('/api/print-jobs', headers=staff).json())


def test_failed_cashier_print_does_not_undo_payment_and_manual_reprint_is_safe(client, headers):
    settings = client.get('/api/printers/config', headers=headers).json()
    settings['receipt_simulation'] = 'connection_failure'
    client.put('/api/printers/config', headers=headers, json=settings)
    payment = paid(client, headers)
    assert run_once() and run_once()
    receipt_url = f"/api/payments/{payment['id']}/receipt"
    receipt = client.get(receipt_url, headers=headers).json()
    assert receipt['print_job']['status'] == 'FAILED'
    assert client.get('/api/tables/5', headers=headers).json()['status'] == 'AVAILABLE'
    settings['receipt_simulation'] = 'success'
    client.put('/api/printers/config', headers=headers, json=settings)
    retry_headers = key(headers)
    endpoint = f"/api/print-jobs/{receipt['print_job']['id']}/retry"
    replacement = client.post(endpoint, headers=retry_headers)
    assert replacement.status_code == 201
    assert client.post(endpoint, headers=key(headers)).status_code == 409
    assert run_once()
    replay = client.post(endpoint, headers=retry_headers)
    assert replay.json()['id'] == replacement.json()['id']
    assert replay.json()['status'] == 'SENT'
    latest = client.get(receipt_url, headers=headers).json()
    assert len(latest['print_history']) == 2
    assert latest['print_job']['reprint']


def test_receipt_worker_targets_pos80_windows_queue_separately(client, headers, monkeypatch):
    captured = []
    class FakeWindows:
        def __init__(self, name): captured.append([name])
        def sendall(self, payload): captured[-1].append(payload)
        def close(self): pass
    monkeypatch.setattr('app.printing.windows.installed_printers', lambda: ['POS-80C'])
    monkeypatch.setattr('app.printing.windows.WindowsRawPrinter', FakeWindows)
    settings = client.get('/api/printers/config', headers=headers).json()
    settings.update(receipt_mode='windows', receipt_printer_name='POS-80C', receipt_width=576)
    assert client.put('/api/printers/config', headers=headers, json=settings).status_code == 200
    payment = paid(client, headers)
    assert run_once() and run_once()
    assert len(captured) == 1 and captured[0][0] == 'POS-80C'
    assert len(captured[0][1]) > 1000
    document = client.get(f"/api/payments/{payment['id']}/receipt", headers=headers).json()
    assert document['print_job']['printer_mode'] == 'windows'
    assert document['print_job']['status'] == 'SENT'


def test_receipt_render_contains_money_modifiers_and_change(client, headers, tmp_path):
    settings = client.get('/api/printers/config', headers=headers).json()
    settings.update(width=576, receipt_width=384, receipt_paper_mm=55)
    assert client.put('/api/printers/config', headers=headers, json=settings).status_code == 200
    payment = paid(client, headers)
    document = client.get(f"/api/payments/{payment['id']}/receipt", headers=headers).json()
    assert document['paper_mm'] == 55 and document['paper_width'] == 384
    assert client.get('/api/printers/config', headers=headers).json()['width'] == 576
    text = '\n'.join(line for line, _ in ticket_lines(document))
    assert '收据 / RECEIPT' in text and '黑酱' in text
    assert 'RM 8.00' in text and '实收 RM 10.00' in text and '找零 RM 2.00' in text
    for width in (384, 576):
        image = render(document, False, width, tmp_path / f'receipt-{width}.png')
        assert image.width == width and image.mode == '1'
        assert image.height > 200
    assert ticket_lines(document, True)[0][0] == 'REPRINT / 重印'


def test_twenty_tables_seed_is_idempotent_and_keeps_active_session(client, headers):
    session = open_session(client, headers)
    seed(); seed()
    tables = client.get('/api/tables', headers=headers).json()
    assert len(tables) == 20
    assert {table['name'] for table in tables} == {f'T{number:02d}' for number in range(1, 21)}
    assert next(table for table in tables if table['id'] == 5)['session_id'] == session


class FakeSpooler:
    def __init__(self, short=False, end_failure=False):
        self.events, self.short, self.end_failure = [], short, end_failure
    def OpenPrinterW(self, name, handle, defaults):
        self.events.append('open'); ctypes.cast(handle, ctypes.POINTER(wintypes.HANDLE))[0] = 42; return True
    def StartDocPrinterW(self, *args): self.events.append('document'); return 1
    def StartPagePrinter(self, *args): self.events.append('page'); return True
    def WritePrinter(self, handle, buffer, size, written):
        self.events.append('write'); ctypes.cast(written, ctypes.POINTER(wintypes.DWORD))[0] = size - 1 if self.short else size; return True
    def EndPagePrinter(self, *args): self.events.append('end_page'); return True
    def EndDocPrinter(self, *args): self.events.append('end_document'); return not self.end_failure
    def ClosePrinter(self, *args): self.events.append('close'); return True
    def AbortPrinter(self, *args): self.events.append('abort'); return True


def test_windows_raw_spool_sequence_and_complete_write():
    api = FakeSpooler()
    printer = WindowsRawPrinter('test', api=api)
    printer.sendall(b'\x00receipt\x00')
    printer.close(); printer.close()
    assert api.events == ['open', 'document', 'page', 'write', 'end_page', 'end_document', 'close']


def test_windows_short_write_is_reported_uncertain():
    api = FakeSpooler(short=True)
    printer = WindowsRawPrinter('test', api=api)
    with pytest.raises(OSError, match='uncertain'): printer.sendall(b'receipt')
    printer.close()


def test_windows_spool_completion_failure_is_not_reported_success():
    api = FakeSpooler(end_failure=True)
    printer = WindowsRawPrinter('test', api=api)
    printer.sendall(b'receipt')
    with pytest.raises(OSError, match='uncertain'): printer.close()
