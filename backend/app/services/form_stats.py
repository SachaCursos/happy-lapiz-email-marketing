"""Form completion, delivery and revenue statistics."""

from __future__ import annotations

from sqlalchemy import text
from sqlmodel import Session


def _person_key_from_email_col() -> str:
    """Clave de persona a partir de la columna email en form_views."""
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
    Tasa = personas que completaron / personas que vieron el formulario.

    Audiencia (vieron el formulario):
      - Cada email distinto que completó (necesariamente vio el formulario)
      - Más cada visitante anónimo registrado al abrir el popup (pixel)
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
            pixel_viewers AS (
                SELECT DISTINCT {person_key} AS person_key
                FROM form_views
                WHERE form_id = :fid
                  AND source IN ('embed', 'page', 'submit')
            ),
            audience AS (
                SELECT person_key FROM completer_people
                UNION
                SELECT person_key FROM pixel_viewers
                WHERE person_key LIKE 'anon:%%'
                   OR person_key LIKE 'legacy-anon:%%'
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
                (SELECT COUNT(*)::int FROM audience) AS audience_size,
                (SELECT COUNT(*)::int FROM pixel_viewers
                 WHERE person_key LIKE 'anon:%%'
                    OR person_key LIKE 'legacy-anon:%%') AS anonymous_viewers,
                (SELECT COUNT(*)::int FROM form_views
                 WHERE form_id = :fid AND source IN ('embed', 'page')) AS popup_impressions,
                (SELECT orders FROM revenue) AS total_orders,
                (SELECT revenue FROM revenue) AS total_revenue
        """),
        {"fid": fid},
    ).one()

    completed = int(row.completed or 0)
    audience_size = int(row.audience_size or 0)
    anonymous_viewers = int(row.anonymous_viewers or 0)
    popup_impressions = int(row.popup_impressions or 0)
    total_orders = int(row.total_orders or 0)
    total_revenue = float(row.total_revenue or 0)

    completion_rate = round(completed / audience_size * 100, 1) if audience_size > 0 else None

    return {
        "form_id": fid,
        "completed": completed,
        "received": audience_size,
        "audience_size": audience_size,
        "popup_viewers": audience_size,
        "popup_views": popup_impressions,
        "anonymous_viewers": anonymous_viewers,
        "completion_rate": completion_rate,
        "total_revenue": total_revenue,
        "total_orders": total_orders,
    }
