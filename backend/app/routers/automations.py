from datetime import datetime, timedelta, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select, func
from sqlalchemy import text
from app.database import get_session
from app.core.deps import get_current_user, require_editor, get_current_shop
from app.models.user import User
from app.models.shop import Shop
from app.models.template import Template
from app.models.automation import (
    Automation, AutomationCreate, AutomationRead, AutomationUpdate,
    AutomationEnrollment, AutomationRun, AutomationRunRead,
)

router = APIRouter()


@router.get("", response_model=List[AutomationRead])
def list_automations(session: Session = Depends(get_session), _: User = Depends(get_current_user), shop: Shop = Depends(get_current_shop)):
    return session.exec(
        select(Automation).where(Automation.shop_id == shop.id).order_by(Automation.created_at.desc())
    ).all()


@router.post("", response_model=AutomationRead, status_code=201)
def create_automation(
    payload: AutomationCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_editor),
    shop: Shop = Depends(get_current_shop),
):
    auto = Automation(**payload.model_dump(), created_by=current_user.id, shop_id=shop.id)
    session.add(auto)
    session.commit()
    session.refresh(auto)
    return auto


@router.get("/{auto_id}", response_model=AutomationRead)
def get_automation(auto_id: int, session: Session = Depends(get_session), _: User = Depends(get_current_user), shop: Shop = Depends(get_current_shop)):
    a = session.get(Automation, auto_id)
    if not a or a.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Automatización no encontrada")
    return a


@router.patch("/{auto_id}", response_model=AutomationRead)
def update_automation(
    auto_id: int,
    payload: AutomationUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
    shop: Shop = Depends(get_current_shop),
):
    a = session.get(Automation, auto_id)
    if not a or a.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Automatización no encontrada")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(a, k, v)
    a.updated_at = datetime.utcnow()
    session.add(a)
    session.commit()
    session.refresh(a)
    return a


@router.delete("/{auto_id}", status_code=204)
def delete_automation(
    auto_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
    shop: Shop = Depends(get_current_shop),
):
    a = session.get(Automation, auto_id)
    if not a or a.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Automatización no encontrada")
    session.delete(a)
    session.commit()


@router.post("/{auto_id}/toggle", response_model=AutomationRead)
def toggle_automation(
    auto_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
    shop: Shop = Depends(get_current_shop),
):
    a = session.get(Automation, auto_id)
    if not a or a.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Automatización no encontrada")
    a.status = "paused" if a.status == "active" else "active"
    a.updated_at = datetime.utcnow()
    session.add(a)
    session.commit()
    session.refresh(a)
    return a


class AutomationSendTestBody(BaseModel):
    to_email: str


@router.post("/{auto_id}/send-test")
def send_automation_test(
    auto_id: int,
    body: AutomationSendTestBody,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
    shop: Shop = Depends(get_current_shop),
):
    """Sends one test email per step of this automation to an arbitrary
    address, using real abandoned-cart data when available (same lookup as
    the template send-test) or placeholders otherwise. Purely a manual
    verification tool — does not create AutomationRun/Enrollment rows."""
    from app.services.email_sender import build_test_vars, render_email_content, send_test_email_now

    auto = session.get(Automation, auto_id)
    if not auto or auto.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Automatización no encontrada")

    steps = auto.steps or (
        [{"step": 1, "template_id": auto.template_id, "subject": auto.subject}] if auto.template_id else []
    )
    if not steps:
        raise HTTPException(status_code=400, detail="Esta automatización no tiene pasos configurados")

    email = body.to_email.lower().strip()
    vars_ = build_test_vars(email, shop.id)
    shop_name = shop.display_name()

    sent, errors = [], []
    for step in steps:
        step_number = step.get("step", 1)
        tpl = session.get(Template, int(step["template_id"])) if step.get("template_id") else None
        if not tpl:
            errors.append({"step": step_number, "error": "Plantilla no encontrada"})
            continue
        subject_override = f"[PRUEBA - Paso {step_number}] {step.get('subject') or tpl.subject_default or tpl.name}"
        subject, html = render_email_content(tpl, email, vars_, shop_name, subject_override=subject_override)
        try:
            result = send_test_email_now(email, subject, html)
            email_id = result.get("id") if isinstance(result, dict) else getattr(result, "id", None)
            sent.append({"step": step_number, "template_id": tpl.id, "subject": subject, "email_id": email_id})
        except Exception as exc:
            errors.append({"step": step_number, "error": str(exc)})

    return {
        "ok": not errors,
        "sent_to": email,
        "sent": sent,
        "errors": errors,
        "cart_data_found": vars_["_cart_data_found"],
    }


