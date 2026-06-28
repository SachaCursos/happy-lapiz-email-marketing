import json
import logging
import re
import time
from typing import List
from datetime import datetime, timezone, timedelta
import resend
from jinja2 import Environment, ChainableUndefined, Template as Jinja2Template
from sqlmodel import Session, select, func
from app.core.config import settings
from app.core.unsub_token import unsub_url
from app.database import engine
from app.models.contact import Contact
from app.models.campaign import Campaign, CampaignSend
from app.models.template import Template
from app.models.segment import Segment

logger = logging.getLogger(__name__)


def _fmt_nombre(name: str | None, email: str = "") -> str:
    """Return title-cased first name only. Falls back to email prefix or 'cliente'."""
    raw = (name or email.split("@")[0] or "cliente").strip()
    first = raw.lower().title().split()[0]
    return first


BATCH_SIZE = 50
RATE_DELAY = 0.25  # 4 emails/segundo — límite de Resend es 5/segundo

# queued/failed = pendiente de envío; el resto = intento ya realizado vía Resend
CAMPAIGN_SEND_ATTEMPTED: tuple[str, ...] = (
    "sent", "delivered", "opened", "clicked", "bounced", "complained",
)

_FOOTER = """<div style="margin-top:40px;padding-top:20px;border-top:1px solid #e5e7eb;
text-align:center;font-size:12px;color:#9ca3af;
font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
Recibiste este correo porque eres cliente de <strong style="color:#6b7280">Happy Lápiz</strong>.
&nbsp;&middot;&nbsp;
<a href="{url}" style="color:#9ca3af;text-decoration:underline;">Cancelar suscripción</a>
</div>"""


def _unsub_link(email: str) -> str:
    """Return a styled anchor tag for the unsubscribe link."""
    url = unsub_url(email)
    return (
        f'<a href="{url}" style="color:#727272;text-decoration:underline;" target="_blank">'
        "Cancelar suscripción"
        "</a>"
    )


def replace_unsub_tag(html: str, email: str) -> str:
    """Replace {% unsubscribe %} with a proper anchor link before Jinja2 rendering.
    Must run before Jinja2 to avoid 'Unknown tag unsubscribe' syntax error."""
    link = _unsub_link(email)
    return html.replace("{% unsubscribe %}", link)


# ── Relative countdown timer resolution ───────────────────────────────────────

_TIMER_RE = re.compile(r'<!-- HOTBOAT_TIMER_RELATIVE:(\{.*?\}) -->', re.DOTALL)
_TIMER_FONT = "'Helvetica Neue', Arial, sans-serif"


