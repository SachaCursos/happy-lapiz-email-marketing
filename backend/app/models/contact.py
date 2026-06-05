from typing import Optional, Any
from datetime import datetime, date
from sqlmodel import Field, SQLModel, Column
from sqlalchemy import Text, JSON
from pydantic import field_validator


class Contact(SQLModel, table=True):
    __tablename__ = "contacts"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
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

    @field_validator("orders_count", mode="before")
    @classmethod
    def _coerce_orders(cls, v: object) -> int:
        return int(v) if v is not None else 0
