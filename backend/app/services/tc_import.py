"""
Import sign-ups from a Google Form CSV export.

For each row:
  1. Resolve the best email from the 3 possible email columns.
  2. Parse Marca temporal.
  3. Upsert into contacts with opted_in=True.
"""
import csv
import io
import logging
from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from app.models.contact import Contact

logger = logging.getLogger(__name__)

_COL_TS       = "Marca temporal"
_COL_NAME     = "Nombre"
_COL_BDAY     = "Fecha de nacimiento"
_COL_EMAIL1   = "Email"
_COL_EMAIL2   = "Dirección de correo electrónico"
_COL_EMAIL3   = "email (si iniciaste sesión puedes dejarlo vacio)"
_COL_PHONE    = "Teléfono"
_COL_ACCEPTED = "Acepto Términos y Condiciones\nI Accept Terms and Conditions"


def _best_email(row: dict) -> Optional[str]:
    for col in [_COL_EMAIL2, _COL_EMAIL3, _COL_EMAIL1]:
        val = (row.get(col) or "").strip().lower()
        if val and "@" in val:
            return val
    return None


def _parse_date(raw: str) -> Optional[object]:
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    return None


def import_tc_csv(content: bytes, session: Session) -> dict:
    text_io = io.StringIO(content.decode("utf-8-sig"))
    reader = csv.DictReader(text_io)

    created = updated = skipped = 0

    for row in reader:
        email = _best_email(row)
        if not email:
            skipped += 1
            continue

        accepted = " ".join((row.get(_COL_ACCEPTED) or "").strip().lower().split())
        if accepted not in ("sí", "si", "yes"):
            skipped += 1
            continue

        name     = (row.get(_COL_NAME) or "").strip() or None
        phone    = (row.get(_COL_PHONE) or "").strip() or None
        birthday = _parse_date(row.get(_COL_BDAY) or "")
        now      = datetime.utcnow()

        existing = session.exec(select(Contact).where(Contact.email == email)).first()

        if existing:
            if name and not existing.name:
                existing.name = name
            if phone and not existing.phone:
                existing.phone = phone
            if birthday and not existing.birthday:
                existing.birthday = birthday
            existing.opted_in = True
            if not existing.opted_in_at:
                existing.opted_in_at = now
            existing.updated_at = now
            session.add(existing)
            updated += 1
        else:
            session.add(Contact(
                email       = email,
                name        = name,
                phone       = phone,
                birthday    = birthday,
                origin_utm  = "Formulario T&C",
                opted_in    = True,
                opted_in_at = now,
            ))
            created += 1

    session.commit()
    result = {"created": created, "updated": updated, "skipped": skipped}
    logger.info("TC import: %s", result)
    return result
