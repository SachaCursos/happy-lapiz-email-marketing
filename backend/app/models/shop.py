from typing import Optional, Any
from datetime import datetime
from sqlmodel import Field, SQLModel, Column
from sqlalchemy import JSON


class Shop(SQLModel, table=True):
    __tablename__ = "shops"

    id: Optional[int] = Field(default=None, primary_key=True)
    shopify_domain: str = Field(unique=True, index=True)
    shopify_shop_id: Optional[str] = None
    access_token_encrypted: str
    scopes: Optional[str] = None
    status: str = Field(default="active")  # active | uninstalled

    installed_at: datetime = Field(default_factory=datetime.utcnow)
    uninstalled_at: Optional[datetime] = None

    shop_owner_email: Optional[str] = None
    plan_name: Optional[str] = None
    currency: Optional[str] = None

    initial_sync_status: str = Field(default="pending")  # pending | running | complete | failed
    initial_sync_started_at: Optional[datetime] = None
    initial_sync_completed_at: Optional[datetime] = None
    initial_sync_error: Optional[str] = None
    initial_sync_stats: Optional[Any] = Field(default=None, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ShopRead(SQLModel):
    id: int
    shopify_domain: str
    status: str
    shop_owner_email: Optional[str] = None
    plan_name: Optional[str] = None
    currency: Optional[str] = None
    initial_sync_status: str
    installed_at: datetime
