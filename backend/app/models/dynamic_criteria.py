from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class DynamicCriteria(SQLModel, table=True):
    __tablename__ = "dynamic_criteria"

    criteria_key: str = Field(primary_key=True)
    name: str
    description: Optional[str] = None
    variables: Optional[Any] = Field(default=None, sa_column=Column(JSON))
    config: Any = Field(default_factory=dict, sa_column=Column(JSON))
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DynamicCriteriaRead(SQLModel):
    criteria_key: str
    name: str
    description: Optional[str] = None
    variables: list[str] = []
    config: dict = {}
    updated_at: datetime


class DynamicCriteriaUpdate(SQLModel):
    config: dict
