from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session, select, func
from jinja2 import Template as JTemplate
import resend
from app.database import get_session, engine
from app.core.config import settings
from app.core.deps import get_current_user, require_editor
from app.models.user import User
from app.models.campaign import Campaign, CampaignCreate, CampaignRead, CampaignStats, CampaignUpdate, CampaignSend
from app.models.contact import Contact
from app.models.segment import Segment
from app.models.template import Template
from app.services.campaign_audience import count_campaign_recipients, get_campaign_recipients
from app.services.email_sender import (
    send_campaign_sync,
    _inject_footer,
    _unsub_headers,
    build_contact_template_vars,
    render_html,
    render_template_text,
    uses_regalado_vars,
)


class SendOptions(BaseModel):
    limit: Optional[int] = None


class AudiencePreviewRequest(BaseModel):
    segment_id: int
    exclude_segment_ids: List[int] = []


class AudiencePreviewResponse(BaseModel):
    segment_count: int
    excluded_count: int
    recipient_count: int

router = APIRouter()


@router.get("", response_model=List[CampaignRead])
def list_campaigns(session: Session = Depends(get_session), _: User = Depends(get_current_user)):
    return session.exec(select(Campaign).order_by(Campaign.created_at.desc())).all()


@router.post("", response_model=CampaignRead, status_code=201)
def create_campaign(
    payload: CampaignCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_editor),
):
    data = payload.model_dump()
    if not data.get("status"):
        data["status"] = "scheduled" if data.get("scheduled_at") else "draft"
    campaign = Campaign(**data, created_by=current_user.id)
    session.add(campaign)
    session.commit()
    session.refresh(campaign)
    return campaign


@router.post("/audience-preview", response_model=AudiencePreviewResponse)
def preview_campaign_audience(
    payload: AudiencePreviewRequest,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    if not session.get(Segment, payload.segment_id):
        raise HTTPException(status_code=404, detail="Segmento no encontrado")
    return count_campaign_recipients(
        session,
        payload.segment_id,
        payload.exclude_segment_ids or None,
    )


@router.get("/{campaign_id}", response_model=CampaignRead)
def get_campaign(campaign_id: int, session: Session = Depends(get_session), _: User = Depends(get_current_user)):
    c = session.get(Campaign, campaign_id)
    if not c:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    return c


@router.patch("/{campaign_id}", response_model=CampaignRead)
def update_campaign(
    campaign_id: int,
    payload: CampaignUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
):
    c = session.get(Campaign, campaign_id)
    if not c:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    if c.status == "sent":
        raise HTTPException(status_code=400, detail="No se puede editar una campaña ya enviada")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


@router.delete("/{campaign_id}", status_code=204)
def delete_campaign(
    campaign_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
):
    c = session.get(Campaign, campaign_id)
    if not c:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    if c.status in ("sending", "sent"):
        raise HTTPException(status_code=400, detail="No se puede eliminar campaña enviada o en envío")
    session.delete(c)
    session.commit()


@router.post("/{campaign_id}/send", response_model=CampaignRead)
def send_campaign_now(
    campaign_id: int,
    background_tasks: BackgroundTasks,
    opts: SendOptions = Body(default=SendOptions()),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_editor),
):
    c = session.get(Campaign, campaign_id)
    if not c:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    if c.status not in ("draft", "scheduled", "sent"):
        raise HTTPException(status_code=400, detail=f"Estado inválido para envío: {c.status}")

    seg = session.get(Segment, c.segment_id)
    if not seg:
        raise HTTPException(status_code=400, detail="Segmento no encontrado")

    contacts = get_campaign_recipients(session, c.segment_id, c.exclude_segment_ids)
    if not contacts:
        raise HTTPException(
            status_code=400,
            detail="El segmento no tiene contactos con opt-in"
            if not c.exclude_segment_ids
            else "Todos los contactos del segmento están excluidos",
        )

    # Excluir contactos que ya recibieron esta campaña; los "failed" sí pueden reintentarse
    already_sent = set(
        session.exec(
            select(CampaignSend.contact_id).where(
                CampaignSend.campaign_id == campaign_id,
                CampaignSend.status != "failed",
            )
        ).all()
    )
    remaining = [ct for ct in contacts if ct.id not in already_sent]

    if not remaining:
        raise HTTPException(status_code=400, detail="Todos los contactos del segmento ya recibieron esta campaña")

    to_send = remaining[: opts.limit] if opts.limit else remaining

    c.status = "sending"
    session.add(c)
    session.commit()
    session.refresh(c)

    contact_ids = [ct.id for ct in to_send]
    background_tasks.add_task(send_campaign_sync, campaign_id, contact_ids, len(contacts))
    return c


@router.get("/{campaign_id}/send-progress")
def send_progress(campaign_id: int, session: Session = Depends(get_session), _: User = Depends(get_current_user)):
    """Retorna cuántos contactos tiene el segmento y cuántos ya recibieron la campaña."""
    c = session.get(Campaign, campaign_id)
    if not c:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    counts = count_campaign_recipients(session, c.segment_id, c.exclude_segment_ids)
    total_in_segment = counts["recipient_count"]
    already_sent = session.exec(
        select(func.count(CampaignSend.contact_id)).where(
            CampaignSend.campaign_id == campaign_id,
            CampaignSend.status != "failed",
        )
    ).one()
    return {"total_in_segment": total_in_segment, "already_sent": already_sent}


