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
    # Multi-step: [{step, delay_hours, subject, template_id, preview_text?}]
    # Step 1 delay_hours is always 0; steps 2+ delay_hours = hours after step 1 was sent.
    steps: Optional[Any] = Field(default=None, sa_column=Column(JSON))
    segment_id: Optional[int] = Field(default=None, foreign_key="segments.id")
    exclude_segment_ids: Optional[Any] = Field(default=None, sa_column=Column(JSON))
    sort_order: int = Field(default=0, index=True)
    status: str = Field(default="active")
    allow_resend: bool = Field(default=False)
    resend_after_days: Optional[int] = Field(default=None)
    min_days_inactive: int = Field(default=15)
    require_open_in_last_n: int = Field(default=5)
    created_by: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class EvergreenEnrollment(SQLModel, table=True):
    __tablename__ = "evergreen_enrollments"

    id: Optional[int] = Field(default=None, primary_key=True)
    evergreen_id: int = Field(foreign_key="evergreen_campaigns.id", index=True)
    contact_id: int = Field(foreign_key="contacts.id", index=True)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    next_step: int = Field(default=2)
    next_send_at: datetime
    status: str = Field(default="active")  # active | completed


class EvergreenSend(SQLModel, table=True):
    __tablename__ = "evergreen_sends"

    id: Optional[int] = Field(default=None, primary_key=True)
    evergreen_id: int = Field(foreign_key="evergreen_campaigns.id", index=True)
    contact_id: int = Field(foreign_key="contacts.id", index=True)
    enrollment_id: Optional[int] = Field(default=None, foreign_key="evergreen_enrollments.id")
    step_number: int = Field(default=1)
    resend_id: Optional[str] = Field(default=None, index=True)
    status: str = Field(default="queued")
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    clicked_at: Optional[datetime] = None
    bounced_at: Optional[datetime] = None


class EvergreenStepPayload(SQLModel):
    step: int
    delay_hours: float = 0
    subject: str
    template_id: int
    preview_text: Optional[str] = None


class EvergreenCampaignCreate(SQLModel):
    name: str
    subject: str
    preview_text: Optional[str] = None
    template_id: int
    steps: Optional[List[dict]] = None
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
    steps: Optional[List[dict]] = None
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
    steps: Optional[List[dict]]
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


def normalize_evergreen_steps(
    subject: str,
    template_id: int,
    preview_text: str | None,
    steps: list | None,
) -> list[dict]:
    """Build canonical steps list; step 1 mirrors top-level subject/template fields."""
    if steps:
        out = []
        for i, raw in enumerate(steps[:3]):
            out.append({
                "step": i + 1,
                "delay_hours": float(raw.get("delay_hours", 0)) if i > 0 else 0.0,
                "subject": str(raw.get("subject", subject if i == 0 else "")).strip(),
                "template_id": int(raw.get("template_id", template_id if i == 0 else 0)),
                "preview_text": raw.get("preview_text") or (preview_text if i == 0 else None),
            })
        if out and out[0]["step"] == 1:
            out[0]["subject"] = subject
            out[0]["template_id"] = template_id
            out[0]["delay_hours"] = 0.0
            if preview_text:
                out[0]["preview_text"] = preview_text
        return [s for s in out if s["subject"] and s["template_id"]]
    return [{
        "step": 1,
        "delay_hours": 0.0,
        "subject": subject,
        "template_id": template_id,
        "preview_text": preview_text,
    }]


def get_evergreen_steps(campaign: EvergreenCampaign) -> list[dict]:
    if campaign.steps:
        return campaign.steps
    return normalize_evergreen_steps(
        campaign.subject,
        campaign.template_id,
        campaign.preview_text,
        None,
    )
