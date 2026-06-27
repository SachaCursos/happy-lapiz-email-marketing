import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session

from app.core.deps import get_current_user, require_editor
from app.database import get_session
from app.models.html_block import DynamicHtmlBlockRead, DynamicHtmlBlockUpdate
from app.models.user import User
from app.services.dynamic_html_blocks import (
    DEFAULT_BLOCKS,
    preview_html_block,
    seed_default_blocks,
)

router = APIRouter()


class PreviewPayload(BaseModel):
    html_template: str | None = None
    design_config: dict | None = None
    sample_products: list | None = None
    btn_color: str = "#f97316"


def _row_to_read(row) -> DynamicHtmlBlockRead:
    return DynamicHtmlBlockRead(
        block_key=row[0],
        name=row[1],
        description=row[2],
        html_template=row[3],
        design_config=row[4],
        sample_products=row[5],
        updated_at=row[6],
    )


_SELECT_COLS = """
    SELECT block_key, name, description, html_template, design_config, sample_products, updated_at
"""


@router.get("", response_model=list[DynamicHtmlBlockRead])
def list_html_blocks(session: Session = Depends(get_session), _: User = Depends(get_current_user)):
    seed_default_blocks(session)
    rows = session.execute(
        text(f"{_SELECT_COLS} FROM dynamic_html_blocks ORDER BY name")
    ).fetchall()
    return [_row_to_read(r) for r in rows]


@router.get("/{block_key}", response_model=DynamicHtmlBlockRead)
def get_html_block(block_key: str, session: Session = Depends(get_session), _: User = Depends(get_current_user)):
    seed_default_blocks(session)
    row = session.execute(
        text(f"{_SELECT_COLS} FROM dynamic_html_blocks WHERE block_key = :k"),
        {"k": block_key},
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Bloque no encontrado")
    return _row_to_read(row)


@router.patch("/{block_key}", response_model=DynamicHtmlBlockRead)
def update_html_block(
    block_key: str,
    payload: DynamicHtmlBlockUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_editor),
):
    seed_default_blocks(session)
    existing = session.execute(
        text("SELECT 1 FROM dynamic_html_blocks WHERE block_key = :k"),
        {"k": block_key},
    ).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Bloque no encontrado")

    updates = []
    params: dict = {"k": block_key, "now": datetime.utcnow()}
    if payload.html_template is not None:
        updates.append("html_template = :tpl")
        params["tpl"] = payload.html_template
    if payload.design_config is not None:
        updates.append("design_config = CAST(:design AS jsonb)")
        params["design"] = json.dumps(payload.design_config, ensure_ascii=False)
    if payload.sample_products is not None:
        updates.append("sample_products = CAST(:samples AS jsonb)")
        params["samples"] = json.dumps(payload.sample_products, ensure_ascii=False)
    if not updates:
        return get_html_block(block_key, session, current_user)

    updates.append("updated_at = :now")
    session.execute(
        text(f"UPDATE dynamic_html_blocks SET {', '.join(updates)} WHERE block_key = :k"),
        params,
    )
    session.commit()
    return get_html_block(block_key, session, current_user)


@router.post("/{block_key}/preview")
def preview_block(
    block_key: str,
    payload: PreviewPayload,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    if block_key not in DEFAULT_BLOCKS:
        seed_default_blocks(session)
    html = preview_html_block(
        session,
        block_key,
        html_template=payload.html_template,
        sample_products=payload.sample_products,
        btn_color=payload.btn_color,
    )
    return {"html": html}


@router.get("/meta/variables")
def block_variables(_: User = Depends(get_current_user)):
    """Documentación de variables disponibles en plantillas de bloques."""
    return {
        "variables": [
            {"name": "products", "description": "Lista de productos [{title, url, image_url, price, handle}]"},
            {"name": "product_rows", "description": "Productos agrupados de a 2 para filas de grilla"},
            {"name": "btn_color", "description": "Color del botón (hex), ej. #f97316 — legacy, el diseño visual define btn_bg"},
            {"name": "descuento_producto_mes", "description": "Porcentaje de descuento (producto del mes)"},
            {"name": "p.title", "description": "Dentro de {% for p in row %}: nombre del producto"},
            {"name": "p.url", "description": "URL del producto en happylapiz.cl"},
            {"name": "p.image_url", "description": "Imagen del producto"},
            {"name": "p.price", "description": "Precio formateado"},
        ],
    }
