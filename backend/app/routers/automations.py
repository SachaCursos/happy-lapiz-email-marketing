from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, func
from app.database import get_session
from app.core.deps import get_current_user, require_editor
from app.models.user import User
from app.models.automation import (
    Automation, AutomationCreate, AutomationRead, AutomationUpdate,
    AutomationRun, AutomationRunRead,
)

router = APIRouter()


@router.get("", response_model=List[AutomationRead])
def list_automations(session: Session = Depends(get_session), _: User = Depends(get_current_user)):
    return session.exec(select(Automation).order_by(Automation.created_at.desc())).all()


@router.post("", response_model=AutomationRead, status_code=201)
def create_automation(
    payload: AutomationCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_editor),
):
    auto = Automation(**payload.model_dump(), created_by=current_user.id)
    session.add(auto)
    session.commit()
    session.refresh(auto)
    return auto


@router.get("/{auto_id}", response_model=AutomationRead)
def get_automation(auto_id: int, session: Session = Depends(get_session), _: User = Depends(get_current_user)):
    a = session.get(Automation, auto_id)
    if not a:
        raise HTTPException(status_code=404, detail="Automatización no encontrada")
    return a


@router.patch("/{auto_id}", response_model=AutomationRead)
def update_automation(
    auto_id: int,
    payload: AutomationUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
):
    a = session.get(Automation, auto_id)
    if not a:
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
):
    a = session.get(Automation, auto_id)
    if not a:
        raise HTTPException(status_code=404, detail="Automatización no encontrada")
    session.delete(a)
    session.commit()


@router.post("/{auto_id}/toggle", response_model=AutomationRead)
def toggle_automation(
    auto_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
):
    a = session.get(Automation, auto_id)
    if not a:
        raise HTTPException(status_code=404, detail="Automatización no encontrada")
    a.status = "paused" if a.status == "active" else "active"
    a.updated_at = datetime.utcnow()
    session.add(a)
    session.commit()
    session.refresh(a)
    return a


@router.get("/{auto_id}/runs", response_model=List[AutomationRunRead])
def list_runs(
    auto_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
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
):
    from sqlalchemy import text
    result = session.exec(text("""
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
    conv = session.exec(text("""
        SELECT
            COUNT(DISTINCT so.id)                   AS orders,
            COALESCE(SUM(so.total_price::numeric), 0) AS revenue
        FROM automation_runs ar
        JOIN shopify_orders so
          ON LOWER(so.email) = LOWER(ar.contact_email)
         AND so.created_at BETWEEN ar.executed_at
                               AND ar.executed_at + INTERVAL '7 days'
        WHERE ar.automation_id = :aid
          AND ar.status = 'sent'
          AND ar.executed_at IS NOT NULL
    """), {"aid": auto_id}).fetchone()

    orders, revenue = conv
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
    }
