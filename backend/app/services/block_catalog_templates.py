"""Ensure block-catalog reference templates exist (gallery, etc.)."""

from datetime import datetime

from sqlmodel import Session, select

from app.models.template import Template
from app.models.user import User
from app.services.favorite_blocks_seed import (
    GALERIA_NAME,
    GALERIA_PREVIEW,
    GALERIA_SUBJECT,
    galeria_blocks,
)
from app.services.template_block_compiler import blocks_to_html


def ensure_catalog_templates(session: Session) -> None:
    """Create or refresh the gallery template so it appears in Plantillas."""
    now = datetime.utcnow()
    admin = session.exec(select(User).order_by(User.id)).first()
    admin_id = admin.id if admin else None

    blocks = galeria_blocks()
    html = blocks_to_html(blocks)

    existing = session.exec(select(Template).where(Template.name == GALERIA_NAME)).first()
    if existing:
        existing.html_content = html
        existing.json_blocks = blocks
        existing.subject_default = GALERIA_SUBJECT
        existing.preview_text = GALERIA_PREVIEW
        existing.updated_at = now
        session.add(existing)
    else:
        session.add(
            Template(
                name=GALERIA_NAME,
                subject_default=GALERIA_SUBJECT,
                preview_text=GALERIA_PREVIEW,
                html_content=html,
                json_blocks=blocks,
                created_by=admin_id,
                created_at=now,
                updated_at=now,
            )
        )
    session.commit()
