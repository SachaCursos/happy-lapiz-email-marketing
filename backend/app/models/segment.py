from typing import Optional, Any, Dict
from datetime import datetime
from sqlmodel import Field, SQLModel, Column
from sqlalchemy.dialects.postgresql import JSONB

# Formato de conditions:
# {
#   "operator": "AND",
#   "rules": [
#     {"field": "orders_count", "op": "gte", "value": 2},
#     {"field": "total_spent",  "op": "gte", "value": 50000}
#   ]
# }


class Segment(SQLModel, table=True):
    __tablename__ = "segments"

    id: Optional[int] = Field(default=None, primary_key=True)
    shop_id: Optional[int] = Field(default=None, foreign_key="shops.id", index=True)
    name: str = Field(index=True)
    description: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = Field(
        default=None, sa_column=Column(JSONB)
    )
    created_by: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SegmentCreate(SQLModel):
    name: str
    description: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None


class SegmentUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None


class SegmentRead(SQLModel):
    id: int
    name: str
    description: Optional[str]
    conditions: Optional[Dict[str, Any]]
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime
    contact_count: Optional[int] = None
