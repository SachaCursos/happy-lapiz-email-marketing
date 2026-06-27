from typing import Any, List, Optional
from datetime import datetime
from sqlmodel import Field, SQLModel, Column
from sqlalchemy import JSON


class EvergreenCampaign(SQLModel, table=True):
    __tablename__ = "evergreen_campaigns"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    subject: str
    preview_text: Optional[str] = None
    template_id: int = Field(foreign_key="templates.id")
    segment_id: Optional[int] = Field(default=None, foreign_key="segments.id")
    exclude_segment_ids: Optional[Any] = Field(default=None, sa_column=Column(JSON))
    sort_order: int = Field(default=0, index=True)
    # active | paused
    status: str = Field(default="active")
    allow_resend: bool = Field(default=False)
    resend_after_days: Optional[int] = Field(default=None)
    min_days_inactive: int = Field(default=15)
    require_open_in_last_n: int = Field(default=5)
    created_by: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class EvergreenSend(SQLModel, table=True):
    __tablename__ = "evergreen_sends"

    id: Optional[int] = Field(default=None, primary_key=True)
    evergreen_id: int = Field(foreign_key="evergreen_campaigns.id", index=True)
    contact_id: int = Field(foreign_key="contacts.id", index=True)
    resend_id: Optional[str] = Field(default=None, index=True)
    status: str = Field(default="queued")
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    clicked_at: Optional[datetime] = None
    bounced_at: Optional[datetime] = None


class EvergreenCampaignCreate(SQLModel):
    name: str
    subject: str
    preview_text: Optional[str] = None
    template_id: int
    segment_id: Optional[int] = None
    exclude_segment_ids: Optional[List[int]] = None
    allow_resend: bool = False
    resend_after_days: Optional[int] = None
    min_days_inactive: int = 15
    require_open_in_last_n: int = 5
    status: str = "active"


class EvergreenCampaignUpdate(SQLModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    preview_text: Optional[str] = None
    template_id: Optional[int] = None
    segment_id: Optional[int] = None
    exclude_segment_ids: Optional[List[int]] = None
    allow_resend: Optional[bool] = None
    resend_after_days: Optional[int] = None
    min_days_inactive: Optional[int] = None
    require_open_in_last_n: Optional[int] = None
    status: Optional[str] = None


class EvergreenCampaignRead(SQLModel):
    id: int
    name: str
    subject: str
    preview_text: Optional[str]
    template_id: int
    segment_id: Optional[int]
    exclude_segment_ids: Optional[List[int]]
    sort_order: int
    status: str
    allow_resend: bool
    resend_after_days: Optional[int]
    min_days_inactive: int
    require_open_in_last_n: int
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime


class EvergreenStats(SQLModel):
    evergreen_id: int
    total: int
    sent: int
    opened: int
    clicked: int
    open_rate: float
    click_rate: float
