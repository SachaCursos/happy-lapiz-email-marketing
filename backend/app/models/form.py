from typing import Optional, Any
from datetime import datetime
from sqlmodel import Field, SQLModel, Column
from sqlalchemy import JSON, Text


class SignupForm(SQLModel, table=True):
    __tablename__ = "signup_forms"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    title: str
    description: Optional[str] = None
    button_text: str = Field(default="Suscribirme")
    success_message: str = Field(default="¡Gracias! Pronto recibirás noticias nuestras.")
    collect_name: bool = Field(default=True)
    collect_phone: bool = Field(default=False)
    # delay | exit_intent | scroll
    popup_trigger: str = Field(default="delay")
    popup_delay_seconds: int = Field(default=5)
    popup_scroll_pct: int = Field(default=50)
    # Custom fields: list of {key, label, type, required, placeholder, options}
    custom_form_fields: Optional[Any] = Field(default=None, sa_column=Column(JSON))
    # Full HTML override for popup content (null = use auto-generated)
    html_override: Optional[str] = Field(default=None, sa_column=Column(Text))
    # Coupon code shown in success screen (null = no coupon)
    coupon_code: Optional[str] = Field(default=None)
    # Visual design: {header_bg, header_bg2, header_text, body_bg, btn_bg, btn_text, border_radius, font}
    design_config: Optional[Any] = Field(default=None, sa_column=Column(JSON))
    # Multi-step: list of {step, title, description, fields, button_text}
    steps_config: Optional[Any] = Field(default=None, sa_column=Column(JSON))
    # Dynamic coupon: link to coupon_campaigns table
    coupon_campaign_id: Optional[int] = Field(default=None)
    # Automation to enroll on submission (for coupon email)
    coupon_automation_id: Optional[int] = Field(default=None)
    # A/B test variants: list of {id, title, description, button_text, weight}
    ab_variants: Optional[Any] = Field(default=None, sa_column=Column("ab_variants", JSON))
    # active | paused
    status: str = Field(default="active")
    created_by: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    # Aperturas/completados para la tasa solo cuentan desde esta fecha
    stats_since: Optional[datetime] = Field(default=None)


class FormSubmission(SQLModel, table=True):
    __tablename__ = "form_submissions"

    id: Optional[int] = Field(default=None, primary_key=True)
    form_id: int = Field(foreign_key="signup_forms.id", index=True)
    email: str
    name: Optional[str] = None
    phone: Optional[str] = None
    source_url: Optional[str] = None
    extra_data: Optional[Any] = Field(default=None, sa_column=Column(JSON))
    coupon_code: Optional[str] = Field(default=None)
    ab_variant: Optional[str] = Field(default=None)
    relacion_regalado: Optional[str] = Field(default=None)
    nombre_regalado: Optional[str] = Field(default=None)
    fecha_nacimiento_regalado: Optional[str] = Field(default=None)
    relacion_regalado2: Optional[str] = Field(default=None)
    nombre_regalado2: Optional[str] = Field(default=None)
    fecha_nacimiento_regalado2: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FormView(SQLModel, table=True):
    __tablename__ = "form_views"

    id: Optional[int] = Field(default=None, primary_key=True)
    form_id: int = Field(foreign_key="signup_forms.id", index=True)
    email: Optional[str] = Field(default=None, index=True)
    # page | embed
    source: str = Field(default="page")
    viewed_at: datetime = Field(default_factory=datetime.utcnow)


class SignupFormCreate(SQLModel):
    name: str
    title: str
    description: Optional[str] = None
    button_text: str = "Suscribirme"
    success_message: str = "¡Gracias! Pronto recibirás noticias nuestras."
    collect_name: bool = True
    collect_phone: bool = False
    popup_trigger: str = "delay"
    popup_delay_seconds: int = 5
    popup_scroll_pct: int = 50
    custom_form_fields: Optional[list] = None
    html_override: Optional[str] = None
    coupon_code: Optional[str] = None
    design_config: Optional[dict] = None
    steps_config: Optional[list] = None
    coupon_campaign_id: Optional[int] = None
    coupon_automation_id: Optional[int] = None
    ab_variants: Optional[list] = None


class SignupFormUpdate(SQLModel):
    name: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    button_text: Optional[str] = None
    success_message: Optional[str] = None
    collect_name: Optional[bool] = None
    collect_phone: Optional[bool] = None
    popup_trigger: Optional[str] = None
    popup_delay_seconds: Optional[int] = None
    popup_scroll_pct: Optional[int] = None
    custom_form_fields: Optional[list] = None
    html_override: Optional[str] = None
    coupon_code: Optional[str] = None
    status: Optional[str] = None
    design_config: Optional[dict] = None
    steps_config: Optional[list] = None
    coupon_campaign_id: Optional[int] = None
    coupon_automation_id: Optional[int] = None
    ab_variants: Optional[list] = None


class SignupFormRead(SQLModel):
    id: int
    name: str
    title: str
    description: Optional[str]
    button_text: str
    success_message: str
    collect_name: bool
    collect_phone: bool
    popup_trigger: str
    popup_delay_seconds: int
    popup_scroll_pct: int
    custom_form_fields: Optional[list]
    html_override: Optional[str]
    coupon_code: Optional[str]
    design_config: Optional[dict]
    steps_config: Optional[list]
    coupon_campaign_id: Optional[int]
    coupon_automation_id: Optional[int]
    ab_variants: Optional[list]
    status: str
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime
    stats_since: Optional[datetime] = None


class FormSubmitPayload(SQLModel):
    email: str
    name: Optional[str] = None
    phone: Optional[str] = None
    source_url: Optional[str] = None
    extra_data: Optional[dict] = None
    ab_variant: Optional[str] = None


class FormViewPayload(SQLModel):
    email: Optional[str] = None
    source: str = "page"
