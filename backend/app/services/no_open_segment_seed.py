"""Ensure the low-engagement (no opens in last N emails) segment exists."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from app.models.segment import Segment
from app.models.user import User
from app.services.segment_evaluator import count_segment

LAST_N_EMAILS = 5
SEGMENT_NAME = "No abrieron los ultimos 5 correos"
SEGMENT_DESCRIPTION = (
    "Contactos con al menos 5 envíos recientes y ninguna apertura en esos 5. "
    "Úsalo en «Excluir segmentos» al enviar."
)
SEGMENT_CONDITIONS = {
    "operator": "AND",
    "rules": [
        {"field": "no_open_in_last_n_emails", "op": "eq", "value": LAST_N_EMAILS},
    ],
}


def ensure_no_open_segment(session: Session) -> dict:
    existing = session.exec(select(Segment).where(Segment.name == SEGMENT_NAME)).first()
    now = datetime.utcnow()
    if existing:
        existing.description = SEGMENT_DESCRIPTION
        existing.conditions = SEGMENT_CONDITIONS
        existing.updated_at = now
        session.add(existing)
        session.commit()
        session.refresh(existing)
        seg = existing
        created = False
    else:
        admin = session.exec(select(User).order_by(User.id)).first()
        seg = Segment(
            name=SEGMENT_NAME,
            description=SEGMENT_DESCRIPTION,
            conditions=SEGMENT_CONDITIONS,
            created_by=admin.id if admin else None,
            created_at=now,
            updated_at=now,
        )
        session.add(seg)
        session.commit()
        session.refresh(seg)
        created = True

    contact_count = count_segment(seg.conditions, session)
    return {
        "segment_id": seg.id,
        "segment_name": seg.name,
        "created": created,
        "contact_count": contact_count,
    }
