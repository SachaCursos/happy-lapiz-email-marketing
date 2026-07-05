import json
import logging
import re
import time
from typing import List
from datetime import datetime, timezone, timedelta
import resend
from sqlalchemy import text
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


def _campaign_seg_ids(campaign: Campaign) -> list[int]:
    ids = list(campaign.segment_ids or [])
    if ids:
        return ids
    return [campaign.segment_id] if campaign.segment_id else []


def _fmt_nombre(name: str | None, email: str = "") -> str:
    """Return title-cased first name only. Falls back to email prefix or 'cliente'."""
    raw = (name or email.split("@")[0] or "cliente").strip()
    first = raw.lower().title().split()[0]
    return first


BATCH_SIZE = 50
RATE_DELAY = 0.2  # 5 emails/segundo (límite Resend)
SEND_BATCH_SIZE = 400  # contactos por lote (~80 s a 5/seg)
STALL_SECONDS = 20  # evita solapar dos workers; no bloquea entre lotes encadenados
RESUME_LOOP_SECONDS = 170  # segundos máx. de envío continuo por ciclo del scheduler

# queued = pendiente de envío; failed = intento fallido (reintentable); el resto = entregado a Resend
CAMPAIGN_SEND_ATTEMPTED: tuple[str, ...] = (
    "sent", "delivered", "opened", "clicked", "bounced", "complained",
)
CAMPAIGN_SEND_COMPLETION: tuple[str, ...] = CAMPAIGN_SEND_ATTEMPTED + ("failed",)
COMPLETION_STALL_SECONDS = 600  # sin envíos nuevos → cerrar si ≥99.5% entregado
SUCCESS_COMPLETION_RATIO = 0.995

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


def count_audience_completion_attempts(
    session: Session, campaign: Campaign, recipient_ids: List[int] | None = None,
) -> int:
    """Distinct audience contacts with at least one send attempt (incl. failed)."""
    if recipient_ids is None:
        from app.services.campaign_audience import get_campaign_recipient_ids

        recipient_ids = get_campaign_recipient_ids(
            session, segment_ids=_campaign_seg_ids(campaign), exclude_segment_ids=campaign.exclude_segment_ids,
        )
    if not recipient_ids:
        return 0
    return session.exec(
        select(func.count(func.distinct(CampaignSend.contact_id))).where(
            CampaignSend.campaign_id == campaign.id,
            CampaignSend.contact_id.in_(recipient_ids),
            CampaignSend.status.in_(CAMPAIGN_SEND_COMPLETION),
        )
    ).one()


def reconcile_campaign_sends(session: Session, campaign_id: int) -> int:
    """Remove orphan queued rows and duplicate send records for one campaign."""
    removed = 0
    removed += session.execute(
        text("""
            DELETE FROM campaign_sends q
            WHERE q.campaign_id = :cid AND q.status = 'queued'
              AND EXISTS (
                SELECT 1 FROM campaign_sends ok
                WHERE ok.campaign_id = q.campaign_id
                  AND ok.contact_id = q.contact_id
                  AND ok.status IN (
                    'sent','delivered','opened','clicked','bounced','complained'
                  )
                  AND ok.id <> q.id
              )
        """),
        {"cid": campaign_id},
    ).rowcount or 0

    removed += session.execute(
        text("""
            DELETE FROM campaign_sends cs
            WHERE cs.campaign_id = :cid
              AND cs.id IN (
                SELECT id FROM (
                  SELECT id,
                    ROW_NUMBER() OVER (
                      PARTITION BY campaign_id, contact_id
                      ORDER BY
                        CASE status
                          WHEN 'delivered' THEN 1
                          WHEN 'opened' THEN 2
                          WHEN 'clicked' THEN 3
                          WHEN 'sent' THEN 4
                          WHEN 'bounced' THEN 5
                          WHEN 'complained' THEN 6
                          WHEN 'failed' THEN 7
                          ELSE 8
                        END,
                        sent_at DESC NULLS LAST,
                        id DESC
                    ) AS rn
                  FROM campaign_sends
                  WHERE campaign_id = :cid
                ) ranked
                WHERE rn > 1
              )
        """),
        {"cid": campaign_id},
    ).rowcount or 0
    if removed:
        session.commit()
    return removed


def count_recipients_with_success(
    session: Session, campaign: Campaign, recipient_ids: List[int] | None = None,
) -> int:
    if recipient_ids is None:
        from app.services.campaign_audience import get_campaign_recipient_ids

        recipient_ids = get_campaign_recipient_ids(
            session, segment_ids=_campaign_seg_ids(campaign), exclude_segment_ids=campaign.exclude_segment_ids,
        )
    if not recipient_ids:
        return 0
    return session.exec(
        select(func.count(func.distinct(CampaignSend.contact_id))).where(
            CampaignSend.campaign_id == campaign.id,
            CampaignSend.contact_id.in_(recipient_ids),
            CampaignSend.status.in_(CAMPAIGN_SEND_ATTEMPTED),
        )
    ).one()


