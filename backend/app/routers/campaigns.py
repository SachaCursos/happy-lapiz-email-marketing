from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, nulls_last, text
from sqlmodel import Session, select, func
from jinja2 import Template as JTemplate
from app.database import get_session, engine
from app.core.config import settings
from app.core.deps import get_current_user, require_editor, get_current_shop
from app.models.user import User
from app.models.shop import Shop
from app.models.campaign import Campaign, CampaignCreate, CampaignRead, CampaignStats, CampaignUpdate, CampaignSend, CampaignVariantStat
from app.models.contact import Contact
from app.models.segment import Segment
from app.models.template import Template
from app.services.campaign_audience import count_campaign_recipients, get_campaign_recipients
from app.services.segment_evaluator import evaluate_segment
from app.services.email_provider import send_email
from app.services.email_sender import (
    send_campaign_batch,
    send_campaign_until_idle,
    CAMPAIGN_SEND_ATTEMPTED,
    count_attempted_campaign_sends,
    _inject_footer,
    _unsub_headers,
    build_contact_template_vars,
    inject_preheader,
    render_html,
    render_template_text,
    uses_regalado_vars,
    replace_unsub_tag,
)


class SendOptions(BaseModel):
    limit: Optional[int] = None


class AudiencePreviewRequest(BaseModel):
    segment_id: Optional[int] = None
    segment_ids: Optional[List[int]] = None
    exclude_segment_ids: List[int] = []


class AudiencePreviewResponse(BaseModel):
    segment_count: int
    excluded_count: int
    recipient_count: int

router = APIRouter()


@router.get("", response_model=List[CampaignRead])
def list_campaigns(session: Session = Depends(get_session), _: User = Depends(get_current_user), shop: Shop = Depends(get_current_shop)):
    # Newest activity first; UI does secondary sorting by column.
    return session.exec(
        select(Campaign).where(Campaign.shop_id == shop.id).order_by(
            nulls_last(desc(Campaign.sent_at)),
            desc(Campaign.created_at),
        )
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


@router.post("/audience-preview", response_model=AudiencePreviewResponse)
def preview_campaign_audience(
    payload: AudiencePreviewRequest,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
    shop: Shop = Depends(get_current_shop),
):
    seg_ids = payload.segment_ids or ([payload.segment_id] if payload.segment_id else [])
    if not seg_ids:
        raise HTTPException(status_code=400, detail="No se especificó ningún segmento")
    for sid in seg_ids:
        seg = session.get(Segment, sid)
        if not seg or seg.shop_id != shop.id:
            raise HTTPException(status_code=404, detail=f"Segmento {sid} no encontrado")
    return count_campaign_recipients(
        session,
        shop.id,
        segment_ids=seg_ids,
        exclude_segment_ids=payload.exclude_segment_ids or None,
    )


@router.post("/{campaign_id}/duplicate", response_model=CampaignRead, status_code=201)
def duplicate_campaign(
    campaign_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_editor),
    shop: Shop = Depends(get_current_shop),
):
    c = session.get(Campaign, campaign_id)
    if not c or c.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    copy = Campaign(
        name=f"{c.name} (copia)",
        subject=c.subject,
        preview_text=c.preview_text,
        template_id=c.template_id,
        segment_id=c.segment_id,
        segment_ids=c.segment_ids,
        exclude_segment_ids=c.exclude_segment_ids,
        status="draft",
        created_by=current_user.id,
        shop_id=shop.id,
    )
    session.add(copy)
    session.commit()
    session.refresh(copy)
    return copy


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
    if c.status in ("sending", "paused"):
        raise HTTPException(status_code=400, detail="No se puede editar una campaña en envío")
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
    if c.status in ("sending", "paused", "sent"):
        raise HTTPException(status_code=400, detail="No se puede eliminar campaña enviada o en envío")
    session.delete(c)
    session.commit()


