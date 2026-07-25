"""Detect and fix common email domain typos (gmaik.com → gmail.com, etc.)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, text
from sqlmodel import Session, select

from app.models.contact import Contact

logger = logging.getLogger(__name__)

# Exact domain replacements (lowercase).
DOMAIN_CORRECTIONS: dict[str, str] = {
    # gmail — TLD / trailing junk
    "gmail.con": "gmail.com",
    "gmail.comm": "gmail.com",
    "gmail.como": "gmail.com",
    "gmail.comc": "gmail.com",
    "gmail.comf": "gmail.com",
    "gmail.comv": "gmail.com",
    "gmail.comg": "gmail.com",
    "gmail.coms": "gmail.com",
    "gmail.coma": "gmail.com",
    "gmail.comp": "gmail.com",
    "gmail.comcom": "gmail.com",
    "gmail.com.com": "gmail.com",
    "gmail.co": "gmail.com",
    "gmail.cl": "gmail.com",
    # gmail — misspellings of "gmail"
    "gmai.com": "gmail.com",
    "gmaik.com": "gmail.com",
    "gmaol.com": "gmail.com",
    "gmaul.com": "gmail.com",
    "gmial.com": "gmail.com",
    "gnail.com": "gmail.com",
    "gmal.com": "gmail.com",
    "gamil.com": "gmail.com",
    "hmail.com": "gmail.com",
    "gemail.com": "gmail.com",
    "ggmail.com": "gmail.com",
    "gmaill.com": "gmail.com",
    # hotmail
    "hotmail.con": "hotmail.com",
    "hotmail.comj": "hotmail.com",
    "hotmail.comfer": "hotmail.com",
    "hotmaik.com": "hotmail.com",
    "hotmai.com": "hotmail.com",
    "hotmal.com": "hotmail.com",
    "hotmial.com": "hotmail.com",
    "htmail.com": "hotmail.com",
    "hitmail.com": "hotmail.com",
    "homail.com": "hotmail.com",
    "hotamil.com": "hotmail.com",
    # outlook / yahoo / icloud / live
    "yahoo.con": "yahoo.com",
    "yahooo.com": "yahoo.com",
    "yaho.com": "yahoo.com",
    "outlook.con": "outlook.com",
    "outlok.com": "outlook.com",
    "outloo.com": "outlook.com",
    "icloud.con": "icloud.com",
    "icoud.com": "icloud.com",
    "live.con": "live.com",
}

# Major providers eligible for edit-distance-1 auto-fix (clear near-miss only).
_KNOWN_PROVIDERS = frozenset({
    "gmail.com",
    "hotmail.com",
    "outlook.com",
    "yahoo.com",
    "icloud.com",
    "live.com",
})

# gmail.com + 1–4 stray letters (gmail.comf) or doubled com (gmail.comcom).
_GMAIL_JUNK = re.compile(r"^gmail\.com(?:[a-z]{1,4}|com)$", re.I)
_HOTMAIL_JUNK = re.compile(r"^hotmail\.com[a-z]{1,2}$", re.I)

# Legitimate regional domains we must not touch.
_PRESERVE_DOMAINS = frozenset({
    "hotmail.cl",
    "hotmail.co.uk",
    "hotmail.com.ar",
    "hotmail.com.br",
    "hotmail.es",
    "gmail.com.ar",
    "yahoo.com.ar",
    "yahoo.es",
})


@dataclass
class EmailFixResult:
    email: str
    corrected: bool
    original: str


def _is_edit_distance_one(a: str, b: str) -> bool:
    """True when a and b differ by exactly one insert/delete/substitution."""
    if a == b:
        return False
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la > lb:
        a, b = b, a
        la, lb = lb, la
    if la == lb:
        return sum(x != y for x, y in zip(a, b)) == 1
    # b is one char longer — one insertion into a
    i = j = 0
    skipped = False
    while i < la and j < lb:
        if a[i] == b[j]:
            i += 1
            j += 1
            continue
        if skipped:
            return False
        skipped = True
        j += 1
    return True


def _provider_near_miss(domain: str) -> str | None:
    """If domain is edit-distance 1 from exactly one known provider, return it."""
    matches = [p for p in _KNOWN_PROVIDERS if _is_edit_distance_one(domain, p)]
    if len(matches) == 1:
        return matches[0]
    return None


def suggest_email_fix(email: str) -> EmailFixResult | None:
    """Return a correction if the domain looks like a known typo, else None."""
    normalized = email.lower().strip()
    if "@" not in normalized:
        return None
    local, domain = normalized.rsplit("@", 1)
    if not local or not domain or domain in _PRESERVE_DOMAINS:
        return None
    if domain in _KNOWN_PROVIDERS:
        return None

    fixed_domain = domain
    if domain in DOMAIN_CORRECTIONS:
        fixed_domain = DOMAIN_CORRECTIONS[domain]
    elif _GMAIL_JUNK.match(domain):
        fixed_domain = "gmail.com"
    elif _HOTMAIL_JUNK.match(domain):
        fixed_domain = "hotmail.com"
    else:
        near = _provider_near_miss(domain)
        if near:
            fixed_domain = near

    if fixed_domain == domain:
        return None
    return EmailFixResult(
        email=f"{local}@{fixed_domain}",
        corrected=True,
        original=normalized,
    )


def normalize_email(email: str) -> str:
    """Lowercase/strip and apply a known typo fix when confident."""
    raw = email.lower().strip()
    fix = suggest_email_fix(raw)
    return fix.email if fix else raw


# Local part + domain with a real TLD (rejects "user@gmail." / "user@gmail").
_EMAIL_RE = re.compile(
    r"^[a-z0-9](?:[a-z0-9._%+\-]*[a-z0-9])?@"
    r"[a-z0-9](?:[a-z0-9\-]*[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9\-]*[a-z0-9])?)+$",
    re.I,
)


def is_valid_email(email: str) -> bool:
    """True if email looks deliverable (has local@domain.tld)."""
    if not email or not isinstance(email, str):
        return False
    normalized = email.strip()
    if len(normalized) > 254 or " " in normalized or normalized.count("@") != 1:
        return False
    return bool(_EMAIL_RE.match(normalized))


# Resend / ESP messages that mean the address will never succeed — do not retry.
_PERMANENT_SEND_ERROR_MARKERS = (
    "invalid `to` field",
    "invalid to field",
    "email address needs to follow",
    "does not contain a valid address",
    "invalid email address",
    "invalid recipient",
    "validation_error",
)


def is_permanent_send_error(error: str | Exception) -> bool:
    """True when retrying the same recipient cannot succeed."""
    msg = str(error).lower()
    return any(marker in msg for marker in _PERMANENT_SEND_ERROR_MARKERS)


def _repoint_email_refs(session: Session, old_email: str, new_email: str) -> None:
    """Update email strings that are not FK contact_id."""
    old = old_email.lower()
    new = new_email.lower()
    session.execute(
        text("UPDATE form_submissions SET email = :new WHERE LOWER(email) = :old"),
        {"new": new, "old": old},
    )
    session.execute(
        text("UPDATE gift_recipients SET email = :new WHERE LOWER(email) = :old"),
        {"new": new, "old": old},
    )
    session.execute(
        text(
            "UPDATE automation_enrollments SET contact_email = :new "
            "WHERE LOWER(contact_email) = :old"
        ),
        {"new": new, "old": old},
    )
    session.execute(
        text(
            "UPDATE automation_runs SET contact_email = :new "
            "WHERE LOWER(contact_email) = :old"
        ),
        {"new": new, "old": old},
    )


def _append_correction_note(contact: Contact, old_email: str, new_email: str, reason: str) -> None:
    stamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    line = f"[{stamp}] Email corregido ({reason}): {old_email} → {new_email}"
    prev = (contact.notes or "").strip()
    contact.notes = f"{prev}\n{line}".strip() if prev else line


def _merge_contacts(session: Session, keep: Contact, drop: Contact) -> None:
    """Merge drop into keep, re-point FKs, then delete drop."""
    if keep.id == drop.id:
        return
    if drop.name and not keep.name:
        keep.name = drop.name
    if drop.phone and not keep.phone:
        keep.phone = drop.phone
    if drop.orders_count and drop.orders_count > (keep.orders_count or 0):
        keep.orders_count = drop.orders_count
    if drop.total_spent and (keep.total_spent or 0) < (drop.total_spent or 0):
        keep.total_spent = drop.total_spent
    if drop.opted_in and not keep.opted_in:
        keep.opted_in = True
        keep.opted_in_at = drop.opted_in_at or keep.opted_in_at
    session.add(keep)

    drop_id, keep_id = drop.id, keep.id
    drop_email, keep_email = drop.email.lower(), keep.email.lower()

    session.execute(
        text("""
            DELETE FROM campaign_sends dup
            USING campaign_sends orig
            WHERE dup.campaign_id = orig.campaign_id
              AND dup.contact_id = :drop_id
              AND orig.contact_id = :keep_id
        """),
        {"drop_id": drop_id, "keep_id": keep_id},
    )
    session.execute(
        text("UPDATE campaign_sends SET contact_id = :keep_id WHERE contact_id = :drop_id"),
        {"keep_id": keep_id, "drop_id": drop_id},
    )
    session.execute(
        text("""
            DELETE FROM evergreen_sends dup
            USING evergreen_sends orig
            WHERE dup.evergreen_id = orig.evergreen_id
              AND dup.contact_id = :drop_id
              AND orig.contact_id = :keep_id
              AND dup.step_number = orig.step_number
        """),
        {"drop_id": drop_id, "keep_id": keep_id},
    )
    session.execute(
        text("UPDATE evergreen_sends SET contact_id = :keep_id WHERE contact_id = :drop_id"),
        {"keep_id": keep_id, "drop_id": drop_id},
    )
    session.execute(
        text(
            "UPDATE automation_runs SET contact_id = :keep_id "
            "WHERE contact_id = :drop_id"
        ),
        {"keep_id": keep_id, "drop_id": drop_id},
    )
    _repoint_email_refs(session, drop_email, keep_email)
    session.delete(drop)


def apply_email_correction(
    session: Session,
    old_email: str,
    new_email: str,
    *,
    reason: str = "manual",
    commit: bool = True,
) -> dict | None:
    """Rename or merge a contact email and repoint related rows."""
    old = old_email.lower().strip()
    new = new_email.lower().strip()
    if not old or not new or old == new:
        return None

    contact = session.exec(
        select(Contact).where(func.lower(Contact.email) == old)
    ).first()
    existing = session.exec(
        select(Contact).where(func.lower(Contact.email) == new)
    ).first()

    if contact and existing and contact.id != existing.id:
        _append_correction_note(existing, old, new, reason)
        _merge_contacts(session, existing, contact)
        action = "merged"
        contact_id = existing.id
    elif contact:
        _repoint_email_refs(session, contact.email.lower(), new)
        _append_correction_note(contact, contact.email, new, reason)
        contact.email = new
        contact.updated_at = datetime.utcnow()
        session.add(contact)
        action = "fixed"
        contact_id = contact.id
    else:
        _repoint_email_refs(session, old, new)
        action = "refs_only"
        contact_id = None

    if commit:
        session.commit()

    result = {
        "from": old,
        "to": new,
        "action": action,
        "contact_id": contact_id,
        "reason": reason,
    }
    logger.info("Email typo correction: %s", result)
    return result


def apply_bounce_typo_fix(session: Session, bounced_email: str) -> dict | None:
    """
    On Resend bounce: if the domain is a clear typo of a major provider
    (gmaik→gmail, hotmaik→hotmail, …), correct the contact automatically.
    """
    if not bounced_email or not isinstance(bounced_email, str):
        return None
    fix = suggest_email_fix(bounced_email)
    if not fix:
        return None
    return apply_email_correction(
        session,
        fix.original,
        fix.email,
        reason="bounce_resend",
        commit=True,
    )


def repair_typo_emails(session: Session) -> dict:
    """Fix typo emails in contacts; merge when the corrected address already exists."""
    contacts = list(session.exec(select(Contact)).all())
    fixed = 0
    merged = 0
    skipped = 0
    examples: list[dict] = []

    for contact in contacts:
        fix = suggest_email_fix(contact.email)
        if not fix:
            continue
        # Re-fetch — prior merges may have deleted this row
        still = session.get(Contact, contact.id)
        if not still:
            skipped += 1
            continue
        result = apply_email_correction(
            session,
            still.email,
            fix.email,
            reason="bulk_repair",
            commit=False,
        )
        if not result:
            skipped += 1
            continue
        if result["action"] == "merged":
            merged += 1
        elif result["action"] == "fixed":
            fixed += 1
        else:
            skipped += 1
        if len(examples) < 20:
            examples.append({
                "from": result["from"],
                "to": result["to"],
                "action": result["action"],
            })

    if fixed or merged:
        session.commit()
    return {
        "fixed": fixed,
        "merged": merged,
        "skipped": skipped,
        "examples": examples,
    }
