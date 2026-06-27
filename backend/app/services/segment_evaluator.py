from typing import List, Optional, Any
from sqlalchemy import and_, or_, func, text
from sqlmodel import Session, select
from app.models.contact import Contact

# Campos permitidos en condiciones de segmento
FIELD_MAP = {
    "id":               Contact.id,
    "email":            Contact.email,
    "origin_utm":       Contact.origin_utm,
    "opted_in":         Contact.opted_in,
    "ultima_visita":    Contact.ultima_visita,
    "ticket_medio":     Contact.ticket_medio,
    "name":             Contact.name,
    "location":         Contact.location,
    "shipping_city":    Contact.shipping_city,
    "shipping_province":Contact.shipping_province,
    # Ecommerce
    "orders_count":     Contact.orders_count,
    "total_spent":      Contact.total_spent,
    "last_purchase":    Contact.last_purchase,
    # Klaviyo
    "accepts_marketing":Contact.accepts_marketing,
    "last_event_date":  Contact.last_event_date,
}

STRING_FIELDS = {"email", "origin_utm", "name", "location", "shipping_city", "shipping_province"}

OPS = {
    "eq":       lambda col, v: col == v,
    "neq":      lambda col, v: col != v,
    "gt":       lambda col, v: col > v,
    "gte":      lambda col, v: col >= v,
    "lt":       lambda col, v: col < v,
    "lte":      lambda col, v: col <= v,
    "contains": lambda col, v: col.ilike(f"%{v}%"),
    "starts":   lambda col, v: col.ilike(f"{v}%"),
    "in":       lambda col, v: col.in_(v),
    "is_null":  lambda col, v: col.is_(None),
    "not_null": lambda col, v: col.isnot(None),
}


def _build_clause(node: dict) -> Optional[Any]:
    """Convierte un nodo de condiciones en un cláusula SQLAlchemy."""
    if "rules" in node:
        operator = node.get("operator", "AND").upper()
        sub_clauses = [_build_clause(r) for r in node["rules"]]
        sub_clauses = [c for c in sub_clauses if c is not None]
        if not sub_clauses:
            return None
        return and_(*sub_clauses) if operator == "AND" else or_(*sub_clauses)

    field = node.get("field")
    op = node.get("op")
    value = node.get("value")

    # Condición especial: tiene o no tiene regalado registrado
    if field == "has_gift_recipient":
        is_true = str(value).lower() in ("true", "1")
        if is_true:
            return text("contacts.email IN (SELECT email FROM gift_recipients)")
        else:
            return text("contacts.email NOT IN (SELECT email FROM gift_recipients)")

    # Condición especial: rellenó (o no) un formulario concreto
    # value: { "form_id": 1, "submitted": true|false }
    if field == "has_form_submission":
        if not isinstance(value, dict):
            return None
        try:
            form_id = int(value.get("form_id") or 0)
        except (TypeError, ValueError):
            return None
        if form_id <= 0:
            return None
        submitted_raw = value.get("submitted", True)
        if isinstance(submitted_raw, str):
            submitted = submitted_raw.lower() in ("true", "1", "yes", "sí", "si")
        else:
            submitted = bool(submitted_raw)
        subq = (
            "SELECT DISTINCT LOWER(email) FROM form_submissions WHERE form_id = :form_id"
        )
        if submitted:
            return text(
                f"LOWER(contacts.email) IN ({subq})"
            ).bindparams(form_id=form_id)
        return text(
            f"LOWER(contacts.email) NOT IN ({subq})"
        ).bindparams(form_id=form_id)

    # Soporte para custom_fields.{clave} — p. ej. custom_fields.es_mama
    if field and field.startswith("custom_fields."):
        key = field[len("custom_fields."):]
        col = Contact.custom_fields[key].astext
        fn = OPS.get(op)
        if fn is None:
            return None
        # Los booleanos se almacenan como texto en JSON ("true"/"false")
        if isinstance(value, bool):
            value = "true" if value else "false"
        return fn(col, value)

    col = FIELD_MAP.get(field)
    fn = OPS.get(op)
    if col is None or fn is None:
        return None

    # Comparación case-insensitive para campos de texto con eq/neq
    if field in STRING_FIELDS and op == "eq" and isinstance(value, str):
        return col.ilike(value)
    if field in STRING_FIELDS and op == "neq" and isinstance(value, str):
        return ~col.ilike(value)

    return fn(col, value)


def evaluate_segment(conditions: Optional[dict], session: Session) -> List[Contact]:
    """Retorna contactos que coinciden con las condiciones del segmento (opted_in=True)."""
    query = select(Contact).where(Contact.opted_in == True)  # noqa: E712
    if conditions:
        clause = _build_clause(conditions)
        if clause is not None:
            query = query.where(clause)
    return list(session.exec(query).all())


def count_segment(conditions: Optional[dict], session: Session) -> int:
    query = select(func.count(Contact.id)).where(Contact.opted_in == True)  # noqa: E712
    if conditions:
        clause = _build_clause(conditions)
        if clause is not None:
            query = query.where(clause)
    return session.exec(query).one()
