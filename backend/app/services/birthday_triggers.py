"""SQL-filtered birthday candidate loaders (reduces Postgres egress)."""

from __future__ import annotations

from datetime import date
from typing import Iterator

from sqlalchemy import text
from sqlmodel import Session, select

from app.models.contact import Contact
from app.models.form import FormSubmission
from app.models.gift_recipient import GiftRecipient
from app.services.regalado_vars import (
    get_regalado_field,
    gift_recipient_to_regalado_dict,
    merge_regalado_sources,
    submission_to_regalado_dict,
)


def _contact_allowed(session: Session, email: str) -> tuple[bool, Contact | None]:
    contact = session.exec(
        select(Contact).where(Contact.email == email.lower())
    ).first()
    if contact and not contact.opted_in:
        return False, contact
    return True, contact


def iter_gift_popup_on_mmdd(
    session: Session, month: int, day: int
) -> Iterator[tuple[str, dict, Contact | None]]:
    rows = session.execute(
        text("""
            SELECT DISTINCT ON (LOWER(email))
                email, nombre_regalado, relacion, fecha_nacimiento_regalado
            FROM gift_recipients
            WHERE fecha_nacimiento_regalado IS NOT NULL
              AND EXTRACT(MONTH FROM fecha_nacimiento_regalado) = :month
              AND EXTRACT(DAY FROM fecha_nacimiento_regalado) = :day
            ORDER BY LOWER(email), created_at DESC
        """),
        {"month": month, "day": day},
    ).mappings().all()

    for row in rows:
        em = (row["email"] or "").lower()
        if not em:
            continue
        allowed, contact = _contact_allowed(session, em)
        if not allowed:
            continue
        gr = GiftRecipient(
            email=em,
            nombre_regalado=row["nombre_regalado"] or "",
            relacion=row["relacion"] or "",
            fecha_nacimiento_regalado=row["fecha_nacimiento_regalado"],
        )
        yield em, gift_recipient_to_regalado_dict(gr), contact


def iter_form_on_mmdd(
    session: Session, form_id: int, month: int, day: int
) -> Iterator[tuple[str, dict, Contact | None]]:
    mm = f"{month:02d}"
    dd = f"{day:02d}"
    patterns = (f"%-{mm}-{dd}", f"%-{dd}-{mm}", f"%/{mm}/{dd}", f"%/{dd}/{mm}")

    rows = session.exec(
        select(FormSubmission)
        .where(FormSubmission.form_id == int(form_id))
        .where(
            text(
                "("
                "fecha_nacimiento_regalado LIKE ANY (ARRAY[:p1,:p2,:p3,:p4]) OR "
                "fecha_nacimiento_regalado2 LIKE ANY (ARRAY[:p1,:p2,:p3,:p4])"
                ")"
            ).bindparams(p1=patterns[0], p2=patterns[1], p3=patterns[2], p4=patterns[3])
        )
        .order_by(FormSubmission.created_at.desc())
    ).all()

    seen: set[str] = set()
    for sub in rows:
        em = (sub.email or "").lower()
        if not em or em in seen:
            continue
        seen.add(em)
        allowed, contact = _contact_allowed(session, em)
        if not allowed:
            continue
        yield em, submission_to_regalado_dict(sub), contact


def iter_contacts_on_mmdd(
    session: Session,
    month: int,
    day: int,
    birthday_field: str = "fecha_nacimiento",
) -> Iterator[tuple[str, dict, Contact]]:
    """Opted-in contacts whose birthday matches month/day (JSON + form overlay)."""
    mm = f"{month:02d}"
    dd = f"{day:02d}"
    pattern = f"%-{mm}-{dd}"

    contacts = session.exec(
        select(Contact).where(Contact.opted_in == True)  # noqa: E712
        .where(
            text(
                "(custom_fields::text LIKE :p1 OR custom_fields::text LIKE :p2 "
                "OR custom_fields::text LIKE :p3)"
            ).bindparams(
                p1=f'%"fecha_nacimiento": "%{mm}-{dd}"%',
                p2=f'%"fecha_nacimiento_regalado": "%{mm}-{dd}"%',
                p3=f'%"fecha_nacimiento": "{mm}-{dd}"%',
            )
        )
    ).all()

    subs_by_email: dict[str, FormSubmission] = {}
    for sub in session.exec(
        select(FormSubmission)
        .where(
            text(
                "(fecha_nacimiento_regalado IS NOT NULL "
                "AND fecha_nacimiento_regalado LIKE :p) "
                "OR (fecha_nacimiento_regalado2 IS NOT NULL "
                "AND fecha_nacimiento_regalado2 LIKE :p)"
            ).bindparams(p=pattern)
        )
        .order_by(FormSubmission.created_at.desc())
    ):
        em = (sub.email or "").lower()
        if em and em not in subs_by_email:
            subs_by_email[em] = sub

    seen: set[str] = set()
    for contact in contacts:
        em = contact.email.lower()
        if em in seen:
            continue
        cf = contact.custom_fields or {}
        if isinstance(cf, str):
            import json
            try:
                cf = json.loads(cf)
            except Exception:
                cf = {}
        sub = subs_by_email.get(em)
        data = merge_regalado_sources(cf if isinstance(cf, dict) else {}, sub)
        if not get_regalado_field(data, birthday_field):
            continue
        seen.add(em)
        yield em, data, contact

    for em, sub in subs_by_email.items():
        if em in seen:
            continue
        data = submission_to_regalado_dict(sub)
        if not get_regalado_field(data, birthday_field):
            continue
        contact = session.exec(select(Contact).where(Contact.email == em)).first()
        if not contact or not contact.opted_in:
            continue
        seen.add(em)
        yield em, data, contact


def iter_gift_popup_all(session: Session) -> Iterator[tuple[str, dict, Contact | None]]:
    """Latest gift recipient per email (light columns only) — for will_enter counts."""
    rows = session.execute(
        text("""
            SELECT DISTINCT ON (LOWER(email))
                email, nombre_regalado, relacion, fecha_nacimiento_regalado
            FROM gift_recipients
            WHERE fecha_nacimiento_regalado IS NOT NULL
            ORDER BY LOWER(email), created_at DESC
        """)
    ).mappings().all()

    for row in rows:
        em = (row["email"] or "").lower()
        if not em:
            continue
        allowed, contact = _contact_allowed(session, em)
        if not allowed:
            continue
        gr = GiftRecipient(
            email=em,
            nombre_regalado=row["nombre_regalado"] or "",
            relacion=row["relacion"] or "",
            fecha_nacimiento_regalado=row["fecha_nacimiento_regalado"],
        )
        yield em, gift_recipient_to_regalado_dict(gr), contact


def iter_form_all(
    session: Session, form_id: int
) -> Iterator[tuple[str, dict, Contact | None]]:
    seen: set[str] = set()
    for sub in session.exec(
        select(FormSubmission)
        .where(FormSubmission.form_id == int(form_id))
        .order_by(FormSubmission.created_at.desc())
    ):
        em = (sub.email or "").lower()
        if not em or em in seen:
            continue
        if not sub.fecha_nacimiento_regalado and not sub.fecha_nacimiento_regalado2:
            continue
        seen.add(em)
        allowed, contact = _contact_allowed(session, em)
        if not allowed:
            continue
        yield em, submission_to_regalado_dict(sub), contact
