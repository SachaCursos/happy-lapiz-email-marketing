from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from app.database import get_session
from app.core.deps import get_current_user, require_editor
from app.models.user import User
from app.models.template import Template, TemplateCreate, TemplateRead, TemplateUpdate

router = APIRouter()


@router.get("", response_model=List[TemplateRead])
def list_templates(session: Session = Depends(get_session), _: User = Depends(get_current_user)):
    return session.exec(select(Template)).all()


@router.post("", response_model=TemplateRead, status_code=201)
def create_template(
    payload: TemplateCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_editor),
):
    tpl = Template(**payload.model_dump(), created_by=current_user.id)
    session.add(tpl)
    session.commit()
    session.refresh(tpl)
    return tpl


@router.get("/{template_id}", response_model=TemplateRead)
def get_template(template_id: int, session: Session = Depends(get_session), _: User = Depends(get_current_user)):
    tpl = session.get(Template, template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    return tpl


@router.patch("/{template_id}", response_model=TemplateRead)
def update_template(
    template_id: int,
    payload: TemplateUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
):
    tpl = session.get(Template, template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(tpl, k, v)
    tpl.updated_at = datetime.utcnow()
    session.add(tpl)
    session.commit()
    session.refresh(tpl)
    return tpl


@router.delete("/{template_id}", status_code=204)
def delete_template(
    template_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
):
    tpl = session.get(Template, template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    session.delete(tpl)
    session.commit()


@router.post("/{template_id}/duplicate", response_model=TemplateRead, status_code=201)
def duplicate_template(
    template_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_editor),
):
    tpl = session.get(Template, template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    copy = Template(
        name=f"{tpl.name} (copia)",
        subject_default=tpl.subject_default,
        preview_text=tpl.preview_text,
        html_content=tpl.html_content,
        json_blocks=tpl.json_blocks,
        created_by=current_user.id,
    )
    session.add(copy)
    session.commit()
    session.refresh(copy)
    return copy


# ── Send-test endpoint ────────────────────────────────────────────────────────

class SendTestBody(BaseModel):
    to_email: str
    subject: Optional[str] = None


@router.post("/{template_id}/send-test")
def send_template_test(
    template_id: int,
    body: SendTestBody,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """
    Renders a template with real or placeholder variables and sends it to
    to_email. Pulls abandoned-cart data for that address if available so
    {{ checkout_url }}, {{ event.extra.checkout_url }}, {{ first_name }}, etc.
    are populated with real values.
    """
    import resend
    import psycopg2
    from jinja2 import Environment, ChainableUndefined
    from app.core.config import settings
    from app.core.unsub_token import unsub_url
    from app.services.email_sender import _inject_footer, _unsub_headers

    tpl = session.get(Template, template_id)
    if not tpl or not tpl.html_content:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada o sin contenido HTML")

    email = body.to_email.lower().strip()

    # ── Pull most recent abandoned cart for this email ────────────────────────
    checkout_url = f"https://happylapiz.cl/cart"
    first_name = email.split("@")[0]
    cart_total = "$0"
    first_product = ""

    try:
        conn = psycopg2.connect(settings.DATABASE_URL)
        cur = conn.cursor()
        cur.execute("""
            SELECT first_name, subtotal_price, line_items, checkout_url
            FROM carritos_abandonados
            WHERE email = %s
              AND (recovered = FALSE OR recovered IS NULL)
              AND checkout_url IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 1
        """, (email,))
        row = cur.fetchone()
        if row:
            first_name   = (row[0] or email.split("@")[0]).strip()
            subtotal     = float(row[1] or 0)
            cart_total   = f"${int(subtotal):,}".replace(",", ".")
            items        = row[2] or []
            first_product = items[0].get("title", "") if items else ""
            checkout_url  = row[3] or checkout_url
        cur.close()
        conn.close()
    except Exception:
        pass  # DB unavailable — fall through to placeholders

    unsub = unsub_url(email)
    vars_ = {
        "nombre":        first_name,
        "first_name":    first_name,
        "email":         email,
        "cart_total":    cart_total,
        "first_product": first_product,
        "cart_url":      checkout_url,
        "checkout_url":  checkout_url,
        "coupon_code":   "CODIGO-PRUEBA",
        "orders_count":  0,
        "ultima_visita": "",
        "ticket_medio":  0,
        "total_spent":   0,
        "shipping_city": "",
        # Mirrors Klaviyo's {{ event.extra.checkout_url }} nested access
        "event": {"extra": {"checkout_url": checkout_url}},
    }

    raw_html = tpl.html_content.replace("{% unsubscribe %}", unsub)
    _env = Environment(undefined=ChainableUndefined)
    html = _inject_footer(_env.from_string(raw_html).render(**vars_), email)

    subject = body.subject or f"[PRUEBA] {tpl.subject_default or tpl.name}"

    resend.api_key = settings.RESEND_API_KEY
    try:
        result = resend.Emails.send({
            "from": settings.RESEND_FROM_EMAIL,
            "to": [email],
            "subject": subject,
            "html": html,
            "headers": _unsub_headers(email),
        })
        email_id = result.get("id") if isinstance(result, dict) else getattr(result, "id", None)
        cart_found = bool(row) if "row" in dir() else False
        return {
            "ok": True,
            "sent_to": email,
            "email_id": email_id,
            "cart_data_found": cart_found,
            "checkout_url_used": checkout_url,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
