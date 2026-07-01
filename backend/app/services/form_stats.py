"""Form completion, delivery and revenue statistics."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlmodel import Session


def _person_key_sql() -> str:
    """Identificador único por persona: email real o anon:sesión."""
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
    fid = int(form_id)
    person_key = _person_key_sql()

    row = session.execute(
        text(f"""
            WITH live_views AS (
                SELECT id, email, viewed_at
                FROM form_views
                WHERE form_id = :fid
                  AND source IN ('embed', 'page')
            ),
            viewer_people AS (
                SELECT DISTINCT {person_key} AS person_key
                FROM live_views
            ),
            completed AS (
                SELECT COUNT(DISTINCT LOWER(email))::int AS cnt
                FROM form_submissions
                WHERE form_id = :fid
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
                (SELECT cnt FROM completed) AS completed,
                (SELECT COUNT(*)::int FROM live_views) AS popup_views,
                (SELECT COUNT(*)::int FROM viewer_people) AS popup_viewers,
                (SELECT orders FROM revenue) AS total_orders,
                (SELECT revenue FROM revenue) AS total_revenue
        """),
        {"fid": fid},
    ).one()

    completed = int(row.completed or 0)
    popup_views = int(row.popup_views or 0)
    popup_viewers = int(row.popup_viewers or 0)
    total_orders = int(row.total_orders or 0)
    total_revenue = float(row.total_revenue or 0)

    completion_rate: Optional[float] = None
    if popup_viewers > 0 and completed <= popup_viewers:
        completion_rate = round(completed / popup_viewers * 100, 1)

    return {
        "form_id": fid,
        "completed": completed,
        "received": popup_viewers,
        "popup_views": popup_views,
        "popup_viewers": popup_viewers,
        "completion_rate": completion_rate,
        "total_revenue": total_revenue,
        "total_orders": total_orders,
    }
