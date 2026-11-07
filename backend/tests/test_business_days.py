from datetime import date, datetime
from uuid import uuid4
import pytest
from sqlalchemy import select
from app.database.db import transaction
from app.models.entities import Payment, TableSession, User
from app.services import business_days


@pytest.mark.parametrize('timestamp,expected', [
    ('2026-11-07T10:00:00+00:00', '2026-11-07'),  # Opening at 18:00
    ('2026-11-07T15:59:59+00:00', '2026-11-07'),
    ('2026-11-07T16:00:00+00:00', '2026-11-07'),  # Midnight does not reset
    ('2026-11-07T19:59:59+00:00', '2026-11-07'),
    ('2026-11-07T20:00:00+00:00', '2026-11-07'),  # 04:00 still belongs to the evening
    ('2026-11-08T03:59:59+00:00', '2026-11-07'),
    ('2026-11-08T04:00:00+00:00', '2026-11-08'),  # Noon is exclusive end
    ('2026-12-31T18:00:00+00:00', '2026-12-31'),
    ('2027-01-01T01:59:59+08:00', '2026-12-31'),
])
def test_business_date_includes_overnight_sales(timestamp, expected):
    assert business_days.current(datetime.fromisoformat(timestamp)).isoformat() == expected


def test_reports_and_transaction_list_use_identical_overnight_boundaries(client, headers, monkeypatch):
    timestamps = [
        '2026-11-07T03:59:59+00:00',  # Before selected day
        '2026-11-07T04:00:00+00:00',  # Start of selected day at noon
        '2026-11-07T10:00:00+00:00',  # 18:00 selected day
        '2026-11-07T16:00:00+00:00',  # Midnight following day
        '2026-11-08T03:59:59+00:00',  # Last second selected day
        '2026-11-08T04:00:00+00:00',  # First second next day
    ]
    with transaction() as db:
        user = db.scalar(select(User).where(User.name == 'cashier'))
        for index, timestamp in enumerate(timestamps):
            session = TableSession(table_id=5, status='PAID', first_order_at='2026-11-06T19:00:00+00:00',
                paid_at=timestamp, closed_at=timestamp)
            db.add(session); db.flush()
            db.add(Payment(session_id=session.id, user_id=user.id, idempotency_key=str(uuid4()), request_hash='test',
                method='CASH' if index % 2 else 'QR', total=800, received=800, change=0, created_at=timestamp))
    report = client.get('/api/reports/daily-sales?day=2026-11-07', headers=headers).json()
    assert report['total'] == 3200 and report['completed_sessions'] == 4
    assert report['methods']['CASH'] == report['methods']['QR'] == 1600
    assert report['business_day_cutoff'] == '12:00'
    assert (report['period_start'], report['period_end']) == business_days.bounds(date(2026, 11, 7))
    history = client.get('/api/reports/transactions?day=2026-11-07', headers=headers).json()
    assert sorted(row['created_at'] for row in history) == timestamps[1:-1]
    monkeypatch.setattr(business_days, 'current', lambda: date(2026, 11, 7))
    assert client.get('/api/reports/daily-sales', headers=headers).json() == report
    next_day = client.get('/api/reports/daily-sales?day=2026-11-08', headers=headers).json()
    assert next_day['total'] == 800 and next_day['completed_sessions'] == 1
