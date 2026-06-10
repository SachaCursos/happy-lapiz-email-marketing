from typing import Optional, Any
from datetime import datetime
from sqlmodel import Field, SQLModel, Column
from sqlalchemy import JSON


class Automation(SQLModel, table=True):
    __tablename__ = "automations"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    # abandoned_booking | welcome | post_visit | reactivation
    trigger_type: str
    trigger_config: Optional[Any] = Field(default=None, sa_column=Column(JSON))
    template_id: int = Field(foreign_key="templates.id")
    subject: str
    # active | paused
    status: str = Field(default="active")
    created_by: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AutomationRun(SQLModel, table=True):
    __tablename__ = "automation_runs"

    id: Optional[int] = Field(default=None, primary_key=True)
    automation_id: int = Field(foreign_key="automations.id", index=True)
    contact_id: Optional[int] = Field(default=None, foreign_key="contacts.id", index=True)
    contact_email: str
    # Unique string per trigger event — prevents double-send
    trigger_key: str = Field(index=True)
    # sent | failed | skipped
    status: str = Field(default="sent")
    triggered_at: datetime = Field(default_factory=datetime.utcnow)
    executed_at: Optional[datetime] = None
    resend_id: Optional[str] = None
    error: Optional[str] = None


class AutomationCreate(SQLModel):
    name: str
    trigger_type: str
    trigger_config: Optional[dict] = None
    template_id: int
    subject: str


class AutomationUpdate(SQLModel):
    name: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_config: Optional[dict] = None
    template_id: Optional[int] = None
    subject: Optional[str] = None
    status: Optional[str] = None


class AutomationRead(SQLModel):
    id: int
    name: str
    trigger_type: str
    trigger_config: Optional[dict]
    template_id: Optional[int]
    subject: Optional[str]
    status: str
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime


class AutomationRunRead(SQLModel):
    id: int
    automation_id: int
    contact_id: Optional[int]
    contact_email: str
    trigger_key: str
    status: str
    triggered_at: datetime
    executed_at: Optional[datetime]
    resend_id: Optional[str]
    error: Optional[str]
