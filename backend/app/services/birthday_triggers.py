"""SQL-filtered birthday candidate loaders (reduces Postgres egress)."""

from __future__ import annotations

from typing import Iterator

from sqlalchemy import text
from sqlmodel import Session, select

from app.models.contact import Contact
from app.models.form import FormSubmission
from app.services.regalado_vars import (
    get_regalado_field,
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


def iter_contacts_on_mmdd(
    session: Session,
    month: int,
    day: int,
    birthday_field: str = "fecha_nacimiento",
) -> Iterator[tuple[str, dict, Contact]]:
    """Opted-in contacts whose birthday matches month/day (JSON + form overlay).

    Distinct from the regalados-based iterators below: this is for reminding a
    contact about THEIR OWN birthday (data_source="contacts"), not a regalado's.
    """
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


# ── Regalados (gift-recipient birthdays) — contact.regalados is the single
# source of truth; these only differ in WHO is eligible per automation
# data_source config, not in where the regalado data itself comes from. ──────

def _form_emails(session: Session, form_id: int) -> set[str]:
    """Emails that submitted a specific signup form (data_source="form" scoping)."""
    rows = session.exec(
        select(FormSubmission.email).where(FormSubmission.form_id == int(form_id))
    ).all()
    return {(e or "").lower() for e in rows if e}


def iter_contacts_with_regalados(
    session: Session,
    *,
    month: int | None = None,
    day: int | None = None,
    emails: set[str] | None = None,
) -> Iterator[tuple[str, dict, Contact | None]]:
    """Opted-in contacts with a non-empty `regalados` list.

    month/day, if given, restrict to contacts with at least one regalado whose
    fecha_nacimiento matches that month/day. `emails`, if given (not None),
    restricts to that set — used to preserve a birthday automation's
    data_source="form" scoping to one specific form's submitters; pass None
    (the default) for the broad "gift_popup"/catch-all eligibility.
    """
    if emails is not None and not emails:
        return

    conditions = [
        "c.regalados IS NOT NULL",
        "jsonb_array_length(c.regalados) > 0",
        "c.opted_in = TRUE",
    ]
    params: dict = {}
    if month is not None and day is not None:
        conditions.append("""
            EXISTS (
                SELECT 1 FROM jsonb_array_elements(c.regalados) elem
                WHERE elem->>'fecha_nacimiento' ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
                  AND EXTRACT(MONTH FROM (elem->>'fecha_nacimiento')::date) = :month
                  AND EXTRACT(DAY FROM (elem->>'fecha_nacimiento')::date) = :day
            )
        """)
        params["month"] = month
        params["day"] = day
    if emails is not None:
        conditions.append("LOWER(c.email) = ANY(:emails)")
        params["emails"] = list(emails)

    rows = session.execute(
        text(f"SELECT id, email, regalados FROM contacts c WHERE {' AND '.join(conditions)}"),
        params,
    ).mappings().all()

    for row in rows:
        em = (row["email"] or "").lower()
        if not em:
            continue
        contact = session.get(Contact, row["id"])
        if not contact or not contact.opted_in:
            continue
        yield em, {"regalados": row["regalados"] or []}, contact


def iter_gift_flow_all(session: Session) -> Iterator[tuple[str, dict, Contact | None]]:
    """data_source="gift_popup": broad catch, any contact with regalado data
    (both the gift widget and the main signup form write into the same
    contact.regalados, so there's no need to distinguish the channel here)."""
    return iter_contacts_with_regalados(session)


def iter_form_all(session: Session, form_id: int) -> Iterator[tuple[str, dict, Contact | None]]:
    """data_source="form": only contacts who submitted that specific form."""
    return iter_contacts_with_regalados(session, emails=_form_emails(session, form_id))
