from datetime import datetime, timezone
from sqlalchemy import String, ForeignKey, JSON, Index, text, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database.db import Base


def now():
    return datetime.now(timezone.utc).isoformat()

class Record:
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[str] = mapped_column(default=now)
    updated_at: Mapped[str] = mapped_column(default=now, onupdate=now)

class User(Record, Base):
    __tablename__ = 'users'
    name: Mapped[str] = mapped_column(String(80), unique=True)
    pin_hash: Mapped[str]
    role: Mapped[str]
    failed_attempts: Mapped[int] = mapped_column(default=0)
    locked_until: Mapped[str | None]
    __table_args__ = (CheckConstraint("role IN ('STAFF','ADMIN')"),)

class AuthSession(Record, Base):
    __tablename__ = 'auth_sessions'
    token_hash: Mapped[str] = mapped_column(unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    expires_at: Mapped[str]

class LoginAttempt(Base):
    __tablename__ = 'login_attempts'
    key: Mapped[str] = mapped_column(primary_key=True)
    count: Mapped[int] = mapped_column(default=0)
    expires_at: Mapped[str]

class RestaurantTable(Record, Base):
    __tablename__ = 'restaurant_tables'
    name: Mapped[str] = mapped_column(unique=True)

class TableSession(Record, Base):
    __tablename__ = 'table_sessions'
    table_id: Mapped[int] = mapped_column(ForeignKey('restaurant_tables.id'), index=True)
    status: Mapped[str] = mapped_column(default='OCCUPIED')
    closed_at: Mapped[str | None]
    opened_at: Mapped[str] = mapped_column(default=now)
    first_order_at: Mapped[str | None]
    paid_at: Mapped[str | None]
    __table_args__ = (Index('uq_active_table', 'table_id', unique=True, sqlite_where=text("status IN ('OCCUPIED','PAYMENT_PENDING')")), CheckConstraint("status IN ('OCCUPIED','PAYMENT_PENDING','PAID','CANCELLED')"))

class MenuCategory(Record, Base):
    __tablename__ = 'menu_categories'
    name: Mapped[str]
    display_order: Mapped[int] = mapped_column(default=0)
    code: Mapped[str | None] = mapped_column(unique=True)
    english_name: Mapped[str] = mapped_column(default='')
    printer_group: Mapped[str] = mapped_column(default='KITCHEN')

class MenuItem(Record, Base):
    __tablename__ = 'menu_items'
    category_id: Mapped[int] = mapped_column(ForeignKey('menu_categories.id'))
    name: Mapped[str]
    base_price: Mapped[int]
    active: Mapped[bool] = mapped_column(default=True)
    sold_out: Mapped[bool] = mapped_column(default=False)
    sku: Mapped[str | None] = mapped_column(unique=True)
    description: Mapped[str] = mapped_column(default='')
    complimentary: Mapped[bool] = mapped_column(default=False)
    verification_required: Mapped[bool] = mapped_column(default=False)
    verification_note: Mapped[str] = mapped_column(default='')
    __table_args__ = (CheckConstraint('base_price >= 0'),)


class MenuPromotion(Record, Base):
    __tablename__ = 'menu_promotions'
    code: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    unit_price: Mapped[int]
    starts_on: Mapped[str]
    ends_on: Mapped[str]
    skus: Mapped[list] = mapped_column(JSON)
    enabled: Mapped[bool] = mapped_column(default=True)
    __table_args__ = (CheckConstraint('unit_price > 0'),)

class ModifierGroup(Record, Base):
    __tablename__ = 'modifier_groups'
    name: Mapped[str]
    minimum: Mapped[int] = mapped_column(default=1)
    maximum: Mapped[int] = mapped_column(default=1)
    display_order: Mapped[int] = mapped_column(default=0)
    __table_args__ = (CheckConstraint('minimum >= 0 AND maximum >= minimum'),)

class ModifierOption(Record, Base):
    __tablename__ = 'modifier_options'
    group_id: Mapped[int] = mapped_column(ForeignKey('modifier_groups.id'), index=True)
    name: Mapped[str]
    price: Mapped[int] = mapped_column(default=0)
    is_default: Mapped[bool] = mapped_column(default=False)
    display_order: Mapped[int] = mapped_column(default=0)
    unit_price: Mapped[int | None]
    bottles: Mapped[int] = mapped_column(default=0)
    enabled: Mapped[bool] = mapped_column(default=True)
    incompatible_with: Mapped[list] = mapped_column(JSON, default=list)
    __table_args__ = (CheckConstraint('price >= 0'),)

class MenuItemModifierGroup(Base):
    __tablename__ = 'menu_item_modifier_groups'
    item_id: Mapped[int] = mapped_column(ForeignKey('menu_items.id'), primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey('modifier_groups.id'), primary_key=True)

class OrderBatch(Record, Base):
    __tablename__ = 'order_batches'
    session_id: Mapped[int] = mapped_column(ForeignKey('table_sessions.id'), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    status: Mapped[str] = mapped_column(default='DRAFT')
    submission_key: Mapped[str | None] = mapped_column(unique=True)
    submitted_at: Mapped[str | None]
    __table_args__ = (
        Index('uq_user_draft', 'session_id', 'user_id', unique=True, sqlite_where=text("status = 'DRAFT'")),
        CheckConstraint("status IN ('DRAFT','SUBMITTED','CANCELLED')"),
    )

class OrderItem(Record, Base):
    __tablename__ = 'order_items'
    batch_id: Mapped[int] = mapped_column(ForeignKey('order_batches.id'), index=True)
    menu_item_id: Mapped[int] = mapped_column(ForeignKey('menu_items.id'))
    name: Mapped[str]
    quantity: Mapped[int]
    base_price: Mapped[int]
    unit_price: Mapped[int]
    line_total: Mapped[int]
    status: Mapped[str] = mapped_column(default='DRAFT')
    sku: Mapped[str | None]
    category_code: Mapped[str] = mapped_column(default='MAINS')
    printer_group: Mapped[str] = mapped_column(default='KITCHEN')
    description: Mapped[str] = mapped_column(default='')
    variant_name: Mapped[str | None]
    bottles_per_unit: Mapped[int] = mapped_column(default=0)
    physical_bottles: Mapped[int] = mapped_column(default=0)
    notes: Mapped[str] = mapped_column(default='')
    __table_args__ = (CheckConstraint('quantity > 0 AND line_total >= 0'),)

class OrderItemModifier(Record, Base):
    __tablename__ = 'order_item_modifiers'
    item_id: Mapped[int] = mapped_column(ForeignKey('order_items.id'), index=True)
    option_id: Mapped[int] = mapped_column(ForeignKey('modifier_options.id'))
    name: Mapped[str]
    price: Mapped[int]

class Payment(Record, Base):
    __tablename__ = 'payments'
    session_id: Mapped[int] = mapped_column(ForeignKey('table_sessions.id'), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    idempotency_key: Mapped[str] = mapped_column(unique=True)
    request_hash: Mapped[str]
    method: Mapped[str]
    total: Mapped[int]
    received: Mapped[int]
    change: Mapped[int]
    __table_args__ = (
        Index('ix_payments_created', 'created_at'),
        CheckConstraint("method IN ('CASH','QR','OTHER')"),
        CheckConstraint('total >= 0 AND received >= total AND change = received - total'),
    )

class PrinterConfiguration(Record, Base):
    __tablename__ = 'printer_configurations'
    config: Mapped[dict] = mapped_column(JSON)

class PrintJob(Record, Base):
    __tablename__ = 'print_jobs'
    batch_id: Mapped[int | None] = mapped_column(ForeignKey('order_batches.id'), index=True)
    status: Mapped[str] = mapped_column(default='PENDING', index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    reprint: Mapped[bool] = mapped_column(default=False)
    ticket: Mapped[dict] = mapped_column(JSON)
    error: Mapped[str | None]
    preview: Mapped[str | None]
    claimed_at: Mapped[str | None]
    routing_group: Mapped[str] = mapped_column(default='COMBINED')
    __table_args__ = (
        Index('uq_active_print_batch', 'batch_id', 'routing_group', unique=True, sqlite_where=text("status IN ('PENDING','SENDING')")),
        CheckConstraint("status IN ('PENDING','SENDING','SENT','FAILED','UNKNOWN')"),
    )

class AuditLog(Record, Base):
    __tablename__ = 'audit_logs'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    action: Mapped[str]
    request_key: Mapped[str | None] = mapped_column(unique=True)
    details: Mapped[dict] = mapped_column(JSON)
