from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import load_only
from sqlmodel import Session, select
from app.database import get_session
from app.core.deps import get_current_user, require_editor, get_current_shop
from app.models.user import User
from app.models.shop import Shop
from app.models.template import Template, TemplateCreate, TemplateRead, TemplateSummary, TemplateUpdate
from app.models.campaign import Campaign
from app.models.automation import Automation
from app.services.template_compositions import compile_template_payload, is_editor_block_list
from app.services.template_block_compiler import blocks_to_html

router = APIRouter()


@router.get("", response_model=List[TemplateSummary])
def list_templates(session: Session = Depends(get_session), _: User = Depends(get_current_user), shop: Shop = Depends(get_current_shop)):
    return session.exec(
        select(Template)
        .where(Template.shop_id == shop.id)
        .options(load_only(
            Template.id,
            Template.name,
            Template.subject_default,
            Template.preview_text,
            Template.html_content,
            Template.created_by,
            Template.created_at,
            Template.updated_at,
        ))
        .order_by(Template.created_at.desc(), Template.id.desc())
    ).all()


@router.post("", response_model=TemplateRead, status_code=201)
def create_template(
    payload: TemplateCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_editor),
    shop: Shop = Depends(get_current_shop),
):
    data = compile_template_payload(payload.model_dump())
    tpl = Template(**data, created_by=current_user.id, shop_id=shop.id)
    session.add(tpl)
    session.commit()
    session.refresh(tpl)
    return tpl


@router.get("/{template_id}", response_model=TemplateRead)
def get_template(template_id: int, session: Session = Depends(get_session), _: User = Depends(get_current_user), shop: Shop = Depends(get_current_shop)):
    tpl = session.get(Template, template_id)
    if not tpl or tpl.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    return tpl


@router.patch("/{template_id}", response_model=TemplateRead)
def update_template(
    template_id: int,
    payload: TemplateUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
    shop: Shop = Depends(get_current_shop),
):
    tpl = session.get(Template, template_id)
    if not tpl or tpl.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    updates = payload.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(tpl, k, v)
    if "json_blocks" in updates and is_editor_block_list(tpl.json_blocks):
        tpl.html_content = blocks_to_html(tpl.json_blocks)
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
    shop: Shop = Depends(get_current_shop),
):
    tpl = session.get(Template, template_id)
    if not tpl or tpl.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")

    # Nullify FK references so deletion doesn't fail on constraints
    for c in session.exec(select(Campaign).where(Campaign.template_id == template_id)).all():
        c.template_id = None
        session.add(c)
    for a in session.exec(select(Automation).where(Automation.template_id == template_id)).all():
        a.template_id = None
        session.add(a)

    session.delete(tpl)
    session.commit()


@router.post("/{template_id}/duplicate", response_model=TemplateRead, status_code=201)
def duplicate_template(
    template_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_editor),
    shop: Shop = Depends(get_current_shop),
):
    tpl = session.get(Template, template_id)
    if not tpl or tpl.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    copy = Template(
        name=f"{tpl.name} (copia)",
        subject_default=tpl.subject_default,
        preview_text=tpl.preview_text,
        html_content=tpl.html_content,
        json_blocks=tpl.json_blocks,
        created_by=current_user.id,
        shop_id=shop.id,
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
    shop: Shop = Depends(get_current_shop),
):
    """
    Renders a template with real or placeholder variables and sends it to
    to_email. Pulls abandoned-cart data for that address if available so
    {{ checkout_url }}, {{ event.extra.checkout_url }}, {{ first_name }}, etc.
    are populated with real values.
    """
    from app.services.email_sender import build_test_vars, render_email_content, send_test_email_now
    from app.services.template_block_compiler import resolve_template_html

    tpl = session.get(Template, template_id)
    tpl_html = resolve_template_html(tpl) if tpl else ""
    if not tpl or tpl.shop_id != shop.id or not tpl_html:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada o sin contenido HTML")

    email = body.to_email.lower().strip()
    vars_ = build_test_vars(email, shop.id)
    subject_override = body.subject or f"[PRUEBA] {tpl.subject_default or tpl.name}"
    subject, html = render_email_content(tpl, email, vars_, shop.display_name(), subject_override=subject_override)

    try:
        result = send_test_email_now(email, subject, html)
        email_id = result.get("id") if isinstance(result, dict) else getattr(result, "id", None)
        return {
            "ok": True,
            "sent_to": email,
            "email_id": email_id,
            "cart_data_found": vars_["_cart_data_found"],
            "checkout_url_used": vars_["checkout_url"],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
