import logging
import time
from typing import List
from datetime import datetime
import resend
from jinja2 import Template as Jinja2Template
from sqlmodel import Session, select, func
from app.core.config import settings
from app.core.unsub_token import unsub_url
from app.database import engine
from app.models.contact import Contact
from app.models.campaign import Campaign, CampaignSend
from app.models.template import Template

logger = logging.getLogger(__name__)


def _fmt_nombre(name: str | None, email: str = "") -> str:
    """Return title-cased first name only. Falls back to email prefix or 'cliente'."""
    raw = (name or email.split("@")[0] or "cliente").strip()
    first = raw.lower().title().split()[0]
    return first


BATCH_SIZE = 50
RATE_DELAY = 0.25  # 4 emails/segundo — límite de Resend es 5/segundo

_FOOTER = """<div style="margin-top:40px;padding-top:20px;border-top:1px solid #e5e7eb;
text-align:center;font-size:12px;color:#9ca3af;
font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
Recibiste este correo porque eres cliente de <strong style="color:#6b7280">Happy Lápiz</strong>.
&nbsp;&middot;&nbsp;
<a href="{url}" style="color:#9ca3af;text-decoration:underline;">Cancelar suscripción</a>
</div>"""


def _inject_footer(html: str, email: str) -> str:
    url = unsub_url(email)
    if "##unsub##" in html:
        return html.replace("##unsub##", url)
    footer = _FOOTER.format(url=url)
    lower = html.lower()
    idx = lower.rfind("</body>")
    if idx != -1:
        return html[:idx] + footer + html[idx:]
    return html + footer


def _unsub_headers(email: str) -> dict:
    url = unsub_url(email)
    return {
        "List-Unsubscribe": f"<{url}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }


def render_html(html_content: str, contact: Contact, coupon_code: str = "") -> str:
    tpl = Jinja2Template(html_content)
    return tpl.render(
        nombre=_fmt_nombre(contact.name, contact.email),
        first_name=_fmt_nombre(contact.name, contact.email).split()[0] if contact.name else "",
        email=contact.email,
        ultima_visita=str(contact.ultima_visita) if contact.ultima_visita else "",
        ticket_medio=contact.ticket_medio or 0,
        orders_count=getattr(contact, "orders_count", 0),
        total_spent=getattr(contact, "total_spent", 0),
        shipping_city=getattr(contact, "shipping_city", "") or "",
        coupon_code=coupon_code,
    )


def _resolve_coupon(template_html: str, contact: Contact, campaign_id: int, session: Session) -> str:
    """If template uses {{ coupon_code }}, generate a unique Shopify code for this contact."""
    if "coupon_code" not in template_html and "{% coupon_code" not in template_html:
        return ""
    from sqlalchemy import text
    row = session.exec(text("""
        SELECT cs.code FROM coupon_sends cs
        WHERE cs.contact_email = :email AND cs.campaign_id = :cid LIMIT 1
    """), {"email": contact.email.lower(), "cid": campaign_id}).fetchone()
    if row:
        return row[0]
    row2 = session.exec(text("""
        SELECT cc.id, cc.prefix FROM coupon_campaigns cc
        JOIN campaigns c ON c.id = :cid
        WHERE cc.status = 'active'
        ORDER BY cc.created_at DESC LIMIT 1
    """), {"cid": campaign_id}).fetchone()
    if not row2:
        return ""
    import random, string
    prefix = row2[1] or "HL"
    code = f"{prefix}-{''.join(random.choices(string.ascii_uppercase+string.digits, k=8))}"
    try:
        session.exec(text("""
            INSERT INTO coupon_sends (coupon_campaign_id, contact_id, contact_email, code, campaign_id)
            VALUES (:ccid, :cid, :email, :code, :campid)
            ON CONFLICT DO NOTHING
        """), {"ccid": row2[0], "cid": contact.id, "email": contact.email.lower(),
               "code": code, "campid": campaign_id})
        session.commit()
    except Exception:
        pass
    return code


def _send_one(campaign: Campaign, template: Template, contact: Contact, session: Session) -> None:
    resend.api_key = settings.RESEND_API_KEY
    coupon = _resolve_coupon(template.html_content, contact, campaign.id, session)
    html = _inject_footer(render_html(template.html_content, contact, coupon_code=coupon), contact.email)
    subject = Jinja2Template(campaign.subject).render(nombre=_fmt_nombre(contact.name, contact.email))

    send = session.exec(
        select(CampaignSend).where(
            CampaignSend.campaign_id == campaign.id,
            CampaignSend.contact_id == contact.id,
        )
    ).first()

    try:
        response = resend.Emails.send({
            "from": settings.RESEND_FROM_EMAIL,
            "to": [contact.email],
            "subject": subject,
            "html": html,
            "headers": _unsub_headers(contact.email),
            "tags": [
                {"name": "campaign_id", "value": str(campaign.id)},
                {"name": "contact_id",  "value": str(contact.id)},
            ],
        })
        if send:
            send.resend_id = response["id"]
            send.status = "sent"
            send.sent_at = datetime.utcnow()
            session.add(send)
            session.commit()
    except Exception as exc:
        logger.error("Error enviando a %s: %s", contact.email, exc)
        if send:
            send.status = "failed"  # error técnico de envío, no rebote real
            session.add(send)
            session.commit()


def send_campaign_sync(campaign_id: int, contact_ids: List[int], total_in_segment: int = 0) -> None:
    """Versión síncrona para usar como BackgroundTask de FastAPI (abre su propia sesión)."""
    with Session(engine) as session:
        campaign = session.get(Campaign, campaign_id)
        if not campaign:
            return
        template = session.get(Template, campaign.template_id)
        if not template:
            return

        contacts = [session.get(Contact, cid) for cid in contact_ids]
        contacts = [c for c in contacts if c]

        # Crear registros queued; resetear los "failed" para que puedan reintentarse
        for contact in contacts:
            exists = session.exec(
                select(CampaignSend).where(
                    CampaignSend.campaign_id == campaign_id,
                    CampaignSend.contact_id == contact.id,
                )
            ).first()
            if not exists:
                session.add(CampaignSend(campaign_id=campaign_id, contact_id=contact.id))
            elif exists.status == "failed":
                exists.status = "queued"
                session.add(exists)
        session.commit()

        # Enviar respetando rate limit de Resend (5 req/seg)
        for i, contact in enumerate(contacts):
            _send_one(campaign, template, contact, session)
            if i < len(contacts) - 1:
                time.sleep(RATE_DELAY)

        # "failed" no cuentan como enviados — quedan pendientes para reintento
        total_sent = session.exec(
            select(func.count(CampaignSend.id)).where(
                CampaignSend.campaign_id == campaign_id,
                CampaignSend.status != "failed",
            )
        ).one()
        if total_in_segment > 0 and total_sent < total_in_segment:
            campaign.status = "draft"
        else:
            campaign.status = "sent"
            campaign.sent_at = datetime.utcnow()
        session.add(campaign)
        session.commit()