def _only_failures_remain(
    session: Session, campaign_id: int, pending_ids: List[int],
) -> bool:
    """True when every pending contact was attempted and only has failed rows."""
    if not pending_ids:
        return True
    for cid in pending_ids:
        statuses = session.exec(
            select(CampaignSend.status).where(
                CampaignSend.campaign_id == campaign_id,
                CampaignSend.contact_id == cid,
            )
        ).all()
        if not statuses:
            return False
        if any(s in CAMPAIGN_SEND_ATTEMPTED for s in statuses):
            return False
        if any(s == "queued" for s in statuses):
            return False
        if not any(s == "failed" for s in statuses):
            return False
    return True


def is_campaign_audience_complete(session: Session, campaign: Campaign) -> bool:
    """True when every current recipient has a successful send (or campaign stalled at ≥99.5%)."""
    reconcile_campaign_sends(session, campaign.id)
    from app.services.campaign_audience import get_campaign_recipient_ids

    recipient_ids = get_campaign_recipient_ids(
        session, segment_ids=_campaign_seg_ids(campaign), exclude_segment_ids=campaign.exclude_segment_ids,
    )
    if not recipient_ids:
        return True

    total = len(recipient_ids)
    success = count_recipients_with_success(session, campaign, recipient_ids)
    if success >= total:
        return True

    pending = get_pending_contact_ids(session, campaign)
    if not pending:
        return True

    if success >= int(total * SUCCESS_COMPLETION_RATIO) and _only_failures_remain(
        session, campaign.id, pending,
    ):
        return True

    if success >= int(total * SUCCESS_COMPLETION_RATIO):
        last_sent_at = session.exec(
            select(func.max(CampaignSend.sent_at)).where(
                CampaignSend.campaign_id == campaign.id,
                CampaignSend.sent_at.isnot(None),
            )
        ).one()
        if last_sent_at and (
            datetime.utcnow() - last_sent_at
        ).total_seconds() >= COMPLETION_STALL_SECONDS:
            return True

    return False


def get_campaign_send_progress(session: Session, campaign: Campaign) -> dict:
    """Progress metrics aligned with finalize_campaign_status (current audience)."""
    reconcile_campaign_sends(session, campaign.id)
    from app.services.campaign_audience import count_campaign_recipients, get_campaign_recipient_ids

    counts = count_campaign_recipients(
        session, segment_ids=_campaign_seg_ids(campaign), exclude_segment_ids=campaign.exclude_segment_ids,
    )
    total = counts["recipient_count"]
    recipient_ids = get_campaign_recipient_ids(
        session, segment_ids=_campaign_seg_ids(campaign), exclude_segment_ids=campaign.exclude_segment_ids,
    )
    delivered = count_recipients_with_success(session, campaign, recipient_ids)
    pending = len(get_pending_contact_ids(session, campaign))
    return {
        "total_in_segment": total,
        "already_sent": delivered,
        "audience_completed": delivered,
        "pending": pending,
        "audience_complete": is_campaign_audience_complete(session, campaign),
    }


def finalize_campaign_status(
    session: Session,
    campaign: Campaign,
    total_in_segment: int,
    *,
    auto_resume: bool = False,
) -> None:
    """Marca la campaña como enviada, en curso (sending) o borrador según pendientes."""
    if campaign.status == "paused":
        session.add(campaign)
        return

    from app.services.campaign_audience import count_campaign_recipients

    if total_in_segment <= 0:
        counts = count_campaign_recipients(
            session, segment_ids=_campaign_seg_ids(campaign), exclude_segment_ids=campaign.exclude_segment_ids,
        )
        total_in_segment = counts["recipient_count"]

    reconcile_campaign_sends(session, campaign.id)

    if is_campaign_audience_complete(session, campaign):
        campaign.status = "sent"
        if not campaign.sent_at:
            first_sent = session.exec(
                select(func.min(CampaignSend.sent_at)).where(
                    CampaignSend.campaign_id == campaign.id,
                    CampaignSend.sent_at.isnot(None),
                )
            ).one()
            campaign.sent_at = first_sent or datetime.utcnow()
        session.add(campaign)
        return

    pending = len(get_pending_contact_ids(session, campaign))
    if pending > 0:
        campaign.status = "sending" if auto_resume else "draft"
    elif total_in_segment > 0 and count_attempted_campaign_sends(session, campaign.id) < total_in_segment:
        campaign.status = "draft"
    else:
        campaign.status = "sent"
        campaign.sent_at = campaign.sent_at or datetime.utcnow()
    session.add(campaign)


