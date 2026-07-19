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
    # Perfil / formulario regalados
    "gender":           Contact.gender,
    "family_role":      Contact.family_role,
}

STRING_FIELDS = {
    "email", "origin_utm", "name", "location",
    "shipping_city", "shipping_province",
    "gender", "family_role",
}

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

    # Condición especial: producto comprado
    if field == "purchased_product":
        if not isinstance(value, dict):
            return None
        product_id = str(value.get("product_id", "")).strip()
        if not product_id:
            return None
        return text("""
            LOWER(contacts.email) IN (
                SELECT LOWER(o.email)
                FROM shopify_order_line_items li
                JOIN shopify_orders o ON o.id = li.order_id
                WHERE li.product_id = :product_id
                  AND o.email IS NOT NULL AND o.email != ''
            )
        """).bindparams(product_id=product_id)

    # Condición especial: recibió (o no) una campaña específica
    if field == "received_campaign":
        if not isinstance(value, dict):
            return None
        campaign_id = int(value.get("campaign_id", 0) or 0)
        if not campaign_id:
            return None
        received = bool(value.get("received", True))
        subq = """
            SELECT DISTINCT cs.contact_id
            FROM campaign_sends cs
            WHERE cs.campaign_id = :campaign_id
              AND cs.status IN ('sent', 'delivered', 'opened', 'clicked', 'bounced', 'complained')
        """
        if received:
            return text(f"contacts.id IN ({subq})").bindparams(campaign_id=campaign_id)
        return text(f"contacts.id NOT IN ({subq})").bindparams(campaign_id=campaign_id)

    # Condición especial: abrió (o no) una campaña específica
    if field == "opened_campaign":
        if not isinstance(value, dict):
            return None
        campaign_id = int(value.get("campaign_id", 0) or 0)
        if not campaign_id:
            return None
        opened = bool(value.get("opened", True))
        if opened:
            return text("""
                contacts.id IN (
                    SELECT DISTINCT cs.contact_id
                    FROM campaign_sends cs
                    WHERE cs.campaign_id = :campaign_id
                      AND cs.opened_at IS NOT NULL
                )
            """).bindparams(campaign_id=campaign_id)
        # No abrió = la recibió (intento de envío) pero opened_at es null
        return text("""
            contacts.id IN (
                SELECT DISTINCT cs.contact_id
                FROM campaign_sends cs
                WHERE cs.campaign_id = :campaign_id
                  AND cs.status IN ('sent', 'delivered', 'opened', 'clicked', 'bounced', 'complained')
                  AND cs.opened_at IS NULL
            )
        """).bindparams(campaign_id=campaign_id)

    # Condición especial: clickeó (o no) una campaña específica
    if field == "clicked_campaign":
        if not isinstance(value, dict):
            return None
        campaign_id = int(value.get("campaign_id", 0) or 0)
        if not campaign_id:
            return None
        clicked = bool(value.get("clicked", True))
        if clicked:
            return text("""
                contacts.id IN (
                    SELECT DISTINCT cs.contact_id
                    FROM campaign_sends cs
                    WHERE cs.campaign_id = :campaign_id
                      AND cs.clicked_at IS NOT NULL
                )
            """).bindparams(campaign_id=campaign_id)
        # No clickeó = la recibió pero clicked_at es null
        return text("""
            contacts.id IN (
                SELECT DISTINCT cs.contact_id
                FROM campaign_sends cs
                WHERE cs.campaign_id = :campaign_id
                  AND cs.status IN ('sent', 'delivered', 'opened', 'clicked', 'bounced', 'complained')
                  AND cs.clicked_at IS NULL
            )
        """).bindparams(campaign_id=campaign_id)

    # Condición especial: Nº de rebotes en campañas (campaign_sends con status bounced)
    if field == "campaign_bounce_count":
        try:
            threshold = int(value)
        except (TypeError, ValueError):
            return None
        op_sql = {
            "gte": ">=",
            "gt": ">",
            "eq": "=",
            "lte": "<=",
            "lt": "<",
        }.get(op)
        if not op_sql:
            return None
        return text(f"""
            contacts.id IN (
                SELECT cs.contact_id
                FROM campaign_sends cs
                WHERE cs.status = 'bounced' OR cs.bounced_at IS NOT NULL
                GROUP BY cs.contact_id
                HAVING COUNT(*) {op_sql} :threshold
            )
        """).bindparams(threshold=threshold)

    # Condición especial: sin aperturas en los últimos N envíos (campañas + automatizaciones + evergreen)
    if field == "no_open_in_last_n_emails":
        try:
            n = int(value)
        except (TypeError, ValueError):
            return None
        if n <= 0:
            return None
        return text("""
            contacts.id IN (
                WITH all_sends AS (
                    SELECT cs.contact_id,
                           cs.sent_at AS ts,
                           cs.opened_at
                    FROM campaign_sends cs
                    WHERE cs.contact_id IS NOT NULL
                      AND cs.sent_at IS NOT NULL
                      AND cs.status NOT IN ('failed', 'queued')
                    UNION ALL
                    SELECT COALESCE(
                        ar.contact_id,
                        (SELECT c2.id FROM contacts c2
                         WHERE LOWER(c2.email) = LOWER(ar.contact_email) LIMIT 1)
                    ),
                    COALESCE(ar.executed_at, ar.triggered_at),
                    ar.opened_at
                    FROM automation_runs ar
                    WHERE ar.status = 'sent'
                      AND COALESCE(ar.executed_at, ar.triggered_at) IS NOT NULL
                    UNION ALL
                    SELECT es.contact_id,
                           es.sent_at,
                           es.opened_at
                    FROM evergreen_sends es
                    WHERE es.contact_id IS NOT NULL
                      AND es.sent_at IS NOT NULL
                      AND es.status NOT IN ('failed', 'queued')
                ),
                valid_sends AS (
                    SELECT contact_id, ts, opened_at
                    FROM all_sends
                    WHERE contact_id IS NOT NULL
                ),
                ranked AS (
                    SELECT contact_id,
                           opened_at,
                           ROW_NUMBER() OVER (PARTITION BY contact_id ORDER BY ts DESC) AS rn
                    FROM valid_sends
                ),
                last_n AS (
                    SELECT contact_id, opened_at
                    FROM ranked
                    WHERE rn <= :n
                ),
                agg AS (
                    SELECT contact_id,
                           COUNT(*)::int AS send_count,
                           COUNT(opened_at)::int AS open_count
                    FROM last_n
                    GROUP BY contact_id
                )
                SELECT contact_id FROM agg
                WHERE send_count = :n AND open_count = 0
            )
        """).bindparams(n=n)

    # Condición especial: abrió al menos un correo en los últimos N días
    # (campañas + automatizaciones + evergreen)
    if field == "opened_email_in_last_n_days":
        try:
            days = int(value)
        except (TypeError, ValueError):
            return None
        if days <= 0:
            return None
        return text("""
            contacts.id IN (
                SELECT cs.contact_id
                FROM campaign_sends cs
                WHERE cs.contact_id IS NOT NULL
                  AND cs.opened_at >= NOW() - make_interval(days => :days)
                UNION
                SELECT COALESCE(
                    ar.contact_id,
                    (SELECT c2.id
                     FROM contacts c2
                     WHERE LOWER(c2.email) = LOWER(ar.contact_email)
                     LIMIT 1)
                )
                FROM automation_runs ar
                WHERE ar.opened_at >= NOW() - make_interval(days => :days)
                UNION
                SELECT es.contact_id
                FROM evergreen_sends es
                WHERE es.contact_id IS NOT NULL
                  AND es.opened_at >= NOW() - make_interval(days => :days)
            )
        """).bindparams(days=days)

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
    ids = evaluate_segment_ids(conditions, session)
    if not ids:
        return []
    return list(session.exec(select(Contact).where(Contact.id.in_(ids))).all())


def evaluate_segment_ids(conditions: Optional[dict], session: Session) -> List[int]:
    """IDs de contactos en el segmento — sin cargar custom_fields ni filas completas."""
    query = select(Contact.id).where(Contact.opted_in == True)  # noqa: E712
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
