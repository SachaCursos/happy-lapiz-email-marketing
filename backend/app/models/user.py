from typing import Optional
from datetime import datetime
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    name: str
    password_hash: str
    role: str = Field(default="editor")  # admin | editor | viewer
    shop_id: Optional[int] = Field(default=None, foreign_key="shops.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserCreate(SQLModel):
    email: str
    name: str
    password: str
    role: str = "editor"


class UserRead(SQLModel):
    id: int
    email: str
    name: str
    role: str
    shop_id: Optional[int] = None
    created_at: datetime


class UserUpdate(SQLModel):
    name: Optional[str] = None
    role: Optional[str] = None
