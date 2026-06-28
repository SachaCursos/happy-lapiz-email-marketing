"""
Block-based email templates for Happy Lápiz.

All marketing templates MUST be defined as json_blocks (editor blocks), not monolithic HTML.
html_content is always compiled from blocks via blocks_to_html().
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from sqlmodel import Session, select

from app.models.template import Template
from app.models.user import User
from app.services.favorite_blocks_seed import (
    BIENVENIDA_NAME,
    BIENVENIDA_PREVIEW,
    BIENVENIDA_SUBJECT,
    GALERIA_NAME,
    GALERIA_PREVIEW,
    GALERIA_SUBJECT,
    VACACIONES_NAME,
    VACACIONES_PREVIEW,
    VACACIONES_SUBJECT,
    bienvenida_blocks,
    galeria_blocks,
    vacaciones_blocks,
)
from app.services.template_block_compiler import blocks_to_html

BlockListFn = Callable[[], list[dict]]

COMPOSITIONS: dict[str, BlockListFn] = {
    "vacaciones": vacaciones_blocks,
    "galeria": galeria_blocks,
    "bienvenida": bienvenida_blocks,
}

# Auto-upserted on startup / list templates (block editor source of truth)
MANAGED_BLOCK_TEMPLATES: list[dict] = [
    {
        "composition": "galeria",
        "name": GALERIA_NAME,
        "subject": GALERIA_SUBJECT,
        "preview": GALERIA_PREVIEW,
    },
    {
        "composition": "vacaciones",
        "name": VACACIONES_NAME,
        "subject": VACACIONES_SUBJECT,
        "preview": VACACIONES_PREVIEW,
    },
    {
        "composition": "bienvenida",
        "name": BIENVENIDA_NAME,
        "subject": BIENVENIDA_SUBJECT,
        "preview": BIENVENIDA_PREVIEW,
    },
]


def resolve_composition(composition: str) -> tuple[list[dict], str]:
    """Return (json_blocks, html_content) for a composition key."""
    fn = COMPOSITIONS.get(composition)
    if not fn:
        raise ValueError(f"Composición desconocida: {composition}")
    blocks = fn()
    return blocks, blocks_to_html(blocks)


def is_editor_block_list(blocks: object) -> bool:
    """True if json_blocks is a list of editor blocks (not plain-text mode)."""
    if not isinstance(blocks, list) or len(blocks) == 0:
        return False
    return all(isinstance(b, dict) and "type" in b and "props" in b for b in blocks)


def compile_template_payload(data: dict) -> dict:
    """If json_blocks is present, always derive html_content from blocks."""
    blocks = data.get("json_blocks")
    if is_editor_block_list(blocks):
        data = {**data, "html_content": blocks_to_html(blocks)}
    return data


def upsert_block_template(
    session: Session,
    *,
    name: str,
    subject: str,
    preview: str,
    blocks: list[dict],
    created_by: int | None = None,
) -> Template:
    now = datetime.utcnow()
    html = blocks_to_html(blocks)
    existing = session.exec(select(Template).where(Template.name == name)).first()
    if existing:
        existing.html_content = html
        existing.json_blocks = blocks
        existing.subject_default = subject
        existing.preview_text = preview
        existing.updated_at = now
        session.add(existing)
        session.flush()
        return existing
    tpl = Template(
        name=name,
        subject_default=subject,
        preview_text=preview,
        html_content=html,
        json_blocks=blocks,
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )
    session.add(tpl)
    session.flush()
    return tpl


def ensure_managed_block_templates(session: Session) -> None:
    """Create or refresh all block-based seed templates (idempotent)."""
    admin = session.exec(select(User).order_by(User.id)).first()
    admin_id = admin.id if admin else None
    for meta in MANAGED_BLOCK_TEMPLATES:
        blocks, _ = resolve_composition(meta["composition"])
        upsert_block_template(
            session,
            name=meta["name"],
            subject=meta["subject"],
            preview=meta["preview"],
            blocks=blocks,
            created_by=admin_id,
        )
    session.commit()


# Backward-compatible alias
ensure_catalog_templates = ensure_managed_block_templates
