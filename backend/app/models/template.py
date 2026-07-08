from typing import Optional, Any
from datetime import datetime
from sqlmodel import Field, SQLModel, Column
from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import JSONB


class Template(SQLModel, table=True):
    __tablename__ = "templates"

    id: Optional[int] = Field(default=None, primary_key=True)
    shop_id: Optional[int] = Field(default=None, foreign_key="shops.id", index=True)
    name: str = Field(index=True)
    subject_default: str = Field(default="")
    preview_text: Optional[str] = None
    html_content: str = Field(sa_column=Column(Text))
    json_blocks: Optional[Any] = Field(default=None, sa_column=Column(JSONB))
    created_by: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TemplateCreate(SQLModel):
    name: str
    subject_default: str = ""
    preview_text: Optional[str] = None
    html_content: str
    json_blocks: Optional[Any] = None


class TemplateUpdate(SQLModel):
    name: Optional[str] = None
    subject_default: Optional[str] = None
    preview_text: Optional[str] = None
    html_content: Optional[str] = None
    json_blocks: Optional[Any] = None


class TemplateRead(SQLModel):
    id: int
    name: str
    subject_default: Optional[str]
    preview_text: Optional[str]
    html_content: str
    json_blocks: Optional[Any]
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime
