"""Detect and fix common email domain typos (gmail.con → gmail.com, etc.)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import text
from sqlmodel import Session, select

from app.models.contact import Contact

# Exact domain replacements (lowercase).
DOMAIN_CORRECTIONS: dict[str, str] = {
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
    "gmai.com": "gmail.com",
    "gmial.com": "gmail.com",
    "gnail.com": "gmail.com",
    "gmal.com": "gmail.com",
    "gamil.com": "gmail.com",
    "hmail.com": "gmail.com",
    "hotmail.con": "hotmail.com",
    "hotmail.comj": "hotmail.com",
    "hotmail.comfer": "hotmail.com",
    "yahoo.con": "yahoo.com",
    "outlook.con": "outlook.com",
    "outlok.com": "outlook.com",
    "icloud.con": "icloud.com",
    "live.con": "live.com",
}

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


def suggest_email_fix(email: str) -> EmailFixResult | None:
    """Return a correction if the domain looks like a known typo, else None."""
    normalized = email.lower().strip()
    if "@" not in normalized:
        return None
    local, domain = normalized.rsplit("@", 1)
    if not local or not domain or domain in _PRESERVE_DOMAINS:
        return None

    fixed_domain = domain
    if domain in DOMAIN_CORRECTIONS:
        fixed_domain = DOMAIN_CORRECTIONS[domain]
    elif _GMAIL_JUNK.match(domain):
        fixed_domain = "gmail.com"
    elif _HOTMAIL_JUNK.match(domain):
        fixed_domain = "hotmail.com"

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
        text("UPDATE form_submissions SET email = :keep_email WHERE LOWER(email) = :drop_email"),
        {"keep_email": keep_email, "drop_email": drop_email},
    )
    session.execute(
        text("UPDATE gift_recipients SET email = :keep_email WHERE LOWER(email) = :drop_email"),
        {"keep_email": keep_email, "drop_email": drop_email},
    )
    session.execute(
        text(
            "UPDATE automation_enrollments SET contact_email = :keep_email "
            "WHERE LOWER(contact_email) = :drop_email"
        ),
        {"keep_email": keep_email, "drop_email": drop_email},
    )
    session.delete(drop)


def repair_typo_emails(session: Session) -> dict:
    """Fix typo emails in contacts; merge when the corrected address already exists."""
    contacts = session.exec(select(Contact)).all()
    by_email = {c.email.lower(): c for c in contacts}
    fixed = 0
    merged = 0
    skipped = 0
    examples: list[dict] = []

    for contact in list(contacts):
        fix = suggest_email_fix(contact.email)
        if not fix:
            continue
        canonical = by_email.get(fix.email)
        if canonical and canonical.id != contact.id:
            _merge_contacts(session, canonical, contact)
            by_email.pop(contact.email.lower(), None)
            merged += 1
            if len(examples) < 20:
                examples.append({"from": fix.original, "to": fix.email, "action": "merged"})
            continue
        if canonical and canonical.id == contact.id:
            skipped += 1
            continue
        old = contact.email
        contact.email = fix.email
        session.add(contact)
        by_email.pop(old.lower(), None)
        by_email[fix.email] = contact
        fixed += 1
        if len(examples) < 20:
            examples.append({"from": old, "to": fix.email, "action": "fixed"})

    if fixed or merged:
        session.commit()
    return {
        "fixed": fixed,
        "merged": merged,
        "skipped": skipped,
        "examples": examples,
    }
