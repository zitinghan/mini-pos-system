import json
from unittest.mock import Mock, patch

import pytest
from app.services import customer_display
from test_workflows import open_session, draft, add, submit, key
from test_v11 import catalog


def test_confirmed_b1_protocol():
    assert customer_display.payload(1234) == b'\x1b@\x1bQA12.34\r'
    assert customer_display.payload(0).endswith(b'0.00\r')
    for invalid in (-1, 100000000, 12.34, True):
        with pytest.raises(ValueError):
            customer_display.payload(invalid)


def test_optional_display_and_transport_failure(tmp_path, monkeypatch):
    path = tmp_path / 'display.json'
    monkeypatch.setattr(customer_display, 'CONFIG_PATH', path)
    assert customer_display.show_amount(1234)['status'] == 'disabled'
    path.write_text(json.dumps({'enabled': True, 'port': 'COM2', 'baudrate': 2400}))
    with patch('serial.Serial') as serial:
        port = serial.return_value.__enter__.return_value
        port.write.return_value = len(customer_display.payload(1234))
        assert customer_display.show_amount(1234)['status'] == 'sent'
        port.write.assert_called_once_with(customer_display.payload(1234))
        serial.assert_called_once_with('COM2', 2400, bytesize=8, parity='N', stopbits=1, timeout=1, write_timeout=1)
    with patch('serial.Serial', side_effect=OSError('Disconnected')):
        assert customer_display.show_amount(1234)['status'] == 'unavailable'


def test_checkout_display_and_committed_cash_change(client, headers, monkeypatch):
    session = open_session(client, headers)
    batch = draft(client, headers, session)
    food = catalog(client, headers)['WANTAN_MEE']
    assert add(client, headers, batch, food).status_code == 201
    assert submit(client, headers, batch).status_code == 200
    send = Mock(return_value={'status': 'sent'})
    monkeypatch.setattr(customer_display, 'show_amount', send)
    checkout = client.post(f'/api/table-sessions/{session}/checkout', headers=headers)
    assert checkout.status_code == 200
    total = checkout.json()['total']
    send.assert_called_once_with(total)
    send.reset_mock()
    endpoint = f'/api/table-sessions/{session}/customer-display'
    assert client.post(endpoint, headers=headers, json={'expected_total': total, 'final_total': total-100}).status_code == 200
    send.assert_called_once_with(total-100)
    send.reset_mock()
    assert client.post(endpoint, headers=headers, json={'expected_total': total+1, 'final_total': total}).status_code == 409
    assert client.post(endpoint, headers=headers, json={'expected_total': total, 'final_total': total+1}).status_code == 422
    assert client.post(endpoint, json={'expected_total': total, 'final_total': total}).status_code == 401
    send.assert_not_called()
    send.return_value = {'status': 'unavailable'}
    payment = client.post(f'/api/table-sessions/{session}/payments', headers=key(headers),
        json={'method': 'CASH', 'received': total+500, 'expected_total': total})
    assert payment.status_code == 200, payment.text
    send.assert_called_once_with(500)
    send.reset_mock()
    assert client.post(endpoint, headers=headers, json={'expected_total': total, 'final_total': total}).status_code == 409
    send.assert_not_called()