@router.get("/{auto_id}/runs", response_model=List[AutomationRunRead])
def list_runs(
    auto_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
    shop: Shop = Depends(get_current_shop),
):
    auto = session.get(Automation, auto_id)
    if not auto or auto.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Automatización no encontrada")
    return session.exec(
        select(AutomationRun)
        .where(AutomationRun.automation_id == auto_id)
        .order_by(AutomationRun.triggered_at.desc())
        .limit(100)
    ).all()


@router.get("/{auto_id}/stats")
def automation_stats(
    auto_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
    shop: Shop = Depends(get_current_shop),
):
    auto = session.get(Automation, auto_id)
    if not auto or auto.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Automatización no encontrada")
    from sqlalchemy import text
    result = session.execute(text("""
        SELECT
            COUNT(*)                                            AS total,
            COUNT(CASE WHEN status = 'sent' THEN 1 END)        AS sent,
            COUNT(CASE WHEN status = 'failed' THEN 1 END)      AS failed,
            COUNT(CASE WHEN opened_at IS NOT NULL THEN 1 END)   AS opened,
            COUNT(CASE WHEN clicked_at IS NOT NULL THEN 1 END)  AS clicked,
            MAX(triggered_at)                                   AS last_run
        FROM automation_runs
        WHERE automation_id = :aid
    """), {"aid": auto_id}).fetchone()

    total, sent, failed, opened, clicked, last_run = result
    sent = sent or 0
    open_rate  = round(opened / sent * 100, 1) if sent else 0.0
    click_rate = round(clicked / sent * 100, 1) if sent else 0.0

    # Conversions: orders from the same email within 7 days of the automation send
    conv = session.execute(text("""
        SELECT
            COUNT(DISTINCT so.id)                   AS orders,
            COALESCE(SUM(so.total_price::numeric), 0) AS revenue
        FROM automation_runs ar
        JOIN shopify_orders so
          ON LOWER(so.email) = LOWER(ar.contact_email)
         AND so.shop_id = :shop_id
         AND so.created_at BETWEEN ar.executed_at
                               AND ar.executed_at + INTERVAL '7 days'
        WHERE ar.automation_id = :aid
          AND ar.status = 'sent'
          AND ar.executed_at IS NOT NULL
    """), {"aid": auto_id, "shop_id": shop.id}).fetchone()

    orders, revenue = conv

    variant_rows = session.execute(text("""
        SELECT
            variant_sent,
            COUNT(*) FILTER (WHERE status = 'sent')           AS sent,
            COUNT(*) FILTER (WHERE opened_at IS NOT NULL)     AS opened,
            COUNT(*) FILTER (WHERE clicked_at IS NOT NULL)    AS clicked
        FROM automation_runs
        WHERE automation_id = :aid AND variant_sent IS NOT NULL
        GROUP BY variant_sent
        ORDER BY variant_sent
    """), {"aid": auto_id}).fetchall()

    variants_stats = [
        {
            "variant":    row[0],
            "sent":       int(row[1] or 0),
            "opened":     int(row[2] or 0),
            "clicked":    int(row[3] or 0),
            "open_rate":  round(int(row[2] or 0) / int(row[1]) * 100, 1) if row[1] else 0.0,
            "click_rate": round(int(row[3] or 0) / int(row[1]) * 100, 1) if row[1] else 0.0,
        }
        for row in variant_rows
    ]

    return {
        "total":      int(total or 0),
        "sent":       int(sent),
        "failed":     int(failed or 0),
        "opened":     int(opened or 0),
        "clicked":    int(clicked or 0),
        "open_rate":  open_rate,
        "click_rate": click_rate,
        "orders":     int(orders or 0),
        "revenue":    float(revenue or 0),
        "last_run":   last_run,
        "variants":   variants_stats,
    }


