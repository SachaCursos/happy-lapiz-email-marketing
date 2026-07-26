from typing import Optional, Any
from datetime import datetime
from sqlmodel import Field, SQLModel, Column
from sqlalchemy import JSON


class Shop(SQLModel, table=True):
    __tablename__ = "shops"

    id: Optional[int] = Field(default=None, primary_key=True)
    shopify_domain: str = Field(unique=True, index=True)
    shopify_shop_id: Optional[str] = None
    name: Optional[str] = None
    access_token_encrypted: str
    scopes: Optional[str] = None
    status: str = Field(default="active", sa_column_kwargs={"server_default": "active"})  # active | uninstalled

    installed_at: datetime = Field(default_factory=datetime.utcnow)
    uninstalled_at: Optional[datetime] = None

    shop_owner_email: Optional[str] = None
    plan_name: Optional[str] = None
    currency: Optional[str] = None

    # pending | running | complete | failed. server_default matters here, not just
    # Python-side default=: raw SQL inserts (e.g. the 0003 migration's bootstrap
    # row) don't go through the ORM, so without a real DB-level default they'd hit
    # a NOT NULL violation on any column they don't list explicitly.
    initial_sync_status: str = Field(default="pending", sa_column_kwargs={"server_default": "pending"})
    initial_sync_started_at: Optional[datetime] = None
    initial_sync_completed_at: Optional[datetime] = None
    initial_sync_error: Optional[str] = None
    initial_sync_stats: Optional[Any] = Field(default=None, sa_column=Column(JSON))

    # None = usa el proveedor global (settings.EMAIL_PROVIDER, hoy "resend").
    # "resend" | "ses" para fijar el proveedor de esta tienda explícitamente.
    email_provider: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def display_name(self) -> str:
        """Human-readable shop name for UI/email use — falls back to the
        Shopify subdomain when the real store name hasn't been fetched yet
        (e.g. a bootstrap shop that never went through OAuth install)."""
        return self.name or self.shopify_domain.removesuffix(".myshopify.com")


class ShopRead(SQLModel):
    id: int
    shopify_domain: str
    name: Optional[str] = None
    status: str
    shop_owner_email: Optional[str] = None
    plan_name: Optional[str] = None
    currency: Optional[str] = None
    initial_sync_status: str
    installed_at: datetime