@router.post("/{campaign_id}/pause", response_model=CampaignRead)
def pause_campaign(
    campaign_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
    shop: Shop = Depends(get_current_shop),
):
    c = session.get(Campaign, campaign_id)
    if not c or c.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    if c.status != "sending":
        raise HTTPException(status_code=400, detail="Solo se pueden pausar campañas en envío")
    c.status = "paused"
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


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
    if c.status not in ("draft", "scheduled", "sent", "sending", "paused"):
        raise HTTPException(status_code=400, detail=f"Estado inválido para envío: {c.status}")

    seg_ids = (c.segment_ids or []) or ([c.segment_id] if c.segment_id else [])
    if not seg_ids:
        raise HTTPException(status_code=400, detail="Segmento no configurado")

    contacts = get_campaign_recipients(session, shop.id, segment_ids=seg_ids, exclude_segment_ids=c.exclude_segment_ids)
    if not contacts:
        raise HTTPException(
            status_code=400,
            detail="El segmento no tiene contactos con opt-in"
            if not c.exclude_segment_ids
            else "Todos los contactos del segmento están excluidos",
        )

    # Excluir contactos que ya recibieron esta campaña; queued/failed pueden reintentarse
    already_sent = set(
        session.exec(
            select(CampaignSend.contact_id).where(
                CampaignSend.campaign_id == campaign_id,
                CampaignSend.status.in_(CAMPAIGN_SEND_ATTEMPTED),
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

    contact_ids = [ct.id for ct in to_send] if opts.limit else None
    background_tasks.add_task(
        send_campaign_until_idle,
        campaign_id,
        contact_ids,
        len(contacts),
        auto_resume=opts.limit is None,
    )
    return c


@router.get("/{campaign_id}/send-progress")
def send_progress(campaign_id: int, session: Session = Depends(get_session), _: User = Depends(get_current_user), shop: Shop = Depends(get_current_shop)):
    """Retorna cuántos contactos tiene el segmento y cuántos ya recibieron la campaña."""
    c = session.get(Campaign, campaign_id)
    if not c or c.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    from app.services.email_sender import get_campaign_send_progress

    return get_campaign_send_progress(session, c)


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

    contact = session.exec(
        select(Contact).where(Contact.email == current_user.email.lower(), Contact.shop_id == shop.id)
    ).first()
    from app.services.template_block_compiler import resolve_template_html

    nombre = current_user.name or current_user.email.split("@")[0]
    sent = []

    variants = c.variants if c.variants and len(c.variants) >= 2 else None
    items = variants if variants else [{"variant": None, "subject": c.subject, "template_id": c.template_id}]

    for item in items:
        tpl = session.get(Template, int(item["template_id"]))
        if not tpl:
            continue

        tpl_html = resolve_template_html(tpl)
        item_subject = item.get("subject") or c.subject
        regalado = uses_regalado_vars(tpl_html, item_subject)

        if contact:
            vars_ = build_contact_template_vars(
                contact,
                session=session,
                load_submission=regalado,
            )
            html = _inject_footer(
                render_html(
                    tpl_html,
                    contact,
                    vars_=vars_,
                    preprocess_regalado=regalado,
                ),
                current_user.email,
                shop.display_name(),
            )
            subject = render_template_text(
                item_subject,
                contact,
                vars_=vars_,
                preprocess_regalado=regalado,
            )
            preview_raw = c.preview_text or tpl.preview_text or ""
            if preview_raw:
                preview_rendered = render_template_text(
                    preview_raw,
                    contact,
                    vars_=vars_,
                    preprocess_regalado=regalado,
                )
                html = inject_preheader(html, preview_rendered)
        else:
            raw_html = replace_unsub_tag(tpl_html, current_user.email)
            html = _inject_footer(JTemplate(raw_html).render(nombre=nombre), current_user.email, shop.display_name())
            subject = item_subject
            html = inject_preheader(html, c.preview_text or tpl.preview_text or "")

        label = f"[PRUEBA {item['variant']}] " if item.get("variant") else "[PRUEBA] "
        try:
            _provider, email_id = send_email(
                shop_id=shop.id,
                from_email=settings.RESEND_FROM_EMAIL,
                to=[current_user.email],
                subject=f"{label}{subject}",
                html=html,
                headers=_unsub_headers(current_user.email),
            )
            sent.append({"variant": item.get("variant"), "email_id": email_id})
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    return {"ok": True, "sent_to": current_user.email, "sent": sent}


@router.get("/{campaign_id}/stats", response_model=CampaignStats)
def campaign_stats(
    campaign_id: int,
    date_from: str | None = Query(default=None, description="YYYY-MM-DD inclusive"),
    date_to: str | None = Query(default=None, description="YYYY-MM-DD inclusive"),
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
    shop: Shop = Depends(get_current_shop),
):
    c = session.get(Campaign, campaign_id)
    if not c or c.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")

    params: dict = {"cid": campaign_id}
    date_sql = ""
    if date_from:
        params["date_from"] = datetime.strptime(date_from, "%Y-%m-%d")
        date_sql += " AND sent_at >= :date_from"
    if date_to:
        params["date_to"] = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
        date_sql += " AND sent_at < :date_to"

    row = session.execute(text(f"""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status NOT IN ('queued', 'failed')) AS sent,
            COUNT(*) FILTER (
                WHERE delivered_at IS NOT NULL
                   OR status IN ('delivered', 'opened', 'clicked')
            ) AS delivered,
            COUNT(*) FILTER (WHERE opened_at IS NOT NULL) AS opened,
            COUNT(*) FILTER (WHERE clicked_at IS NOT NULL) AS clicked,
            COUNT(*) FILTER (WHERE bounced_at IS NOT NULL OR status = 'bounced') AS bounced,
            COUNT(*) FILTER (WHERE status = 'complained') AS complained
        FROM campaign_sends
        WHERE campaign_id = :cid
        {date_sql}
    """), params).fetchone()

    total = int(row[0] or 0)
    sent = int(row[1] or 0)
    delivered = int(row[2] or 0)
    opened = int(row[3] or 0)
    clicked = int(row[4] or 0)
    bounced = int(row[5] or 0)
    complained = int(row[6] or 0)

    base = delivered or sent or 1

    # Build per-variant stats
    sends = session.exec(
        select(CampaignSend).where(CampaignSend.campaign_id == campaign_id, CampaignSend.variant_sent.isnot(None))
    ).all()
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
    days: int = Query(default=5, ge=1, le=90),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
    shop: Shop = Depends(get_current_shop),
):
    """
    Atribución estilo Klaviyo: pedidos dentro de `days` días posteriores
    a un open o click del correo (last-touch).
    """
    from app.services.campaign_attribution import get_campaign_attribution

    campaign = session.get(Campaign, campaign_id)
    if not campaign or campaign.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")

    empty = {"campaign_id": campaign_id, "window_days": days, "bookings": 0, "revenue": 0.0, "converted_contacts": 0}

    if campaign.status not in ("sent", "sending", "paused"):
        return empty

    has_sends = session.exec(
        select(CampaignSend.id)
        .where(CampaignSend.campaign_id == campaign_id)
        .where(CampaignSend.sent_at.isnot(None))
        .limit(1)
    ).first()
    if not has_sends:
        return empty

    order_from = datetime.strptime(date_from, "%Y-%m-%d") if date_from else None
    order_to = (datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)) if date_to else None

    stats = get_campaign_attribution(
        session, campaign_id, shop.id, window_days=days,
        order_date_from=order_from, order_date_to=order_to,
    )
    return {
        "campaign_id": campaign_id,
        "window_days": days,
        **stats,
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
