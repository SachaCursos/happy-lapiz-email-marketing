"""Infer and persist contact family role from form relationships + gender.

Roles stored on contacts.family_role (singular, Spanish lowercase):
  madre | padre | abuela | abuelo | tia | tio | madrina | padrino |
  hermana | hermano | otro
"""
from __future__ import annotations

import json
import logging
import unicodedata
from typing import Iterable

from sqlalchemy import text
from sqlmodel import Session, select

from app.models.contact import Contact

logger = logging.getLogger(__name__)

FAMILY_ROLES = frozenset({
    "madre", "padre",
    "abuela", "abuelo",
    "tia", "tio",
    "madrina", "padrino",
    "hermana", "hermano",
    "otro",
})

# Prefer closer family when a contact has multiple relationships over time.
_ROLE_PRIORITY = {
    "madre": 1, "padre": 1,
    "abuela": 2, "abuelo": 2,
    "tia": 3, "tio": 3,
    "madrina": 4, "padrino": 4,
    "hermana": 5, "hermano": 5,
    "otro": 9,
}


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def _norm(s: str) -> str:
    return _strip_accents((s or "").lower().strip())


def infer_family_role_from_relacion(relacion: str, gender: str | None) -> str | None:
    """Map 'Para mi hijo/nieto/…' + submitter gender → family_role."""
    r = _norm(relacion)
    if not r:
        return None

    g = (gender or "").upper() if gender else None
    if g not in ("M", "F"):
        g = None

    def pick(female: str, male: str) -> str:
        if g == "F":
            return female
        if g == "M":
            return male
        # Unknown gender: prefer feminine label only when ambiguous? Use generic pair default
        # Prefer the more common role for that relationship in our data (mothers/grandmothers).
        return female

    # Order matters: "ahijado" contains "hijo"; "sobrina" before generic checks.
    if "ahijad" in r:
        return pick("madrina", "padrino")
    if "sobrino" in r or "sobrina" in r:
        return pick("tia", "tio")
    if "nieto" in r or "nieta" in r:
        return pick("abuela", "abuelo")
    if "hijo" in r or "hija" in r:
        return pick("madre", "padre")
    if "hermano" in r or "hermana" in r:
        return pick("hermana", "hermano")
    if r in ("para mi", "para mí", "yo") or "para mi mismo" in r or "para mi misma" in r:
        return "otro"
    if "amigo" in r or "amiga" in r or "otro" in r or "otra" in r:
        return "otro"
    return "otro"


def extract_relaciones_from_submission(
    *,
    relacion_regalado: str | None = None,
    relacion_regalado2: str | None = None,
    extra_data: dict | list | str | None = None,
    regalados: list[dict] | None = None,
) -> list[str]:
    """Collect relationship labels from a form submission."""
    out: list[str] = []
    if regalados:
        for r in regalados:
            rel = (r.get("relacion") or r.get("para_quien") or "").strip()
            if rel:
                out.append(rel)
    ed = extra_data
    if isinstance(ed, str):
        try:
            ed = json.loads(ed)
        except Exception:
            ed = {}
    if isinstance(ed, dict):
        for r in ed.get("regalados") or []:
            if isinstance(r, dict):
                rel = (r.get("para_quien") or r.get("relacion") or "").strip()
                if rel:
                    out.append(rel)
        for r in ed.get("regalados_extra") or []:
            if isinstance(r, dict):
                rel = (r.get("para_quien") or r.get("relacion") or "").strip()
                if rel:
                    out.append(rel)
        if not out and ed.get("para_quien"):
            out.append(str(ed["para_quien"]).strip())
    if not out:
        if relacion_regalado:
            out.append(relacion_regalado.strip())
        if relacion_regalado2:
            out.append(relacion_regalado2.strip())
    # dedupe preserving order
    seen: set[str] = set()
    uniq: list[str] = []
    for rel in out:
        key = _norm(rel)
        if key and key not in seen:
            seen.add(key)
            uniq.append(rel)
    return uniq


def pick_primary_family_role(roles: Iterable[str | None]) -> str | None:
    """Choose one role when multiple relationships exist."""
    best: str | None = None
    best_pri = 99
    for role in roles:
        if not role or role not in FAMILY_ROLES:
            continue
        pri = _ROLE_PRIORITY.get(role, 99)
        if pri < best_pri:
            best = role
            best_pri = pri
    return best


def infer_family_role(
    *,
    name: str | None,
    gender: str | None,
    relaciones: list[str],
) -> str | None:
    """Infer family_role from submitter gender + gift relationships."""
    from app.services.automation_engine import _detect_name_gender

    g = gender if gender in ("M", "F") else _detect_name_gender(name or "")
    roles = [infer_family_role_from_relacion(rel, g) for rel in relaciones]
    return pick_primary_family_role(roles)


def apply_family_role_to_contact(
    contact: Contact,
    *,
    relaciones: list[str],
    name: str | None = None,
) -> str | None:
    """Update contact.family_role (and gender if missing). Returns new role or None."""
    from app.services.automation_engine import _detect_name_gender

    if not contact.gender:
        detected = _detect_name_gender(name or contact.name or "")
        if detected:
            contact.gender = detected

    role = infer_family_role(
        name=name or contact.name,
        gender=contact.gender,
        relaciones=relaciones,
    )
    if not role:
        return None

    # Keep closer relationship if already set to a higher-priority role
    existing = getattr(contact, "family_role", None)
    if existing and existing in FAMILY_ROLES:
        if _ROLE_PRIORITY.get(existing, 99) <= _ROLE_PRIORITY.get(role, 99):
            return existing

    contact.family_role = role
    return role


def backfill_family_roles(session: Session) -> dict:
    """Populate contacts.family_role from historical form_submissions."""
    rows = session.execute(text("""
        SELECT
            LOWER(fs.email) AS email,
            fs.name,
            fs.relacion_regalado,
            fs.relacion_regalado2,
            fs.extra_data,
            fs.created_at
        FROM form_submissions fs
        WHERE fs.email IS NOT NULL AND fs.email <> ''
        ORDER BY fs.created_at ASC
    """)).fetchall()

    # Aggregate roles per email (later submissions can refine)
    by_email: dict[str, dict] = {}
    for row in rows:
        email = (row[0] or "").lower().strip()
        if not email:
            continue
        name = row[1]
        relaciones = extract_relaciones_from_submission(
            relacion_regalado=row[2],
            relacion_regalado2=row[3],
            extra_data=row[4],
        )
        entry = by_email.setdefault(email, {"name": name, "relaciones": []})
        if name and not entry.get("name"):
            entry["name"] = name
        entry["relaciones"].extend(relaciones)

    updated = skipped = 0
    for email, data in by_email.items():
        contact = session.exec(select(Contact).where(Contact.email == email)).first()
        if not contact:
            skipped += 1
            continue
        before = getattr(contact, "family_role", None)
        # Force recompute from all relaciones for backfill
        role = infer_family_role(
            name=data.get("name") or contact.name,
            gender=contact.gender,
            relaciones=data["relaciones"],
        )
        if not role:
            skipped += 1
            continue
        if not contact.gender:
            from app.services.automation_engine import _detect_name_gender
            contact.gender = _detect_name_gender(data.get("name") or contact.name or "")
        contact.family_role = role
        session.add(contact)
        if before != role:
            updated += 1

    session.commit()
    logger.info("backfill_family_roles: updated=%d skipped=%d emails=%d", updated, skipped, len(by_email))
    return {"updated": updated, "skipped": skipped, "emails": len(by_email)}
