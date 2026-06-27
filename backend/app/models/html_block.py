from typing import Optional, Any
from datetime import datetime
from sqlmodel import Field, SQLModel, Column
from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import JSONB


class DynamicHtmlBlock(SQLModel, table=True):
    __tablename__ = "dynamic_html_blocks"

    block_key: str = Field(primary_key=True)
    name: str
    description: Optional[str] = None
    html_template: str = Field(sa_column=Column(Text))
    sample_products: Optional[Any] = Field(default=None, sa_column=Column(JSONB))
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DynamicHtmlBlockUpdate(SQLModel):
    html_template: Optional[str] = None
    sample_products: Optional[list] = None


class DynamicHtmlBlockRead(SQLModel):
    block_key: str
    name: str
    description: Optional[str]
    html_template: str
    sample_products: Optional[list]
    updated_at: datetime
