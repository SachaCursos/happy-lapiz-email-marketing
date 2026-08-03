from typing import Optional, Any
from datetime import datetime, date
from sqlmodel import Field, SQLModel, Column, UniqueConstraint
from sqlalchemy import Text, JSON
from pydantic import field_validator


class Contact(SQLModel, table=True):
    __tablename__ = "contacts"
    # Per-shop-unique email — applied to the live DB by the self-healing
    # migration block in database.py (backfill any NULL shop_id, then swap
    # the old global-unique index for this composite one). NOT the alembic
    # 0004_tighten_shop_id_constraints migration — that one bundles 18 other
    # tables that still have live code paths writing NULL shop_id and isn't
    # safe to run yet; this constraint only concerns contacts.
    __table_args__ = (UniqueConstraint("shop_id", "email", name="contacts_shop_id_email_key"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    shop_id: Optional[int] = Field(default=None, foreign_key="shops.id", index=True)
    email: str = Field(index=True)
    name: Optional[str] = None
    phone: Optional[str] = None
    origin_utm: Optional[str] = None

    # opt-in
    opted_in: bool = Field(default=True)
    opted_in_at: Optional[datetime] = None
    opted_out_at: Optional[datetime] = None

    # legacy (kept for backward compat, maps to last_purchase)
    ultima_visita: Optional[date] = None
    ticket_medio: Optional[float] = None
    location: Optional[str] = None

    custom_fields: Optional[Any] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Shopify ecommerce
    orders_count: int = Field(default=0)
    total_spent: Optional[float] = None
    last_purchase: Optional[date] = None
    products_purchased: Optional[Any] = Field(default=None, sa_column=Column(JSON))
    shipping_city: Optional[str] = None
    shipping_province: Optional[str] = None
    all_shipping_cities: Optional[Any] = Field(default=None, sa_column=Column(JSON))

    # Klaviyo
    klaviyo_id: Optional[str] = None
    last_event_date: Optional[datetime] = None
    klaviyo_properties: Optional[Any] = Field(default=None, sa_column=Column(JSON))
    klaviyo_location: Optional[Any] = Field(default=None, sa_column=Column(JSON))
    ultima_visita_web: Optional[datetime] = None
    accepts_marketing: Optional[bool] = None
    expected_next_order: Optional[date] = None
    gender: Optional[str] = Field(default=None)  # 'M' | 'F' | None
    # Inferred from form: madre|padre|abuela|abuelo|tia|tio|madrina|padrino|hermana|hermano|otro|no_identificado
    family_role: Optional[str] = Field(default=None, index=True)
    birthday: Optional[date] = None
    notes: Optional[str] = None


class ContactCreate(SQLModel):
    email: str
    name: Optional[str] = None
    phone: Optional[str] = None
    origin_utm: Optional[str] = None
    location: Optional[str] = None
    opted_in: bool = True
    orders_count: int = 0
    ultima_visita: Optional[date] = None
    ticket_medio: Optional[float] = None
    custom_fields: Optional[dict] = None


class ContactUpdate(SQLModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    origin_utm: Optional[str] = None
    location: Optional[str] = None
    opted_in: Optional[bool] = None
    orders_count: Optional[int] = None
    ultima_visita: Optional[date] = None
    ticket_medio: Optional[float] = None
    custom_fields: Optional[dict] = None
    accepts_marketing: Optional[bool] = None


class ContactRead(SQLModel):
    id: int
    email: str
    name: Optional[str] = None
    phone: Optional[str] = None
    origin_utm: Optional[str] = None
    location: Optional[str] = None
    opted_in: bool
    opted_in_at: Optional[datetime] = None
    opted_out_at: Optional[datetime] = None
    ultima_visita: Optional[date] = None
    ticket_medio: Optional[float] = None
    custom_fields: Optional[dict] = None
    created_at: datetime
    updated_at: datetime
    # Shopify
    orders_count: int = 0
    total_spent: Optional[float] = None
    last_purchase: Optional[date] = None
    products_purchased: Optional[Any] = None
    shipping_city: Optional[str] = None
    shipping_province: Optional[str] = None
    all_shipping_cities: Optional[Any] = None
    # Klaviyo
    klaviyo_id: Optional[str] = None
    last_event_date: Optional[datetime] = None
    klaviyo_properties: Optional[dict] = None
    klaviyo_location: Optional[dict] = None
    ultima_visita_web: Optional[datetime] = None
    accepts_marketing: Optional[bool] = None
    expected_next_order: Optional[date] = None
    gender: Optional[str] = None
    family_role: Optional[str] = None
    birthday: Optional[date] = None
    notes: Optional[str] = None

    @field_validator("orders_count", mode="before")
    @classmethod
    def _coerce_orders(cls, v: object) -> int:
        return int(v) if v is not None else 0
