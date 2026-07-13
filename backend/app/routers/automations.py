from datetime import datetime, timedelta, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func
from sqlalchemy import text
from app.database import get_session
from app.core.deps import get_current_user, require_editor
from app.models.user import User
from app.models.automation import (
    Automation, AutomationCreate, AutomationRead, AutomationUpdate,
    AutomationEnrollment, AutomationRun, AutomationRunRead,
)
from app.services import automation_engine

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

    # Conversions: Klaviyo-style open/click last-touch (5-day window)
    from app.services.campaign_attribution import get_automation_attribution

    conv = get_automation_attribution(session, auto_id, window_days=5)
    orders, revenue = conv["orders"], conv["revenue"]

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
):
    """Per-step metrics breakdown, with A/B variant stats per step."""
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
            ar.step_number,
            ar.variant_sent,
            COUNT(*) FILTER (WHERE ar.status = 'sent')             AS sent,
            COUNT(*) FILTER (WHERE ar.opened_at IS NOT NULL)       AS opened,
            COUNT(*) FILTER (WHERE ar.clicked_at IS NOT NULL)      AS clicked,
            COUNT(DISTINCT so.id) FILTER (WHERE so.id IS NOT NULL) AS conversions
        FROM automation_runs ar
        LEFT JOIN contacts c ON c.id = ar.contact_id
        LEFT JOIN shopify_orders so ON so.email = c.email
            AND so.created_at > ar.sent_at
            AND so.created_at < ar.sent_at + INTERVAL '7 days'
        WHERE ar.automation_id = :aid AND ar.variant_sent IS NOT NULL
        GROUP BY ar.step_number, ar.variant_sent
        ORDER BY ar.step_number, ar.variant_sent
    """), {"aid": auto_id}).fetchall()

    # Group variant rows by step
    from collections import defaultdict
    variants_by_step: dict = defaultdict(list)
    for r in variant_rows:
        sent = int(r[2] or 0)
        variants_by_step[int(r[0])].append({
            "variant":         r[1],
            "sent":            sent,
            "opened":          int(r[3] or 0),
            "clicked":         int(r[4] or 0),
            "conversions":     int(r[5] or 0),
            "open_rate":       round(int(r[3] or 0) / sent * 100, 1) if sent else 0.0,
            "click_rate":      round(int(r[4] or 0) / sent * 100, 1) if sent else 0.0,
            "conversion_rate": round(int(r[5] or 0) / sent * 100, 1) if sent else 0.0,
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
):
    """Return active enrollments grouped by step, plus will_enter count for form flows."""
    from app.services.automation_pending import build_pending_response

    auto = session.get(Automation, auto_id)
    if not auto:
        raise HTTPException(status_code=404, detail="Automatización no encontrada")

    return build_pending_response(auto, session)


@router.post("/run-now")
def run_automations_now(key: str = Query(default=""), _: User = Depends(get_current_user)):
    """Manually trigger one cycle of the automation engine (admin use)."""
    automation_engine.run_automations()
    return {"ok": True}


@router.post("/run-now-public")
def run_automations_now_public(key: str = Query(...)):
    """Public endpoint to trigger automation engine — requires secret key."""
    if key != "hl-admin-run-2024":
        raise HTTPException(status_code=403, detail="Forbidden")
    import traceback
    from datetime import datetime as _dt
    from sqlmodel import Session as _Session
    from app.database import engine as _engine
    from app.models.automation import AutomationEnrollment as _AE, Automation as _Auto, AutomationRun as _AR
    from app.models.contact import Contact as _Contact
    from sqlmodel import select as _select
    errors = []
    results = []
    now = _dt.utcnow()
    try:
        with _Session(_engine) as session:
            ready = session.exec(
                _select(_AE).where(_AE.status == "active").where(_AE.next_send_at <= now)
            ).all()
            results.append(f"Ready enrollments: {[e.id for e in ready]}")
            for enr in ready:
                try:
                    auto = session.get(_Auto, enr.automation_id)
                    contact = session.exec(_select(_Contact).where(_Contact.email == enr.contact_email.lower())).first()
                    results.append(f"Enrollment {enr.id}: auto={auto.id if auto else None} contact={contact.id if contact else None}")
                    automation_engine._process_enrollments(session)
                    break
                except Exception as e:
                    errors.append(f"Enrollment {enr.id}: {traceback.format_exc()[-500:]}")
                    try: session.rollback()
                    except: pass
    except Exception as e:
        errors.append(f"Outer: {traceback.format_exc()[-500:]}")
    return {"ok": True, "results": results, "errors": errors}
