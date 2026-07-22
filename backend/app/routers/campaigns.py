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
from app.core.deps import get_current_user, require_editor, get_current_shop
from app.models.user import User
from app.models.shop import Shop
from app.models.campaign import Campaign, CampaignCreate, CampaignRead, CampaignStats, CampaignUpdate, CampaignSend, CampaignVariantStat
from app.models.contact import Contact
from app.models.segment import Segment
from app.models.template import Template
from app.services.segment_evaluator import evaluate_segment
from app.services.email_sender import send_campaign_sync, _inject_footer, _unsub_headers, replace_unsub_tag


class SendOptions(BaseModel):
    limit: Optional[int] = None

router = APIRouter()


@router.get("", response_model=List[CampaignRead])
def list_campaigns(session: Session = Depends(get_session), _: User = Depends(get_current_user), shop: Shop = Depends(get_current_shop)):
    return session.exec(
        select(Campaign).where(Campaign.shop_id == shop.id).order_by(Campaign.created_at.desc())
    ).all()


@router.post("", response_model=CampaignRead, status_code=201)
def create_campaign(
    payload: CampaignCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_editor),
    shop: Shop = Depends(get_current_shop),
):
    data = payload.model_dump()
    if not data.get("status"):
        data["status"] = "scheduled" if data.get("scheduled_at") else "draft"
    campaign = Campaign(**data, created_by=current_user.id, shop_id=shop.id)
    session.add(campaign)
    session.commit()
    session.refresh(campaign)
    return campaign


@router.get("/{campaign_id}", response_model=CampaignRead)
def get_campaign(campaign_id: int, session: Session = Depends(get_session), _: User = Depends(get_current_user), shop: Shop = Depends(get_current_shop)):
    c = session.get(Campaign, campaign_id)
    if not c or c.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    return c


@router.patch("/{campaign_id}", response_model=CampaignRead)
def update_campaign(
    campaign_id: int,
    payload: CampaignUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
    shop: Shop = Depends(get_current_shop),
):
    c = session.get(Campaign, campaign_id)
    if not c or c.shop_id != shop.id:
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
    shop: Shop = Depends(get_current_shop),
):
    c = session.get(Campaign, campaign_id)
    if not c or c.shop_id != shop.id:
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
    shop: Shop = Depends(get_current_shop),
):
    c = session.get(Campaign, campaign_id)
    if not c or c.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    if c.status not in ("draft", "scheduled", "sent"):
        raise HTTPException(status_code=400, detail=f"Estado inválido para envío: {c.status}")

    seg = session.get(Segment, c.segment_id)
    if not seg or seg.shop_id != shop.id:
        raise HTTPException(status_code=400, detail="Segmento no encontrado")

    contacts = evaluate_segment(seg.conditions, session, shop.id)
    if not contacts:
        raise HTTPException(status_code=400, detail="El segmento no tiene contactos con opt-in")

    # Excluir contactos pertenecientes a segmentos de exclusión
    if c.exclude_segment_ids:
        excluded_ids: set[int] = set()
        for excl_id in c.exclude_segment_ids:
            excl_seg = session.get(Segment, excl_id)
            if excl_seg and excl_seg.shop_id == shop.id:
                excluded_ids.update(ct.id for ct in evaluate_segment(excl_seg.conditions, session, shop.id))
        contacts = [ct for ct in contacts if ct.id not in excluded_ids]
    if not contacts:
        raise HTTPException(status_code=400, detail="Todos los contactos del segmento están excluidos")

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
def send_progress(campaign_id: int, session: Session = Depends(get_session), _: User = Depends(get_current_user), shop: Shop = Depends(get_current_shop)):
    """Retorna cuántos contactos tiene el segmento y cuántos ya recibieron la campaña."""
    c = session.get(Campaign, campaign_id)
    if not c or c.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    seg = session.get(Segment, c.segment_id)
    total_in_segment = len(evaluate_segment(seg.conditions, session, shop.id)) if seg else 0
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
    shop: Shop = Depends(get_current_shop),
):
    """Envía un email de prueba al usuario autenticado (una prueba por variante si hay A/B)."""
    c = session.get(Campaign, campaign_id)
    if not c or c.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")

    resend.api_key = settings.RESEND_API_KEY
    nombre = current_user.name or current_user.email.split("@")[0]
    sent = []

    variants = c.variants if c.variants and len(c.variants) >= 2 else None
    items = variants if variants else [{"variant": None, "subject": c.subject, "template_id": c.template_id}]

    for item in items:
        tpl = session.get(Template, int(item["template_id"]))
        if not tpl:
            continue
        raw_html = replace_unsub_tag(tpl.html_content, current_user.email)
        html = _inject_footer(JTemplate(raw_html).render(nombre=nombre), current_user.email, shop.display_name())
        label = f"[PRUEBA {item['variant']}] " if item.get("variant") else "[PRUEBA] "
        try:
            result = resend.Emails.send({
                "from": settings.RESEND_FROM_EMAIL,
                "to": [current_user.email],
                "subject": f"{label}{item['subject']}",
                "html": html,
                "headers": _unsub_headers(current_user.email),
            })
            email_id = result.get("id") if isinstance(result, dict) else getattr(result, "id", None)
            sent.append({"variant": item.get("variant"), "email_id": email_id})
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    return {"ok": True, "sent_to": current_user.email, "sent": sent}


