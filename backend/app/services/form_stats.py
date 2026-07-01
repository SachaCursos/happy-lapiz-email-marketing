"""Form completion, delivery and revenue statistics."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlmodel import Session


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
    Tasa real = completados / personas que abrieron el popup (solo tracking embed/page).

    No se infieren aperturas desde envíos históricos: solo cuenta opens registrados.
    """
    fid = int(form_id)
    person_key = _person_key_from_email_col()

    row = session.execute(
        text(f"""
            WITH completer_people AS (
                SELECT DISTINCT LOWER(TRIM(email)) AS person_key
                FROM form_submissions
                WHERE form_id = :fid
                  AND email IS NOT NULL
                  AND TRIM(email) <> ''
            ),
            popup_viewers AS (
                SELECT DISTINCT {person_key} AS person_key
                FROM form_views
                WHERE form_id = :fid
                  AND source IN ('embed', 'page')
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
                (SELECT COUNT(*)::int FROM completer_people) AS completed,
                (SELECT COUNT(*)::int FROM popup_viewers) AS popup_viewers,
                (SELECT COUNT(*)::int FROM form_views
                 WHERE form_id = :fid AND source IN ('embed', 'page')) AS popup_impressions,
                (SELECT orders FROM revenue) AS total_orders,
                (SELECT revenue FROM revenue) AS total_revenue
        """),
        {"fid": fid},
    ).one()

    completed = int(row.completed or 0)
    popup_viewers = int(row.popup_viewers or 0)
    popup_impressions = int(row.popup_impressions or 0)
    total_orders = int(row.total_orders or 0)
    total_revenue = float(row.total_revenue or 0)

    completion_rate: Optional[float] = None
    if popup_viewers > 0:
        completion_rate = round(min(100.0, completed / popup_viewers * 100), 1)

    not_completed = max(0, popup_viewers - completed) if popup_viewers >= completed else 0

    return {
        "form_id": fid,
        "completed": completed,
        "received": popup_viewers,
        "audience_size": popup_viewers,
        "popup_viewers": popup_viewers,
        "popup_views": popup_impressions,
        "anonymous_viewers": not_completed,
        "completion_rate": completion_rate,
        "tracking_ready": popup_viewers > 0,
        "total_revenue": total_revenue,
        "total_orders": total_orders,
    }
