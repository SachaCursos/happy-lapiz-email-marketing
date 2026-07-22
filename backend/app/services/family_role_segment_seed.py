"""Ensure dynamic family-role segments (Mamás, Papás, Abuelas, …) exist.

These filter contacts.family_role inferred from form gift relationships,
so they grow automatically as new forms are submitted.
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from app.models.segment import Segment
from app.models.user import User
from app.services.segment_evaluator import count_segment

# (segment name, family_role value, description)
FAMILY_ROLE_SEGMENTS = [
    (
        "Mamás",
        "madre",
        "Contactos identificados como madre desde el formulario de regalados (family_role=madre). Crece con cada envío.",
    ),
    (
        "Papás",
        "padre",
        "Contactos identificados como padre desde el formulario de regalados (family_role=padre). Crece con cada envío.",
    ),
    (
        "Abuelas",
        "abuela",
        "Contactos identificados como abuela desde el formulario de regalados (family_role=abuela). Crece con cada envío.",
    ),
    (
        "Abuelos",
        "abuelo",
        "Contactos identificados como abuelo desde el formulario de regalados (family_role=abuelo). Crece con cada envío.",
    ),
    (
        "Tías",
        "tia",
        "Contactos identificados como tía desde el formulario de regalados (family_role=tia). Crece con cada envío.",
    ),
    (
        "Tíos",
        "tio",
        "Contactos identificados como tío desde el formulario de regalados (family_role=tio). Crece con cada envío.",
    ),
]


def _conditions_for_role(role: str) -> dict:
    return {
        "operator": "AND",
        "rules": [
            {"field": "opted_in", "op": "eq", "value": True},
            {"field": "family_role", "op": "eq", "value": role},
        ],
    }


def ensure_family_role_segments(session: Session) -> list[dict]:
    """Upsert Mamás/Papás/Abuelas/Abuelos/Tías/Tíos segments on family_role."""
    admin = session.exec(select(User).order_by(User.id)).first()
    admin_id = admin.id if admin else None
    now = datetime.utcnow()
    results: list[dict] = []

    for name, role, description in FAMILY_ROLE_SEGMENTS:
        conditions = _conditions_for_role(role)
        existing = session.exec(select(Segment).where(Segment.name == name)).first()
        created = False
        if existing:
            existing.description = description
            existing.conditions = conditions
            existing.updated_at = now
            session.add(existing)
            seg = existing
        else:
            seg = Segment(
                name=name,
                description=description,
                conditions=conditions,
                created_by=admin_id,
                created_at=now,
                updated_at=now,
            )
            session.add(seg)
            created = True
        session.commit()
        session.refresh(seg)
        results.append({
            "segment_id": seg.id,
            "segment_name": seg.name,
            "family_role": role,
            "created": created,
            "contact_count": count_segment(seg.conditions, session),
        })

    return results
