"""Scheduled prices use inclusive Malaysia dates and leave regular menu prices intact."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select
from app.models.entities import MenuPromotion

KOPI_TEH_SKUS = ['KOPI_O', 'KOPI', 'KOPI_C', 'TEH_O', 'TEH', 'TEH_C']
KOPI_TEH_CODE = 'KOPI_TEH_RM1_2026'


def current_day(at=None):
    return (at or datetime.now(timezone.utc)).astimezone(ZoneInfo('Asia/Kuala_Lumpur')).date().isoformat()


def active_promotions(db):
    day = current_day()
    return list(db.scalars(select(MenuPromotion).where(MenuPromotion.enabled == True,
        MenuPromotion.starts_on <= day, MenuPromotion.ends_on >= day).order_by(MenuPromotion.id.desc())))


def for_sku(promotions, sku):
    return next((promotion for promotion in promotions if sku in promotion.skus), None)


def data(promotion):
    return {'id': promotion.id, 'code': promotion.code, 'name': promotion.name,
        'unit_price': promotion.unit_price, 'starts_on': promotion.starts_on,
        'ends_on': promotion.ends_on, 'skus': promotion.skus, 'enabled': promotion.enabled,
        'is_active': promotion.enabled and promotion.starts_on <= current_day() <= promotion.ends_on}
