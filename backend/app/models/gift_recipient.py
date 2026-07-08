from typing import Optional
from datetime import datetime, date
from sqlmodel import Field, SQLModel


RELACION_OPTIONS = [
    "hijo", "hija", "sobrino", "sobrina", "nieto", "nieta",
    "amigo", "amiga", "pareja", "mamá", "papá", "otro",
]


class GiftRecipient(SQLModel, table=True):
    __tablename__ = "gift_recipients"

    id: Optional[int] = Field(default=None, primary_key=True)
    shop_id: Optional[int] = Field(default=None, foreign_key="shops.id", index=True)
    email: str = Field(index=True)
    relacion: str
    nombre_regalado: str
    fecha_nacimiento_regalado: Optional[date] = None
    contact_id: Optional[int] = Field(default=None)
    source_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class GiftRecipientCreate(SQLModel):
    email: str
    relacion: str
    nombre_regalado: str
    fecha_nacimiento_regalado: Optional[date] = None
    source_url: Optional[str] = None
    shop_domain: Optional[str] = None  # ej: "mi-tienda.myshopify.com" — lo setea el embed JS


class GiftRecipientRead(SQLModel):
    id: int
    email: str
    relacion: str
    nombre_regalado: str
    fecha_nacimiento_regalado: Optional[date]
    contact_id: Optional[int]
    source_url: Optional[str]
    created_at: datetime
