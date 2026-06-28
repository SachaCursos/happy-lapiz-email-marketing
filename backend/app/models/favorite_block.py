from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class FavoriteBlock(SQLModel, table=True):
    __tablename__ = "favorite_blocks"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    block_type: str
    props: Any = Field(sa_column=Column(JSONB))
    sort_order: int = Field(default=0)
    created_by: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class FavoriteBlockCreate(SQLModel):
    name: str
    block_type: str
    props: dict
    sort_order: int = 0


class FavoriteBlockUpdate(SQLModel):
    name: Optional[str] = None
    block_type: Optional[str] = None
    props: Optional[dict] = None
    sort_order: Optional[int] = None


class FavoriteBlockRead(SQLModel):
    id: int
    name: str
    block_type: str
    props: dict
    sort_order: int
    created_at: datetime
    updated_at: datetime
