from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select, func
import resend

from app.core.config import settings
from app.core.deps import get_current_user, require_editor
from app.database import get_session
from app.models.contact import Contact
from app.models.evergreen import (
    EvergreenCampaign,
    EvergreenCampaignCreate,
    EvergreenCampaignRead,
    EvergreenCampaignUpdate,
    EvergreenSend,
    EvergreenStats,
)
from app.models.template import Template
from app.models.user import User
from app.services.email_sender import (
    _inject_footer,
    _unsub_headers,
    build_contact_template_vars,
    render_html,
    render_template_text,
    uses_regalado_vars,
)
from app.services.evergreen_engine import run_evergreen_campaigns

router = APIRouter()


class ReorderBody(BaseModel):
    ordered_ids: List[int]


@router.get("", response_model=List[EvergreenCampaignRead])
def list_evergreen(session: Session = Depends(get_session), _: User = Depends(get_current_user)):
    return session.exec(
        select(EvergreenCampaign).order_by(
            EvergreenCampaign.sort_order.asc(),
            EvergreenCampaign.id.asc(),
        )
    ).all()


@router.post("", response_model=EvergreenCampaignRead, status_code=201)
def create_evergreen(
    payload: EvergreenCampaignCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_editor),
):
    max_order = session.exec(select(func.max(EvergreenCampaign.sort_order))).one() or 0
    data = payload.model_dump()
    eg = EvergreenCampaign(**data, sort_order=max_order + 1, created_by=current_user.id)
    session.add(eg)
    session.commit()
    session.refresh(eg)
    return eg


@router.post("/reorder", response_model=List[EvergreenCampaignRead])
def reorder_evergreen(
    body: ReorderBody,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
):
    for idx, eg_id in enumerate(body.ordered_ids):
        eg = session.get(EvergreenCampaign, eg_id)
        if eg:
            eg.sort_order = idx
            session.add(eg)
    session.commit()
    return session.exec(
        select(EvergreenCampaign).order_by(EvergreenCampaign.sort_order.asc())
    ).all()


@router.post("/run-now")
def run_evergreen_now(_: User = Depends(require_editor)):
    """Manual trigger for the daily evergreen dispatcher (admin/debug)."""
    return run_evergreen_campaigns(force=True)


@router.get("/{evergreen_id}", response_model=EvergreenCampaignRead)
def get_evergreen(
    evergreen_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    eg = session.get(EvergreenCampaign, evergreen_id)
    if not eg:
        raise HTTPException(status_code=404, detail="Campaña evergreen no encontrada")
    return eg


@router.patch("/{evergreen_id}", response_model=EvergreenCampaignRead)
def update_evergreen(
    evergreen_id: int,
    payload: EvergreenCampaignUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
):
    eg = session.get(EvergreenCampaign, evergreen_id)
    if not eg:
        raise HTTPException(status_code=404, detail="Campaña evergreen no encontrada")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(eg, k, v)
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
):
    eg = session.get(EvergreenCampaign, evergreen_id)
    if not eg:
        raise HTTPException(status_code=404, detail="Campaña evergreen no encontrada")
    session.delete(eg)
    session.commit()


@router.get("/{evergreen_id}/stats", response_model=EvergreenStats)
def evergreen_stats(
    evergreen_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    eg = session.get(EvergreenCampaign, evergreen_id)
    if not eg:
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
):
    eg = session.get(EvergreenCampaign, evergreen_id)
    if not eg:
        raise HTTPException(status_code=404, detail="Campaña evergreen no encontrada")
    tpl = session.get(Template, eg.template_id)
    if not tpl or not tpl.html_content:
        raise HTTPException(status_code=400, detail="Plantilla no encontrada")

    contact = session.exec(
        select(Contact).where(Contact.email == current_user.email.lower())
    ).first()
    regalado = uses_regalado_vars(tpl.html_content, eg.subject)

    if contact:
        vars_ = build_contact_template_vars(
            contact, session=session, load_submission=regalado
        )
        html = _inject_footer(
            render_html(tpl.html_content, contact, vars_=vars_, preprocess_regalado=regalado),
            current_user.email,
        )
        subject = render_template_text(
            eg.subject, contact, vars_=vars_, preprocess_regalado=regalado
        )
    else:
        from jinja2 import Template as JTemplate
        nombre = current_user.name or current_user.email.split("@")[0]
        html = _inject_footer(JTemplate(tpl.html_content).render(nombre=nombre), current_user.email)
        subject = eg.subject

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