def get_pending_contact_ids(session: Session, campaign: Campaign) -> List[int]:
    """Contactos del segmento que aún no recibieron un intento de envío exitoso."""
    from app.services.campaign_audience import get_campaign_recipient_ids

    recipient_ids = get_campaign_recipient_ids(
        session, segment_ids=_campaign_seg_ids(campaign), exclude_segment_ids=campaign.exclude_segment_ids,
    )
    if not recipient_ids:
        return []
    attempted = set(
        session.exec(
            select(CampaignSend.contact_id).where(
                CampaignSend.campaign_id == campaign.id,
                CampaignSend.status.in_(CAMPAIGN_SEND_ATTEMPTED),
            )
        ).all()
    )
    return [cid for cid in recipient_ids if cid not in attempted]


def _ensure_send_records(session: Session, campaign_id: int, contact_ids: List[int]) -> None:
    for cid in contact_ids:
        rows = session.exec(
            select(CampaignSend).where(
                CampaignSend.campaign_id == campaign_id,
                CampaignSend.contact_id == cid,
            )
        ).all()
        if not rows:
            session.add(CampaignSend(campaign_id=campaign_id, contact_id=cid))
            continue
        if any(r.status in CAMPAIGN_SEND_ATTEMPTED for r in rows):
            continue
        failed = next((r for r in rows if r.status == "failed"), None)
        if failed:
            failed.status = "queued"
            session.add(failed)


def send_campaign_until_idle(
    campaign_id: int,
    contact_ids: List[int] | None = None,
    total_in_segment: int = 0,
    *,
    auto_resume: bool = False,
    max_seconds: float = RESUME_LOOP_SECONDS,
) -> dict:
    """Envía lotes seguidos hasta agotar pendientes o alcanzar max_seconds."""
    deadline = time.monotonic() + max_seconds
    totals = {"campaign_id": campaign_id, "processed": 0, "pending_after": 0, "batches": 0}
    while time.monotonic() < deadline:
        result = send_campaign_batch(
            campaign_id,
            contact_ids=contact_ids,
            total_in_segment=total_in_segment,
            auto_resume=auto_resume,
        )
        totals["processed"] += result["processed"]
        totals["pending_after"] = result["pending_after"]
        totals["batches"] += 1
        contact_ids = None
        if result["processed"] == 0 or result["pending_after"] == 0:
            break
    return totals


def send_campaign_batch(
    campaign_id: int,
    contact_ids: List[int] | None = None,
    total_in_segment: int = 0,
    *,
    auto_resume: bool = False,
) -> dict:
    """Envía un lote de correos. Con auto_resume=True el scheduler continúa los pendientes."""
    stats = {"campaign_id": campaign_id, "processed": 0, "pending_after": 0}
    with Session(engine) as session:
        campaign = session.get(Campaign, campaign_id)
        if not campaign:
            return stats
        if campaign.status == "paused":
            return stats
        template = session.get(Template, campaign.template_id)
        if not template:
            logger.error("Campaña %d: plantilla no encontrada — cancelando envío", campaign_id)
            campaign.status = "draft"
            session.add(campaign)
            session.commit()
            return stats

        if total_in_segment <= 0:
            from app.services.campaign_audience import count_campaign_recipients
            counts = count_campaign_recipients(
                session, segment_ids=_campaign_seg_ids(campaign), exclude_segment_ids=campaign.exclude_segment_ids,
            )
            total_in_segment = counts["recipient_count"]

        if contact_ids is None:
            pending = get_pending_contact_ids(session, campaign)
            to_process_ids = pending[:SEND_BATCH_SIZE]
        else:
            cap = SEND_BATCH_SIZE if auto_resume else len(contact_ids)
            to_process_ids = contact_ids[:cap]

        if not to_process_ids:
            finalize_campaign_status(
                session, campaign, total_in_segment, auto_resume=auto_resume,
            )
            session.commit()
            return stats

        campaign.status = "sending"
        session.add(campaign)
        session.commit()

        contacts = [session.get(Contact, cid) for cid in to_process_ids]
        contacts = [c for c in contacts if c]

        try:
            _ensure_send_records(session, campaign_id, [c.id for c in contacts])
            session.commit()

            for i, contact in enumerate(contacts):
                live = session.get(Campaign, campaign_id)
                if not live or live.status == "paused":
                    break
                _send_one(live, template, contact, session)
                stats["processed"] += 1
                if i < len(contacts) - 1:
                    time.sleep(RATE_DELAY)
        except Exception as exc:
            logger.exception("Error en envío de campaña %d: %s", campaign_id, exc)
        finally:
            campaign = session.get(Campaign, campaign_id)
            if campaign:
                pending_left = len(get_pending_contact_ids(session, campaign))
                still_auto = (
                    auto_resume
                    and pending_left > 0
                    and not is_campaign_audience_complete(session, campaign)
                )
                finalize_campaign_status(
                    session, campaign, total_in_segment, auto_resume=still_auto,
                )
                stats["pending_after"] = len(get_pending_contact_ids(session, campaign))
                session.commit()
    return stats