@router.get("/{auto_id}/step-stats")
def automation_step_stats(
    auto_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
    shop: Shop = Depends(get_current_shop),
):
    """Per-step metrics breakdown, with A/B variant stats per step."""
    auto = session.get(Automation, auto_id)
    if not auto or auto.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Automatización no encontrada")
    step_rows = session.execute(text("""
        SELECT
            step_number,
            COUNT(*) FILTER (WHERE status = 'sent')           AS sent,
            COUNT(*) FILTER (WHERE opened_at IS NOT NULL)     AS opened,
            COUNT(*) FILTER (WHERE clicked_at IS NOT NULL)    AS clicked
        FROM automation_runs
        WHERE automation_id = :aid
        GROUP BY step_number
        ORDER BY step_number
    """), {"aid": auto_id}).fetchall()

    variant_rows = session.execute(text("""
        SELECT
            step_number,
            variant_sent,
            COUNT(*) FILTER (WHERE status = 'sent')           AS sent,
            COUNT(*) FILTER (WHERE opened_at IS NOT NULL)     AS opened,
            COUNT(*) FILTER (WHERE clicked_at IS NOT NULL)    AS clicked
        FROM automation_runs
        WHERE automation_id = :aid AND variant_sent IS NOT NULL
        GROUP BY step_number, variant_sent
        ORDER BY step_number, variant_sent
    """), {"aid": auto_id}).fetchall()

    # Group variant rows by step (r[0]=step_number, r[1]=variant_sent, r[2-4]=counts)
    from collections import defaultdict
    variants_by_step: dict = defaultdict(list)
    for r in variant_rows:
        variants_by_step[int(r[0])].append({
            "variant":    r[1],
            "sent":       int(r[2] or 0),
            "opened":     int(r[3] or 0),
            "clicked":    int(r[4] or 0),
            "open_rate":  round(int(r[3] or 0) / int(r[2]) * 100, 1) if r[2] else 0.0,
            "click_rate": round(int(r[4] or 0) / int(r[2]) * 100, 1) if r[2] else 0.0,
        })

    return [
        {
            "step":       int(row[0]),
            "sent":       int(row[1] or 0),
            "opened":     int(row[2] or 0),
            "clicked":    int(row[3] or 0),
            "open_rate":  round(int(row[2] or 0) / int(row[1]) * 100, 1) if row[1] else 0.0,
            "click_rate": round(int(row[3] or 0) / int(row[1]) * 100, 1) if row[1] else 0.0,
            "variants":   variants_by_step.get(int(row[0]), []),
        }
        for row in step_rows
    ]


@router.get("/{auto_id}/pending")
def automation_pending(
    auto_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
    shop: Shop = Depends(get_current_shop),
):
    """Return active enrollments for this automation (contacts awaiting a send)."""
    auto = session.get(Automation, auto_id)
    if not auto or auto.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Automatización no encontrada")

    now = datetime.now(timezone.utc)

    def _is_ready(dt: datetime) -> bool:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt <= now

    enrollments = session.exec(
        select(AutomationEnrollment)
        .where(AutomationEnrollment.automation_id == auto_id)
        .where(AutomationEnrollment.status == "active")
        .order_by(AutomationEnrollment.next_send_at.asc())
        .limit(50)
    ).all()

    contacts = []
    for e in enrollments:
        import json as _json
        extra = _json.loads(e.extra_vars_json or "{}")
        name = extra.get("nombre") or extra.get("first_name") or e.contact_email
        detail = extra.get("cart_total") or extra.get("order_number") or ""
        if extra.get("first_product"):
            detail = f"{extra['first_product']} · {detail}" if detail else extra["first_product"]
        contacts.append({
            "email":     e.contact_email,
            "name":      name,
            "detail":    detail,
            "send_at":   e.next_send_at.isoformat(),
            "ready":     _is_ready(e.next_send_at),
            "step":      e.next_step,
        })

    return {"count": len(contacts), "contacts": contacts}
