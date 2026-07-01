"""Form completion, delivery and revenue statistics."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlmodel import Session, select

from app.models.form import SignupForm


def ensure_form_stats_epoch(session: Session) -> None:
    """
    Primera vez: fija stats_since en todos los formularios y limpia vistas
    históricas poco fiables. Los formularios nuevos solo reciben su propia fecha.
    """
    forms = list(session.exec(select(SignupForm)).all())
    if not forms:
        return

    unset = [f for f in forms if f.stats_since is None]
    if not unset:
        return

    now = datetime.utcnow()
    first_global_reset = len(unset) == len(forms)
    if first_global_reset:
        session.execute(text("DELETE FROM form_views"))

    for form in unset:
        form.stats_since = now
        session.add(form)
    session.commit()


def _person_key_from_email_col() -> str:
    return """
        CASE
            WHEN email IS NOT NULL AND TRIM(email) <> ''
                AND LOWER(TRIM(email)) NOT LIKE 'anon:%%'
                THEN LOWER(TRIM(email))
            WHEN email IS NOT NULL AND TRIM(email) <> ''
                AND LOWER(TRIM(email)) LIKE 'anon:%%'
                THEN LOWER(TRIM(email))
            ELSE 'legacy-anon:' || id::text
        END
    """


def get_form_stats(session: Session, form_id: int) -> dict:
    """
    Tasa = completados desde stats_since / personas que abrieron el popup (embed/page)
    registradas desde stats_since. Sin datos históricos mezclados.
    """
    form = session.get(SignupForm, form_id)
    if not form:
        return {
            "form_id": form_id,
            "completed": 0,
            "completed_total": 0,
            "completed_period": 0,
            "received": 0,
            "audience_size": 0,
            "popup_viewers": 0,
            "popup_views": 0,
            "completion_rate": None,
            "tracking_ready": False,
            "stats_since": None,
            "total_revenue": 0.0,
            "total_orders": 0,
        }

    ensure_form_stats_epoch(session)
    session.refresh(form)

    fid = int(form_id)
    since = form.stats_since
    person_key = _person_key_from_email_col()

    row = session.execute(
        text(f"""
            WITH completer_total AS (
                SELECT COUNT(DISTINCT LOWER(TRIM(email)))::int AS cnt
                FROM form_submissions
                WHERE form_id = :fid
                  AND email IS NOT NULL
                  AND TRIM(email) <> ''
            ),
            completer_period AS (
                SELECT COUNT(DISTINCT LOWER(TRIM(email)))::int AS cnt
                FROM form_submissions
                WHERE form_id = :fid
                  AND email IS NOT NULL
                  AND TRIM(email) <> ''
                  AND (:since IS NULL OR created_at >= :since)
            ),
            popup_viewers AS (
                SELECT DISTINCT {person_key} AS person_key
                FROM form_views
                WHERE form_id = :fid
                  AND source IN ('embed', 'page')
                  AND (:since IS NULL OR viewed_at >= :since)
            ),
            revenue AS (
                SELECT
                    COUNT(*)::int AS orders,
                    COALESCE(SUM(total_price), 0)::float AS revenue
                FROM (
                    SELECT DISTINCT ON (so.id)
                        so.id,
                        so.total_price::numeric AS total_price
                    FROM form_submissions fs
                    JOIN shopify_orders so ON LOWER(so.email) = LOWER(fs.email)
                    WHERE fs.form_id = :fid
                      AND so.created_at >= fs.created_at
                    ORDER BY so.id
                ) attributed
            )
            SELECT
                (SELECT cnt FROM completer_total) AS completed_total,
                (SELECT cnt FROM completer_period) AS completed_period,
                (SELECT COUNT(*)::int FROM popup_viewers) AS popup_viewers,
                (SELECT COUNT(*)::int FROM form_views
                 WHERE form_id = :fid
                   AND source IN ('embed', 'page')
                   AND (:since IS NULL OR viewed_at >= :since)) AS popup_impressions,
                (SELECT orders FROM revenue) AS total_orders,
                (SELECT revenue FROM revenue) AS total_revenue
        """),
        {"fid": fid, "since": since},
    ).one()

    completed_total = int(row.completed_total or 0)
    completed_period = int(row.completed_period or 0)
    popup_viewers = int(row.popup_viewers or 0)
    popup_impressions = int(row.popup_impressions or 0)
    total_orders = int(row.total_orders or 0)
    total_revenue = float(row.total_revenue or 0)

    completion_rate: Optional[float] = None
    if popup_viewers > 0:
        completion_rate = round(completed_period / popup_viewers * 100, 1)

    return {
        "form_id": fid,
        "completed": completed_total,
        "completed_total": completed_total,
        "completed_period": completed_period,
        "received": popup_viewers,
        "audience_size": popup_viewers,
        "popup_viewers": popup_viewers,
        "popup_views": popup_impressions,
        "completion_rate": completion_rate,
        "tracking_ready": popup_viewers > 0,
        "stats_since": since.isoformat() if since else None,
        "total_revenue": total_revenue,
        "total_orders": total_orders,
    }
