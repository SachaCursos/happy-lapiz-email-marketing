from typing import Any, Dict, List, Optional
from datetime import datetime
from sqlmodel import Field, SQLModel, Column
from sqlalchemy import JSON


class Campaign(SQLModel, table=True):
    __tablename__ = "campaigns"

    id: Optional[int] = Field(default=None, primary_key=True)
    shop_id: Optional[int] = Field(default=None, foreign_key="shops.id", index=True)
    name: str = Field(index=True)
    subject: str
    preview_text: Optional[str] = None
    template_id: Optional[int] = Field(default=None, foreign_key="templates.id")
    segment_id: int = Field(foreign_key="segments.id")
    exclude_segment_ids: Optional[Any] = Field(default=None, sa_column=Column(JSON))
    # A/B variants: [{variant, subject, template_id, weight}, ...]
    variants: Optional[Any] = Field(default=None, sa_column=Column("variants", JSON))
    # draft | scheduled | sending | sent | cancelled
    status: str = Field(default="draft")
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    created_by: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CampaignSend(SQLModel, table=True):
    __tablename__ = "campaign_sends"

    id: Optional[int] = Field(default=None, primary_key=True)
    shop_id: Optional[int] = Field(default=None, foreign_key="shops.id", index=True)
    campaign_id: int = Field(foreign_key="campaigns.id", index=True)
    contact_id: int = Field(foreign_key="contacts.id", index=True)
    resend_id: Optional[str] = Field(default=None, index=True)
    # queued | sent | delivered | opened | clicked | bounced | complained
    status: str = Field(default="queued")
    variant_sent: Optional[str] = Field(default=None)  # "A", "B", etc.
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    clicked_at: Optional[datetime] = None
    bounced_at: Optional[datetime] = None


class CampaignCreate(SQLModel):
    name: str
    subject: str
    preview_text: Optional[str] = None
    template_id: Optional[int] = None
    segment_id: int
    exclude_segment_ids: Optional[List[int]] = None
    variants: Optional[List[Dict]] = None
    scheduled_at: Optional[datetime] = None
    status: Optional[str] = None


class CampaignUpdate(SQLModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    preview_text: Optional[str] = None
    template_id: Optional[int] = None
    segment_id: Optional[int] = None
    exclude_segment_ids: Optional[List[int]] = None
    variants: Optional[List[Dict]] = None
    scheduled_at: Optional[datetime] = None
    status: Optional[str] = None


class CampaignRead(SQLModel):
    id: int
    name: str
    subject: str
    preview_text: Optional[str]
    template_id: Optional[int]
    segment_id: int
    exclude_segment_ids: Optional[List[int]] = None
    variants: Optional[List[Dict]] = None
    status: str
    scheduled_at: Optional[datetime]
    sent_at: Optional[datetime]
    created_by: Optional[int]
    created_at: datetime


class CampaignVariantStat(SQLModel):
    variant: str
    sent: int
    opened: int
    clicked: int
    open_rate: float
    click_rate: float


class CampaignStats(SQLModel):
    campaign_id: int
    total: int
    sent: int
    delivered: int
    opened: int
    clicked: int
    bounced: int
    complained: int
    open_rate: float
    click_rate: float
    bounce_rate: float
    variants: List[CampaignVariantStat] = []
