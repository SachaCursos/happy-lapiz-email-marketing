from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select, func

from app.core.config import settings
from app.core.deps import get_current_user, get_current_shop, require_editor
from app.database import get_session
from app.models.contact import Contact
from app.models.shop import Shop
from app.models.evergreen import (
    EvergreenCampaign,
    EvergreenCampaignCreate,
    EvergreenCampaignRead,
    EvergreenCampaignUpdate,
    EvergreenSend,
    EvergreenStats,
    normalize_evergreen_steps,
)
from app.models.template import Template
from app.models.user import User
from app.services.email_sender import (
    _inject_footer,
    _unsub_headers,
    build_contact_template_vars,
    inject_preheader,
    render_html,
    render_template_text,
    uses_regalado_vars,
)
from app.models.evergreen import get_evergreen_steps
from app.services.email_provider import send_email
from app.services.evergreen_engine import run_evergreen_campaigns, process_evergreen_followups

router = APIRouter()


class ReorderBody(BaseModel):
    ordered_ids: List[int]


@router.get("", response_model=List[EvergreenCampaignRead])
def list_evergreen(
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
    shop: Shop = Depends(get_current_shop),
):
    return session.exec(
        select(EvergreenCampaign)
        .where(EvergreenCampaign.shop_id == shop.id)
        .order_by(
            EvergreenCampaign.sort_order.asc(),
            EvergreenCampaign.id.asc(),
        )
    ).all()


@router.post("", response_model=EvergreenCampaignRead, status_code=201)
def create_evergreen(
    payload: EvergreenCampaignCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_editor),
    shop: Shop = Depends(get_current_shop),
):
    max_order = session.exec(
        select(func.max(EvergreenCampaign.sort_order)).where(EvergreenCampaign.shop_id == shop.id)
    ).one() or 0
    data = payload.model_dump()
    steps = normalize_evergreen_steps(
        data["subject"],
        data["template_id"],
        data.get("preview_text"),
        data.get("steps"),
    )
    data["steps"] = steps
    eg = EvergreenCampaign(**data, shop_id=shop.id, sort_order=max_order + 1, created_by=current_user.id)
    session.add(eg)
    session.commit()
    session.refresh(eg)
    return eg


@router.post("/reorder", response_model=List[EvergreenCampaignRead])
def reorder_evergreen(
    body: ReorderBody,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
    shop: Shop = Depends(get_current_shop),
):
    for idx, eg_id in enumerate(body.ordered_ids):
        eg = session.get(EvergreenCampaign, eg_id)
        if eg and eg.shop_id == shop.id:
            eg.sort_order = idx
            session.add(eg)
    session.commit()
    return session.exec(
        select(EvergreenCampaign)
        .where(EvergreenCampaign.shop_id == shop.id)
        .order_by(EvergreenCampaign.sort_order.asc())
    ).all()


@router.post("/run-now")
def run_evergreen_now(_: User = Depends(require_editor)):
    """Manual trigger for the daily evergreen dispatcher (admin/debug) — runs
    for every shop, each campaign already scoped to its own contacts."""
    entry = run_evergreen_campaigns(force=True)
    followups = process_evergreen_followups()
    return {"entry": entry, "followups": followups}


@router.get("/{evergreen_id}", response_model=EvergreenCampaignRead)
def get_evergreen(
    evergreen_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
    shop: Shop = Depends(get_current_shop),
):
    eg = session.get(EvergreenCampaign, evergreen_id)
    if not eg or eg.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Campaña evergreen no encontrada")
    return eg


@router.patch("/{evergreen_id}", response_model=EvergreenCampaignRead)
def update_evergreen(
    evergreen_id: int,
    payload: EvergreenCampaignUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
    shop: Shop = Depends(get_current_shop),
):
    eg = session.get(EvergreenCampaign, evergreen_id)
    if not eg or eg.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Campaña evergreen no encontrada")
    updates = payload.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(eg, k, v)
    if any(k in updates for k in ("subject", "template_id", "preview_text", "steps")):
        eg.steps = normalize_evergreen_steps(
            eg.subject,
            eg.template_id,
            eg.preview_text,
            eg.steps,
        )
    from datetime import datetime
    eg.updated_at = datetime.utcnow()
    session.add(eg)
    session.commit()
    session.refresh(eg)
    return eg


@router.delete("/{evergreen_id}", status_code=204)
def delete_evergreen(
    evergreen_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
    shop: Shop = Depends(get_current_shop),
):
    eg = session.get(EvergreenCampaign, evergreen_id)
    if not eg or eg.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Campaña evergreen no encontrada")
    session.delete(eg)
    session.commit()


@router.get("/{evergreen_id}/stats", response_model=EvergreenStats)
def evergreen_stats(
    evergreen_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
    shop: Shop = Depends(get_current_shop),
):
    eg = session.get(EvergreenCampaign, evergreen_id)
    if not eg or eg.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Campaña evergreen no encontrada")

    sends = session.exec(
        select(EvergreenSend).where(EvergreenSend.evergreen_id == evergreen_id)
    ).all()
    total = len(sends)
    sent = sum(1 for s in sends if s.status not in ("queued", "failed"))
    opened = sum(1 for s in sends if s.opened_at is not None)
    clicked = sum(1 for s in sends if s.clicked_at is not None)
    base = sent or 1
    return EvergreenStats(
        evergreen_id=evergreen_id,
        total=total,
        sent=sent,
        opened=opened,
        clicked=clicked,
        open_rate=round(opened / base * 100, 1),
        click_rate=round(clicked / base * 100, 1),
    )


@router.post("/{evergreen_id}/send-test")
def send_test_evergreen(
    evergreen_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    shop: Shop = Depends(get_current_shop),
):
    eg = session.get(EvergreenCampaign, evergreen_id)
    if not eg or eg.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Campaña evergreen no encontrada")
    steps = get_evergreen_steps(eg)
    step1 = steps[0]
    tpl = session.get(Template, int(step1["template_id"]))
    if not tpl or not tpl.html_content:
        raise HTTPException(status_code=400, detail="Plantilla no encontrada")

    contact = session.exec(
        select(Contact).where(Contact.email == current_user.email.lower(), Contact.shop_id == shop.id)
    ).first()
    regalado = uses_regalado_vars(tpl.html_content, step1["subject"])

    if contact:
        vars_ = build_contact_template_vars(
            contact, session=session, load_submission=regalado
        )
        html = _inject_footer(
            render_html(tpl.html_content, contact, vars_=vars_, preprocess_regalado=regalado),
            current_user.email,
        )
        subject = render_template_text(
            step1["subject"], contact, vars_=vars_, preprocess_regalado=regalado
        )
        preview_raw = step1.get("preview_text") or eg.preview_text or ""
        if preview_raw:
            preview_text = render_template_text(
                str(preview_raw), contact, vars_=vars_, preprocess_regalado=regalado
            )
            html = inject_preheader(html, preview_text)
    else:
        from jinja2 import Template as JTemplate
        nombre = current_user.name or current_user.email.split("@")[0]
        html = _inject_footer(JTemplate(tpl.html_content).render(nombre=nombre), current_user.email)
        subject = step1["subject"]

    try:
        _provider, email_id = send_email(
            shop_id=current_user.shop_id,
            from_email=settings.RESEND_FROM_EMAIL,
            to=[current_user.email],
            subject=f"[PRUEBA] {subject}",
            html=html,
            headers=_unsub_headers(current_user.email),
        )
        return {"ok": True, "sent_to": current_user.email, "email_id": email_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