@router.get("/{campaign_id}/stats", response_model=CampaignStats)
def campaign_stats(campaign_id: int, session: Session = Depends(get_session), _: User = Depends(get_current_user), shop: Shop = Depends(get_current_shop)):
    c = session.get(Campaign, campaign_id)
    if not c or c.shop_id != shop.id:
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

    # Build per-variant stats
    variant_labels = sorted({s.variant_sent for s in sends if s.variant_sent})
    variant_stats: list[CampaignVariantStat] = []
    for label in variant_labels:
        vs = [s for s in sends if s.variant_sent == label]
        vs_sent    = sum(1 for s in vs if s.status not in ("queued", "failed"))
        vs_opened  = sum(1 for s in vs if s.opened_at is not None)
        vs_clicked = sum(1 for s in vs if s.clicked_at is not None)
        vs_base    = vs_sent or 1
        variant_stats.append(CampaignVariantStat(
            variant=label,
            sent=vs_sent,
            opened=vs_opened,
            clicked=vs_clicked,
            open_rate=round(vs_opened / vs_base * 100, 1),
            click_rate=round(vs_clicked / vs_base * 100, 1),
        ))

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
        variants=variant_stats,
    )


@router.get("/{campaign_id}/conversions")
def campaign_conversions(
    campaign_id: int,
    days: int = Query(default=60, ge=1, le=365),
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
    shop: Shop = Depends(get_current_shop),
):
    """
    Atribución de compras: contactos que recibieron esta campaña y
    realizaron una compra en Shopify dentro de `days` días
    posteriores al envío.
    """
    campaign = session.get(Campaign, campaign_id)
    if not campaign or campaign.shop_id != shop.id:
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
              AND shop_id = :shop_id
              AND created_at >= :start_date
              AND created_at <= :end_date
            GROUP BY LOWER(email)
        """), {
            "emails": [e.lower() for e in emails],
            "shop_id": shop.id,
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
    shop: Shop = Depends(get_current_shop),
):
    """Lista de contactos a los que se envió la campaña con su estado individual."""
    campaign = session.get(Campaign, campaign_id)
    if not campaign or campaign.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")

    sends = session.exec(
        select(CampaignSend).where(CampaignSend.campaign_id == campaign_id)
    ).all()

    contact_ids = [s.contact_id for s in sends]
    contacts = {c.id: c for c in session.exec(select(Contact).where(Contact.id.in_(contact_ids))).all()}

    return [
        {
            "contact_id":   s.contact_id,
            "name":         contacts[s.contact_id].name if s.contact_id in contacts else "—",
            "email":        contacts[s.contact_id].email if s.contact_id in contacts else "—",
            "opted_in":     contacts[s.contact_id].opted_in if s.contact_id in contacts else None,
            "status":       s.status,
            "variant_sent": s.variant_sent,
            "sent_at":      s.sent_at,
            "delivered_at": s.delivered_at,
            "opened_at":    s.opened_at,
            "clicked_at":   s.clicked_at,
            "bounced_at":   s.bounced_at,
        }
        for s in sends
    ]
