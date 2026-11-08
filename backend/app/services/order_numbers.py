"""Allocate only on submission, inside the application's serialized write transaction."""
from datetime import datetime
from sqlalchemy import select, func
from app.models.entities import OrderBatch
from app.services import business_days


def assign(db, batch):
    if batch.order_number is not None:
        return
    day = business_days.current(datetime.fromisoformat(batch.submitted_at)).isoformat()
    last = db.scalar(select(func.max(OrderBatch.order_number)).where(OrderBatch.business_day == day)) or 0
    batch.business_day, batch.order_number = day, last + 1
