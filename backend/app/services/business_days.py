"""Restaurant reporting days end at noon in Kuala Lumpur, including overnight sales."""
from datetime import datetime, date, time, timedelta, timezone
from zoneinfo import ZoneInfo

ZONE = ZoneInfo('Asia/Kuala_Lumpur')
CUTOFF_HOUR = 12


def current(timestamp: datetime | None = None) -> date:
    local = (timestamp or datetime.now(timezone.utc)).astimezone(ZONE)
    return (local - timedelta(hours=CUTOFF_HOUR)).date()


def bounds(day: date) -> tuple[str, str]:
    start = datetime.combine(day, time(CUTOFF_HOUR), ZONE)
    end = datetime.combine(day + timedelta(days=1), time(CUTOFF_HOUR), ZONE)
    return start.astimezone(timezone.utc).isoformat(), end.astimezone(timezone.utc).isoformat()
