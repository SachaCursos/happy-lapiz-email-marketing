from typing import Optional
from datetime import datetime
from sqlmodel import Field, SQLModel


class BrandAsset(SQLModel, table=True):
    __tablename__ = "plantillas_de_la_marca"

    id: Optional[int] = Field(default=None, primary_key=True)
    shop_id: Optional[int] = Field(default=None, foreign_key="shops.id", index=True)
    categoria: str  # color | logo | tipografia
    nombre: str
    valor: str
    descripcion: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BrandAssetCreate(SQLModel):
    categoria: str
    nombre: str
    valor: str
    descripcion: Optional[str] = None


class BrandAssetUpdate(SQLModel):
    nombre: Optional[str] = None
    valor: Optional[str] = None
    descripcion: Optional[str] = None


class BrandAssetRead(SQLModel):
    id: int
    categoria: str
    nombre: str
    valor: str
    descripcion: Optional[str] = None