@router.post("/{campaign_id}/send-test")
def send_test_email(
    campaign_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Envía un email de prueba al usuario autenticado."""
    c = session.get(Campaign, campaign_id)
    if not c:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    tpl = session.get(Template, c.template_id)
    if not tpl:
        raise HTTPException(status_code=400, detail="Plantilla no encontrada")

    contact = session.exec(
        select(Contact).where(Contact.email == current_user.email.lower())
    ).first()
    regalado = uses_regalado_vars(tpl.html_content, c.subject)

    if contact:
        vars_ = build_contact_template_vars(
            contact,
            session=session,
            load_submission=regalado,
        )
        html = _inject_footer(
            render_html(
                tpl.html_content,
                contact,
                vars_=vars_,
                preprocess_regalado=regalado,
            ),
            current_user.email,
        )
        subject = render_template_text(
            c.subject,
            contact,
            vars_=vars_,
            preprocess_regalado=regalado,
        )
    else:
        nombre = current_user.name or current_user.email.split("@")[0]
        html = _inject_footer(JTemplate(tpl.html_content).render(nombre=nombre), current_user.email)
        subject = c.subject

    resend.api_key = settings.RESEND_API_KEY
    try:
        result = resend.Emails.send({
            "from": settings.RESEND_FROM_EMAIL,
            "to": [current_user.email],
            "subject": f"[PRUEBA] {subject}",
            "html": html,
            "headers": _unsub_headers(current_user.email),
        })
        email_id = result.get("id") if isinstance(result, dict) else getattr(result, "id", None)
        return {"ok": True, "sent_to": current_user.email, "email_id": email_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{campaign_id}/stats", response_model=CampaignStats)
def campaign_stats(campaign_id: int, session: Session = Depends(get_session), _: User = Depends(get_current_user)):
    c = session.get(Campaign, campaign_id)
    if not c:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")

    sends = session.exec(select(CampaignSend).where(CampaignSend.campaign_id == campaign_id)).all()
    total = len(sends)
    sent      = sum(1 for s in sends if s.status not in ("queued", "failed"))
    delivered = sum(1 for s in sends if s.delivered_at is not None or s.status in ("delivered", "opened", "clicked"))
    opened    = sum(1 for s in sends if s.opened_at is not None)
    clicked   = sum(1 for s in sends if s.clicked_at is not None)
    bounced   = sum(1 for s in sends if s.bounced_at is not None or s.status == "bounced")
    complained = sum(1 for s in sends if s.status == "complained")

    base = delivered or sent or 1
    return CampaignStats(
        campaign_id=campaign_id,
        total=total,
        sent=sent,
        delivered=delivered,
        opened=opened,
        clicked=clicked,
        bounced=bounced,
        complained=complained,
        open_rate=round(opened / base * 100, 1),
        click_rate=round(clicked / base * 100, 1),
        bounce_rate=round(bounced / (sent or 1) * 100, 1),
    )


@router.get("/{campaign_id}/conversions")
def campaign_conversions(
    campaign_id: int,
    days: int = Query(default=60, ge=1, le=365),
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """
    Atribución de compras: contactos que recibieron esta campaña y
    realizaron una compra en Shopify dentro de `days` días
    posteriores al envío.
    """
    campaign = session.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")

    empty = {"campaign_id": campaign_id, "window_days": days, "bookings": 0, "revenue": 0.0, "converted_contacts": 0}

    if not campaign.sent_at:
        return empty

    sends = session.exec(
        select(CampaignSend).where(CampaignSend.campaign_id == campaign_id)
    ).all()
    if not sends:
        return empty

    contact_ids = list({s.contact_id for s in sends})
    contacts_q = session.exec(select(Contact).where(Contact.id.in_(contact_ids))).all()
    emails = [ct.email for ct in contacts_q]
    if not emails:
        return empty

    try:
        rows = session.execute(text("""
            SELECT
                LOWER(email)                          AS email,
                COUNT(*)                              AS bookings,
                COALESCE(SUM(total_price), 0)         AS revenue
            FROM shopify_orders
            WHERE LOWER(email) = ANY(:emails)
              AND created_at >= :start_date
              AND created_at <= :end_date
            GROUP BY LOWER(email)
        """), {
            "emails": [e.lower() for e in emails],
            "start_date": campaign.sent_at,
            "end_date": campaign.sent_at + timedelta(days=days),
        }).fetchall()
    except Exception:
        return empty

    total_bookings = sum(int(r.bookings) for r in rows)
    total_revenue = sum(float(r.revenue) for r in rows)
    converted_contacts = len(rows)

    return {
        "campaign_id": campaign_id,
        "window_days": days,
        "bookings": total_bookings,
        "revenue": total_revenue,
        "converted_contacts": converted_contacts,
    }


@router.get("/{campaign_id}/sends")
def campaign_sends(
    campaign_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """Lista de contactos a los que se envió la campaña con su estado individual."""
    campaign = session.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")

    sends = session.exec(
        select(CampaignSend).where(CampaignSend.campaign_id == campaign_id)
    ).all()

    contact_ids = [s.contact_id for s in sends]
    contacts = {c.id: c for c in session.exec(select(Contact).where(Contact.id.in_(contact_ids))).all()}

    return [
        {
            "contact_id": s.contact_id,
            "name":       contacts[s.contact_id].name if s.contact_id in contacts else "—",
            "email":      contacts[s.contact_id].email if s.contact_id in contacts else "—",
            "opted_in":   contacts[s.contact_id].opted_in if s.contact_id in contacts else None,
            "status":     s.status,
            "sent_at":    s.sent_at,
            "delivered_at": s.delivered_at,
            "opened_at":  s.opened_at,
            "clicked_at": s.clicked_at,
            "bounced_at": s.bounced_at,
        }
        for s in sends
    ]
