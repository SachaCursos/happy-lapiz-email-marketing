from datetime import datetime, timedelta, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, func
from sqlalchemy import text
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


@router.get("/{auto_id}/pending")
def automation_pending(
    auto_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    auto = session.get(Automation, auto_id)
    if not auto:
        raise HTTPException(status_code=404, detail="Automatización no encontrada")

    config = auto.trigger_config or {}
    now = datetime.now(timezone.utc)
    contacts = []

    def _is_ready(dt: datetime) -> bool:
        """Compare possibly tz-aware dt with now, normalising if needed."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt <= now

    if auto.trigger_type == "abandoned_cart":
        delay_hours   = float(config.get("delay_hours", 1))
        lookback_hours = float(config.get("lookback_hours", 24))
        cutoff_recent  = now - timedelta(hours=lookback_hours)

        rows = session.exec(text("""
            SELECT email, first_name, last_name, subtotal_price, line_items, created_at
            FROM carritos_abandonados
            WHERE recovered = FALSE
              AND abandoned_email_sent = FALSE
              AND email IS NOT NULL AND email <> ''
              AND created_at >= :recent
            ORDER BY created_at ASC
            LIMIT 30
        """), {"recent": cutoff_recent}).fetchall()

        for r in rows:
            send_at  = r.created_at + timedelta(hours=delay_hours)
            items    = r.line_items or []
            detail   = items[0].get("title", "")[:45] if items else ""
            price    = f"${int(float(r.subtotal_price or 0)):,}".replace(",", ".")
            contacts.append({
                "email":   r.email,
                "name":    f"{r.first_name or ''} {r.last_name or ''}".strip() or r.email,
                "detail":  f"{detail} · {price}" if detail else price,
                "send_at": send_at.isoformat(),
                "ready":   _is_ready(send_at),
            })

    elif auto.trigger_type == "welcome":
        delay_hours = float(config.get("delay_hours", 0))
        cutoff      = now - timedelta(hours=max(delay_hours + 48, 48))

        rows = session.exec(text("""
            SELECT c.email, c.name, c.created_at
            FROM contacts c
            WHERE c.opted_in = TRUE
              AND c.created_at >= :cutoff
              AND NOT EXISTS (
                  SELECT 1 FROM automation_runs ar
                  WHERE ar.automation_id = :aid
                    AND ar.contact_email = c.email
                    AND ar.status = 'sent'
              )
            ORDER BY c.created_at ASC
            LIMIT 30
        """), {"cutoff": cutoff, "aid": auto_id}).fetchall()

        for r in rows:
            send_at = r.created_at + timedelta(hours=delay_hours)
            contacts.append({
                "email":   r.email,
                "name":    r.name or r.email,
                "detail":  "Nuevo suscriptor",
                "send_at": send_at.isoformat(),
                "ready":   _is_ready(send_at),
            })

    elif auto.trigger_type == "reactivation":
        inactivity_days = int(config.get("inactivity_days", 90))
        cooldown_days   = int(config.get("cooldown_days", 180))
        cutoff_date     = (now - timedelta(days=inactivity_days)).date()
        cooldown_start  = now - timedelta(days=cooldown_days)

        rows = session.exec(text("""
            SELECT c.email, c.name, c.ultima_visita
            FROM contacts c
            WHERE c.opted_in = TRUE
              AND c.ultima_visita IS NOT NULL
              AND c.ultima_visita <= :cutoff
              AND NOT EXISTS (
                  SELECT 1 FROM automation_runs ar
                  WHERE ar.automation_id = :aid
                    AND ar.contact_email = c.email
                    AND ar.status = 'sent'
                    AND ar.triggered_at >= :cooldown
              )
            ORDER BY c.ultima_visita ASC
            LIMIT 30
        """), {"cutoff": cutoff_date, "aid": auto_id, "cooldown": cooldown_start}).fetchall()

        for r in rows:
            contacts.append({
                "email":   r.email,
                "name":    r.name or r.email,
                "detail":  f"Sin compra desde {r.ultima_visita}",
                "send_at": now.isoformat(),
                "ready":   True,
            })

    elif auto.trigger_type == "post_visit":
        delay_days  = int(config.get("delay_days", 3))
        target_date = (now - timedelta(days=delay_days)).date()

        rows = session.exec(text("""
            SELECT c.email, c.name, c.ultima_visita
            FROM contacts c
            WHERE c.opted_in = TRUE
              AND c.ultima_visita = :target
              AND NOT EXISTS (
                  SELECT 1 FROM automation_runs ar
                  WHERE ar.automation_id = :aid
                    AND ar.contact_email = c.email
                    AND ar.status = 'sent'
              )
            ORDER BY c.email ASC
            LIMIT 30
        """), {"target": target_date, "aid": auto_id}).fetchall()

        for r in rows:
            contacts.append({
                "email":   r.email,
                "name":    r.name or r.email,
                "detail":  f"Última compra: {r.ultima_visita}",
                "send_at": now.isoformat(),
                "ready":   True,
            })

    else:
        # Shopify event triggers — show unprocessed events within lookback
        topic_map = {
            "placed_order":    "orders/create",
            "fulfilled_order": "orders/fulfilled",
            "cancelled_order": "orders/cancelled",
            "ordered_product": "ordered_product",
            "delivered_shipment": "delivered_shipment",
        }
        topic = topic_map.get(auto.trigger_type)
        if topic:
            delay_hours    = float(config.get("delay_hours", 0))
            lookback_hours = float(config.get("lookback_hours", 48))
            cutoff_recent  = now - timedelta(hours=lookback_hours)

            rows = session.exec(text("""
                SELECT email, payload, created_at
                FROM shopify_events
                WHERE topic = :topic
                  AND processed = FALSE
                  AND email IS NOT NULL
                  AND created_at >= :recent
                ORDER BY created_at ASC
                LIMIT 30
            """), {"topic": topic, "recent": cutoff_recent}).fetchall()

            for r in rows:
                send_at = r.created_at + timedelta(hours=delay_hours)
                payload = r.payload or {}
                order_num = payload.get("order_number", "")
                contacts.append({
                    "email":   r.email,
                    "name":    r.email,
                    "detail":  f"Pedido #{order_num}" if order_num else "",
                    "send_at": send_at.isoformat(),
                    "ready":   _is_ready(send_at),
                })

    return {"count": len(contacts), "contacts": contacts}