def _render_timer_html(cfg: dict, now: datetime) -> str:
    duration_hours = float(cfg.get("duration_hours", 24))
    target = now + timedelta(hours=duration_hours)
    diff = max(0.0, (target - now).total_seconds())

    days = int(diff // 86400)
    hrs  = int((diff % 86400) // 3600)
    mins = int((diff % 3600) // 60)
    secs = int(diff % 60)

    def p(n: int) -> str:
        return str(n).zfill(2)

    f      = _TIMER_FONT
    bg     = cfg.get("bg_color", "#111111")
    accent = cfg.get("accent_color", "#682ae7")
    tc     = cfg.get("text_color", "#ffffff")
    design = cfg.get("design", "clasico")
    title  = cfg.get("title", "")
    sub    = cfg.get("subtitle", "")
    units  = [
        (p(days), cfg.get("label_days", "DÍAS")),
        (p(hrs),  cfg.get("label_hours", "HRS")),
        (p(mins), cfg.get("label_minutes", "MIN")),
    ]
    if cfg.get("show_seconds", True):
        units.append((p(secs), cfg.get("label_seconds", "SEG")))

    if design == "clasico":
        cells = ""
        for i, (val, lbl) in enumerate(units):
            if i > 0:
                cells += f'<td style="padding:0 6px;vertical-align:middle;"><span style="font-size:28px;color:rgba(255,255,255,0.3);font-weight:300;font-family:{f};">:</span></td>'
            cells += (
                f'<td style="text-align:center;padding:0 4px;">'
                f'<div style="background:{accent};border-radius:10px;padding:14px 10px;min-width:58px;display:inline-block;">'
                f'<div style="font-size:38px;font-weight:900;color:{tc};line-height:1;font-family:{f};letter-spacing:-1px;">{val}</div>'
                f'<div style="font-size:10px;color:rgba(255,255,255,0.65);margin-top:6px;letter-spacing:2px;font-family:{f};">{lbl}</div>'
                f'</div></td>'
            )
        title_h = f'<p style="margin:0 0 20px;font-size:18px;font-weight:700;color:{tc};font-family:{f};">{title}</p>' if title else ""
        sub_h   = f'<p style="margin:20px 0 0;font-size:13px;color:rgba(255,255,255,0.5);font-family:{f};">{sub}</p>' if sub else ""
        return (
            f'<div style="background:{bg};padding:32px 24px;text-align:center;">'
            f'{title_h}<table role="presentation" width="auto" cellpadding="0" cellspacing="0" border="0" style="margin:0 auto;">'
            f'<tr>{cells}</tr></table>{sub_h}</div>'
        )

    if design == "minimal":
        cells = ""
        for i, (val, lbl) in enumerate(units):
            if i > 0:
                cells += f'<td style="padding:0 4px;vertical-align:top;padding-top:6px;"><span style="font-size:36px;color:{accent};font-weight:300;font-family:{f};opacity:0.4;">:</span></td>'
            cells += (
                f'<td style="text-align:center;padding:0 12px;">'
                f'<div style="font-size:52px;font-weight:900;color:{accent};line-height:1;font-family:{f};">{val}</div>'
                f'<div style="font-size:11px;color:#9ca3af;margin-top:6px;letter-spacing:2px;font-family:{f};">{lbl}</div>'
                f'</td>'
            )
        title_h = f'<p style="margin:0 0 24px;font-size:16px;font-weight:600;color:#222;font-family:{f};">{title}</p>' if title else ""
        sub_h   = f'<p style="margin:24px 0 0;font-size:13px;color:#6b7280;font-family:{f};">{sub}</p>' if sub else ""
        return (
            f'<div style="background:{bg};padding:32px 24px;text-align:center;border-top:3px solid {accent};">'
            f'{title_h}<table role="presentation" width="auto" cellpadding="0" cellspacing="0" border="0" style="margin:0 auto;">'
            f'<tr>{cells}</tr></table>{sub_h}</div>'
        )

    if design == "urgencia":
        cells = ""
        for i, (val, lbl) in enumerate(units):
            if i > 0:
                cells += f'<td style="padding:0 5px;vertical-align:middle;"><span style="font-size:28px;color:rgba(255,255,255,0.4);font-family:{f};">:</span></td>'
            cells += (
                f'<td style="text-align:center;padding:0 5px;">'
                f'<div style="background:rgba(255,255,255,0.15);border:2px solid rgba(255,255,255,0.3);border-radius:8px;padding:12px 8px;min-width:56px;display:inline-block;">'
                f'<div style="font-size:40px;font-weight:900;color:#ffffff;line-height:1;font-family:{f};">{val}</div>'
                f'<div style="font-size:10px;color:rgba(255,255,255,0.7);margin-top:5px;letter-spacing:2px;font-family:{f};">{lbl}</div>'
                f'</div></td>'
            )
        title_h = f'<p style="margin:0 0 16px;font-size:12px;font-weight:700;color:rgba(255,255,255,0.85);letter-spacing:3px;text-transform:uppercase;font-family:{f};">&#9889; {title} &#9889;</p>' if title else ""
        sub_h   = f'<p style="margin:20px 0 0;font-size:13px;color:rgba(255,255,255,0.7);font-family:{f};">{sub}</p>' if sub else ""
        return (
            f'<div style="background:{bg};padding:32px 24px;text-align:center;">'
            f'{title_h}<table role="presentation" width="auto" cellpadding="0" cellspacing="0" border="0" style="margin:0 auto;">'
            f'<tr>{cells}</tr></table>{sub_h}</div>'
        )

    # elegante
    cells = ""
    for i, (val, lbl) in enumerate(units):
        if i > 0:
            cells += f'<td style="padding:0 8px;vertical-align:top;padding-top:6px;"><span style="font-size:30px;color:{accent};font-weight:200;font-family:{f};opacity:0.4;">:</span></td>'
        cells += (
            f'<td style="text-align:center;padding:0 6px;">'
            f'<div style="border:2px solid {accent};border-radius:12px;padding:14px 10px;min-width:62px;display:inline-block;background:#ffffff;">'
            f'<div style="font-size:38px;font-weight:900;color:{accent};line-height:1;font-family:{f};">{val}</div>'
            f'<div style="font-size:10px;color:#9ca3af;margin-top:6px;letter-spacing:2px;font-family:{f};">{lbl}</div>'
            f'</div></td>'
        )
    title_h = f'<p style="margin:0 0 6px;font-size:12px;font-weight:600;color:{accent};letter-spacing:3px;text-transform:uppercase;font-family:{f};">{title}</p><div style="width:48px;height:2px;background:{accent};margin:0 auto 20px;"></div>' if title else ""
    sub_h   = f'<p style="margin:24px 0 0;font-size:13px;color:#6b7280;font-family:{f};">{sub}</p>' if sub else ""
    return (
        f'<div style="background:{bg};padding:36px 24px;text-align:center;">'
        f'{title_h}<table role="presentation" width="auto" cellpadding="0" cellspacing="0" border="0" style="margin:0 auto;">'
        f'<tr>{cells}</tr></table>{sub_h}</div>'
    )


def resolve_relative_timers(html: str) -> str:
    """Replace <!-- HOTBOAT_TIMER_RELATIVE:{...} --> placeholders with static timer HTML.
    Called at send time so the countdown reflects the actual send moment."""
    if "HOTBOAT_TIMER_RELATIVE" not in html:
        return html
    now = datetime.now(timezone.utc)

    def _replace(m: re.Match) -> str:
        try:
            cfg = json.loads(m.group(1))
            return _render_timer_html(cfg, now)
        except Exception:
            logger.warning("resolve_relative_timers: failed to parse timer config: %s", m.group(1))
            return ""

    return _TIMER_RE.sub(_replace, html)


_HOTBOAT_FOOTER_RE = re.compile(
    r'(<(?:div|table|p)[^>]*>(?:(?!<(?:div|table|p))[^<]|<(?!(?:div|table|p)))*?)?'
    r'HotBoat(?:[^<\n]*(?:\n|<[^>]+>))*?'
    r'(?:Experiencias en el agua[^\n<]*(?:\n|<[^>]+>))*?'
    r'(?:[^\n<]*[Cc]ancelar\s+suscripci[óo]n[^\n<]*)?'
    r'(?:</(?:div|table|p)>\s*)*',
    re.DOTALL | re.IGNORECASE,
)

_HOTBOAT_PLAIN_RE = re.compile(
    r'\n{0,3}HotBoat[^\n]*\nExperiencias en el agua[^\n]*\n.*',
    re.DOTALL | re.IGNORECASE,
)


def _strip_hotboat_footer(html: str) -> str:
    """Remove any residual HotBoat-branded footer from template content."""
    result = _HOTBOAT_PLAIN_RE.sub("", html)
    result = _HOTBOAT_FOOTER_RE.sub("", result)
    return result.rstrip()


def _inject_footer(html: str, email: str) -> str:
    url = unsub_url(email)
    if "##unsub##" in html:
        return html.replace("##unsub##", url)
    # Strip any leftover HotBoat footer before deciding what to inject
    lower_check = html.lower()
    if "hotboat" in lower_check or "experiencias en el agua" in lower_check:
        html = _strip_hotboat_footer(html)
    lower = html.lower()
    # Don't inject if the template already has an unsubscribe block.
    # Check for the link text OR the /unsubscribe path in the URL.
    if "cancelar suscripci" in lower or "/unsubscribe" in lower:
        return html
    footer = _FOOTER.format(url=url)
    # Inject inside the email container div, not after </body>
    # to avoid unconstrained content that triggers mobile zoom-out
    insert_before = "</div>\n</td></tr>\n</table>"
    idx = lower.rfind(insert_before)
    if idx != -1:
        return html[:idx] + footer + html[idx:]
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


_REGALADO_MARKERS = (
    "nombre_regalado",
    "relacion_regalado",
    "relacion2",
    "nombres_regalados",
    "fecha_nacimiento_regalado",
    "fecha_nacimiento2",
    "relacion",
    "fecha_nacimiento",
    "para_quien",
    "destinatario_nombre",
)


def uses_regalado_vars(*texts: str) -> bool:
    joined = " ".join(t for t in texts if t).lower()
    return any(m in joined for m in _REGALADO_MARKERS)


def _parse_custom_fields(contact: Contact) -> dict:
    cf = contact.custom_fields or {}
    if isinstance(cf, str):
        try:
            cf = json.loads(cf)
        except Exception:
            cf = {}
    return cf if isinstance(cf, dict) else {}


def _merge_regalado_from_submission(vars_: dict, email: str, session: Session) -> None:
    """Overlay regalado fields from the latest form submission for this email."""
    from app.models.form import FormSubmission
    from app.services.regalado_vars import merge_regalado_sources

    sub = session.exec(
        select(FormSubmission)
        .where(FormSubmission.email == email.lower())
        .order_by(FormSubmission.created_at.desc())
    ).first()
    if not sub:
        return

    merged = merge_regalado_sources(vars_, sub)
    for key, val in merged.items():
        if val and not vars_.get(key):
            vars_[key] = val


def build_contact_template_vars(
    contact: Contact,
    coupon_code: str = "",
    extra_vars: dict | None = None,
    session: Session | None = None,
    load_submission: bool = False,
) -> dict:
    """Build Jinja context for campaigns — mirrors automation email vars."""
    cf = _parse_custom_fields(contact)
    nombre = _fmt_nombre(contact.name, contact.email)
    first_name = nombre.split()[0] if contact.name else ""

    vars_ = {
        "nombre": nombre,
        "first_name": first_name,
        "email": contact.email,
        "ultima_visita": str(contact.ultima_visita) if contact.ultima_visita else "",
        "ticket_medio": contact.ticket_medio or 0,
        "orders_count": getattr(contact, "orders_count", 0),
        "total_spent": getattr(contact, "total_spent", 0),
        "shipping_city": getattr(contact, "shipping_city", "") or "",
        "shipping_province": getattr(contact, "shipping_province", "") or "",
        "coupon_code": coupon_code,
        "custom_fields": cf,
        **{k: v for k, v in cf.items() if isinstance(k, str)},
        **(extra_vars or {}),
    }

    if load_submission and session:
        _merge_regalado_from_submission(vars_, contact.email, session)

    from app.services.regalado_vars import prepare_regalado_vars
    prepare_regalado_vars(vars_)
    return vars_


def render_template_text(
    text: str,
    contact: Contact,
    vars_: dict | None = None,
    *,
    preprocess_regalado: bool = False,
) -> str:
    """Render a Jinja fragment (HTML body, subject, preview text)."""
    if not text:
        return ""
    from app.services.regalado_vars import preprocess_regalado_template

    raw = preprocess_regalado_template(text) if preprocess_regalado else text
    ctx = vars_ or build_contact_template_vars(contact)
    _env = Environment(undefined=ChainableUndefined)
    return _env.from_string(raw).render(**ctx)


def inject_preheader(html: str, preview_text: str) -> str:
    """Insert hidden preheader after <body> for inbox preview snippets."""
    text = (preview_text or "").strip()
    if not text:
        return html
    preheader = (
        '<span style="display:none;max-height:0;overflow:hidden;'
        f'font-size:1px;line-height:1px;color:#fff;opacity:0">{text}</span>'
    )
    lower = html.lower()
    if "<body" in lower:
        return re.sub(r"(<body[^>]*>)", r"\1" + preheader, html, count=1, flags=re.IGNORECASE)
    return preheader + html


def render_html(
    html_content: str,
    contact: Contact,
    coupon_code: str = "",
    vars_: dict | None = None,
    session: Session | None = None,
    preprocess_regalado: bool = False,
) -> str:
    # Replace {% unsubscribe %} before Jinja2 parses the template — Jinja2 would
    # throw "Unknown tag 'unsubscribe'" if left as-is.
    html_content = replace_unsub_tag(html_content, contact.email)
    html_content = resolve_relative_timers(html_content)
    return render_template_text(
        html_content,
        contact,
        vars_=vars_,
        preprocess_regalado=preprocess_regalado,
    )


def _resolve_coupon(template_html: str, contact: Contact, campaign_id: int, session: Session) -> str:
    """If template uses {{ coupon_code }}, generate a unique Shopify code for this contact."""
    if "coupon_code" not in template_html and "{% coupon_code" not in template_html:
        return ""
    from sqlalchemy import text

    row = session.execute(text("""
        SELECT cs.code FROM coupon_sends cs
        WHERE cs.contact_email = :email AND cs.campaign_id = :cid LIMIT 1
    """), {"email": contact.email.lower(), "cid": campaign_id}).fetchone()
    if row:
        return row[0]
    row2 = session.execute(text("""
        SELECT cc.id, cc.prefix FROM coupon_campaigns cc
        WHERE cc.status = 'active'
        ORDER BY cc.created_at DESC LIMIT 1
    """)).fetchone()
    if not row2:
        return ""
    import random, string
    prefix = row2[1] or "HL"
    code = f"{prefix}-{''.join(random.choices(string.ascii_uppercase+string.digits, k=8))}"
    try:
        session.execute(text("""
            INSERT INTO coupon_sends (coupon_campaign_id, contact_id, contact_email, code, campaign_id)
            VALUES (:ccid, :cid, :email, :code, :campid)
            ON CONFLICT DO NOTHING
        """), {"ccid": row2[0], "cid": contact.id, "email": contact.email.lower(),
               "code": code, "campid": campaign_id})
        session.commit()
    except Exception:
        session.rollback()
    return code


def count_attempted_campaign_sends(session: Session, campaign_id: int) -> int:
    return session.exec(
        select(func.count(CampaignSend.id)).where(
            CampaignSend.campaign_id == campaign_id,
            CampaignSend.status.in_(CAMPAIGN_SEND_ATTEMPTED),
        )
    ).one()


def finalize_campaign_status(session: Session, campaign: Campaign, total_in_segment: int) -> None:
    """Marca la campaña como enviada o borrador según cuántos contactos del segmento ya recibieron el mail."""
    attempted = count_attempted_campaign_sends(session, campaign.id)
    if total_in_segment > 0 and attempted < total_in_segment:
        campaign.status = "draft"
    else:
        campaign.status = "sent"
        campaign.sent_at = campaign.sent_at or datetime.utcnow()
    session.add(campaign)


def _send_one(campaign: Campaign, template: Template, contact: Contact, session: Session) -> None:
    send = session.exec(
        select(CampaignSend).where(
            CampaignSend.campaign_id == campaign.id,
            CampaignSend.contact_id == contact.id,
        )
    ).first()
    try:
        resend.api_key = settings.RESEND_API_KEY
        coupon = _resolve_coupon(template.html_content, contact, campaign.id, session)
        regalado = uses_regalado_vars(template.html_content, campaign.subject)
        vars_ = build_contact_template_vars(
            contact,
            coupon_code=coupon,
            session=session,
            load_submission=regalado,
        )
        html = _inject_footer(
            render_html(
                template.html_content,
                contact,
                coupon_code=coupon,
                vars_=vars_,
                preprocess_regalado=regalado,
            ),
            contact.email,
        )
        subject = render_template_text(
            campaign.subject,
            contact,
            vars_=vars_,
            preprocess_regalado=regalado,
        )
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
            logger.error("Campaña %d: plantilla no encontrada — cancelando envío", campaign_id)
            campaign.status = "draft"
            session.add(campaign)
            session.commit()
            return

        contacts = [session.get(Contact, cid) for cid in contact_ids]
        contacts = [c for c in contacts if c]

        try:
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
        except Exception as exc:
            logger.exception("Error en envío de campaña %d: %s", campaign_id, exc)
        finally:
            campaign = session.get(Campaign, campaign_id)
            if campaign and campaign.status == "sending":
                finalize_campaign_status(session, campaign, total_in_segment)
                session.commit()


STUCK_SENDING_MINUTES = 3


def recover_stuck_sending_campaigns() -> None:
    """Reanuda o cierra campañas que quedaron en 'sending' tras un crash o redeploy."""
    from app.services.campaign_audience import get_campaign_recipients

    cutoff = datetime.utcnow() - timedelta(minutes=STUCK_SENDING_MINUTES)
    with Session(engine) as session:
        stuck = session.exec(select(Campaign).where(Campaign.status == "sending")).all()
        for campaign in stuck:
            try:
                last_sent_at = session.exec(
                    select(func.max(CampaignSend.sent_at)).where(
                        CampaignSend.campaign_id == campaign.id,
                    )
                ).one()
                if last_sent_at and last_sent_at > cutoff:
                    continue

                queued_ids = list(session.exec(
                    select(CampaignSend.contact_id).where(
                        CampaignSend.campaign_id == campaign.id,
                        CampaignSend.status == "queued",
                    )
                ).all())
                total_sends = session.exec(
                    select(func.count(CampaignSend.id)).where(
                        CampaignSend.campaign_id == campaign.id,
                    )
                ).one()

                if queued_ids:
                    seg = session.get(Segment, campaign.segment_id)
                    if not seg:
                        finalize_campaign_status(session, campaign, 0)
                        session.commit()
                        continue
                    contacts = get_campaign_recipients(
                        session, campaign.segment_id, campaign.exclude_segment_ids,
                    )
                    session.commit()
                    send_campaign_sync(campaign.id, queued_ids, len(contacts))
                    continue

                if total_sends == 0:
                    campaign.status = "draft"
                    session.add(campaign)
                    session.commit()
                    continue

                contacts = get_campaign_recipients(
                    session, campaign.segment_id, campaign.exclude_segment_ids,
                )
                finalize_campaign_status(session, campaign, len(contacts))
                session.commit()
            except Exception as exc:
                logger.exception("Error recuperando campaña %d: %s", campaign.id, exc)