def send_campaign_sync(campaign_id: int, contact_ids: List[int], total_in_segment: int = 0) -> None:
    """Compat: delega en send_campaign_batch (lotes + reanudación si la lista es grande)."""
    send_campaign_batch(
        campaign_id,
        contact_ids=contact_ids,
        total_in_segment=total_in_segment,
        auto_resume=len(contact_ids) > SEND_BATCH_SIZE,
    )


def finalize_stuck_sending_campaigns(session: Session) -> int:
    """On startup, reconcile and close campaigns that finished sending but stayed in 'sending'."""
    campaigns = session.exec(select(Campaign).where(Campaign.status == "sending")).all()
    closed = 0
    for campaign in campaigns:
        reconcile_campaign_sends(session, campaign.id)
        if is_campaign_audience_complete(session, campaign):
            from app.services.campaign_audience import count_campaign_recipients

            counts = count_campaign_recipients(
                session, segment_ids=_campaign_seg_ids(campaign), exclude_segment_ids=campaign.exclude_segment_ids,
            )
            finalize_campaign_status(
                session, campaign, counts["recipient_count"], auto_resume=False,
            )
            closed += 1
    if closed:
        session.commit()
    return closed


def resume_pending_campaign_sends() -> None:
    """Reanuda campañas en 'sending' con contactos pendientes (tras crash, deploy o timeout)."""
    to_resume: list[int] = []
    with Session(engine) as session:
        sending = session.exec(select(Campaign).where(Campaign.status == "sending")).all()
        now = datetime.utcnow()
        for campaign in sending:
            try:
                reconcile_campaign_sends(session, campaign.id)
                pending = get_pending_contact_ids(session, campaign)
                if not pending or is_campaign_audience_complete(session, campaign):
                    from app.services.campaign_audience import count_campaign_recipients
                    counts = count_campaign_recipients(
                        session, segment_ids=_campaign_seg_ids(campaign), exclude_segment_ids=campaign.exclude_segment_ids,
                    )
                    finalize_campaign_status(
                        session, campaign, counts["recipient_count"], auto_resume=False,
                    )
                    session.commit()
                    logger.info("Campaña %d completada (sin pendientes)", campaign.id)
                    continue

                last_sent_at = session.exec(
                    select(func.max(CampaignSend.sent_at)).where(
                        CampaignSend.campaign_id == campaign.id,
                    )
                ).one()
                if last_sent_at and (now - last_sent_at).total_seconds() < STALL_SECONDS:
                    continue

                to_resume.append(campaign.id)
            except Exception as exc:
                logger.exception("Error evaluando campaña %d para reanudar: %s", campaign.id, exc)

    for campaign_id in to_resume:
        try:
            logger.info("Reanudando envío automático de campaña %d", campaign_id)
            result = send_campaign_until_idle(campaign_id, auto_resume=True)
            logger.info(
                "Campaña %d: %d lote(s), %d enviados, %d pendientes",
                campaign_id, result["batches"], result["processed"], result["pending_after"],
            )
        except Exception as exc:
            logger.exception("Error reanudando campaña %d: %s", campaign_id, exc)


def _send_one(campaign: Campaign, template: Template, contact: Contact, session: Session) -> None:
    from app.services.template_block_compiler import resolve_template_html

    template_html = resolve_template_html(template)
    send = session.exec(
        select(CampaignSend).where(
            CampaignSend.campaign_id == campaign.id,
            CampaignSend.contact_id == contact.id,
        )
    ).first()
    try:
        resend.api_key = settings.RESEND_API_KEY
        coupon = _resolve_coupon(template_html, contact, campaign.id, session)
        regalado = uses_regalado_vars(template_html, campaign.subject)
        vars_ = build_contact_template_vars(
            contact,
            coupon_code=coupon,
            session=session,
            load_submission=regalado,
        )
        html = _inject_footer(
            render_html(
                template_html,
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
            send.status = "failed"
            session.add(send)
            session.commit()
