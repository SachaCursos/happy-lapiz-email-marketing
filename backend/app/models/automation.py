from typing import Optional, Any, List
from datetime import datetime
from sqlmodel import Field, SQLModel, Column
from sqlalchemy import JSON


class Automation(SQLModel, table=True):
    __tablename__ = "automations"

    id: Optional[int] = Field(default=None, primary_key=True)
    shop_id: Optional[int] = Field(default=None, foreign_key="shops.id", index=True)
    name: str = Field(index=True)
    trigger_type: str
    trigger_config: Optional[Any] = Field(default=None, sa_column=Column(JSON))
    # Legacy single-step fields (kept for backwards compat)
    template_id: Optional[int] = Field(default=None, foreign_key="templates.id")
    subject: Optional[str] = Field(default=None)
    # Multi-step: list of {step, delay_hours, template_id, subject, condition, variants?}
    steps: Optional[Any] = Field(default=None, sa_column=Column("steps", JSON))
    status: str = Field(default="active")
    # Optional dynamic coupon campaign to attach to every email in this automation
    coupon_campaign_id: Optional[int] = Field(default=None)
    created_by: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AutomationEnrollment(SQLModel, table=True):
    __tablename__ = "automation_enrollments"

    id: Optional[int] = Field(default=None, primary_key=True)
    shop_id: Optional[int] = Field(default=None, foreign_key="shops.id", index=True)
    automation_id: int = Field(foreign_key="automations.id", index=True)
    contact_email: str = Field(index=True)
    trigger_key: str = Field(index=True)
    enrolled_at: datetime = Field(default_factory=datetime.utcnow)
    next_send_at: datetime
    next_step: int = Field(default=1)
    # active | completed | converted | cancelled
    status: str = Field(default="active")
    # JSON-encoded extra vars to carry across steps (cart_url, order_number, etc.)
    extra_vars_json: Optional[str] = Field(default=None)


class AutomationRun(SQLModel, table=True):
    __tablename__ = "automation_runs"

    id: Optional[int] = Field(default=None, primary_key=True)
    shop_id: Optional[int] = Field(default=None, foreign_key="shops.id", index=True)
    automation_id: int = Field(foreign_key="automations.id", index=True)
    contact_id: Optional[int] = Field(default=None, foreign_key="contacts.id", index=True)
    contact_email: str
    trigger_key: str = Field(index=True)
    step_number: int = Field(default=1)
    status: str = Field(default="sent")
    triggered_at: datetime = Field(default_factory=datetime.utcnow)
    executed_at: Optional[datetime] = None
    resend_id: Optional[str] = None
    error: Optional[str] = None
    opened_at: Optional[datetime] = None
    clicked_at: Optional[datetime] = None
    variant_sent: Optional[str] = None  # A/B test variant label ("A", "B", etc.)


class AutomationCreate(SQLModel):
    name: str
    trigger_type: str
    trigger_config: Optional[dict] = None
    # Multi-step (preferred)
    steps: Optional[List[dict]] = None
    # Legacy single-step (kept for compat)
    template_id: Optional[int] = None
    subject: Optional[str] = None
    coupon_campaign_id: Optional[int] = None


class AutomationUpdate(SQLModel):
    name: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_config: Optional[dict] = None
    steps: Optional[List[dict]] = None
    template_id: Optional[int] = None
    subject: Optional[str] = None
    status: Optional[str] = None
    coupon_campaign_id: Optional[int] = None


class AutomationRead(SQLModel):
    id: int
    name: str
    trigger_type: str
    trigger_config: Optional[dict]
    steps: Optional[List[dict]]
    template_id: Optional[int]
    subject: Optional[str]
    status: str
    coupon_campaign_id: Optional[int]
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime


class AutomationRunRead(SQLModel):
    id: int
    automation_id: int
    contact_id: Optional[int]
    contact_email: str
    trigger_key: str
    step_number: int = 1
    status: str
    triggered_at: datetime
    executed_at: Optional[datetime]
    resend_id: Optional[str]
    error: Optional[str]
    opened_at: Optional[datetime] = None
    clicked_at: Optional[datetime] = None
    variant_sent: Optional[str] = None


class AutomationEnrollmentRead(SQLModel):
    id: int
    automation_id: int
    contact_email: str
    trigger_key: str
    enrolled_at: datetime
    next_send_at: datetime
    next_step: int
    status: str
