"""Form completion, delivery and revenue statistics."""

from __future__ import annotations

from sqlalchemy import text
from sqlmodel import Session


def get_form_stats(session: Session, form_id: int) -> dict:
    fid = int(form_id)
    pattern = f"%/forms/{fid}/%"

    row = session.execute(
        text("""
            WITH form_templates AS (
                SELECT t.id
                FROM templates t
                WHERE t.html_content ILIKE :pattern
                   OR COALESCE(t.json_blocks::text, '') ILIKE :pattern
            ),
            email_sent AS (
                SELECT DISTINCT LOWER(ct.email) AS rkey
                FROM campaign_sends cs
                JOIN contacts ct ON ct.id = cs.contact_id
                JOIN campaigns c ON c.id = cs.campaign_id
                JOIN form_templates ft ON ft.id = c.template_id
                WHERE cs.sent_at IS NOT NULL
                  AND cs.status NOT IN ('failed', 'queued')

                UNION

                SELECT DISTINCT LOWER(ar.contact_email) AS rkey
                FROM automation_runs ar
                WHERE ar.status = 'sent'
                  AND ar.executed_at IS NOT NULL
                  AND ar.contact_email IS NOT NULL
                  AND ar.contact_email <> ''
                  AND ar.automation_id IN (
                      SELECT a.id
                      FROM automations a
                      WHERE a.template_id IN (SELECT id FROM form_templates)
                         OR EXISTS (
                             SELECT 1
                             FROM jsonb_array_elements(COALESCE(a.steps::jsonb, '[]'::jsonb)) step
                             WHERE (step->>'template_id')::int IN (SELECT id FROM form_templates)
                         )
                  )
            ),
            viewers AS (
                SELECT DISTINCT CASE
                    WHEN email IS NOT NULL AND TRIM(email) <> '' THEN LOWER(TRIM(email))
                    ELSE 'anon:' || id::text
                END AS rkey
                FROM form_views
                WHERE form_id = :fid
            ),
            all_recipients AS (
                SELECT rkey FROM email_sent WHERE rkey IS NOT NULL AND rkey <> ''
                UNION
                SELECT rkey FROM viewers
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
                (SELECT COUNT(*)::int FROM all_recipients) AS received,
                (SELECT orders FROM revenue) AS total_orders,
                (SELECT revenue FROM revenue) AS total_revenue
        """),
        {"fid": fid, "pattern": pattern},
    ).one()

    completed = int(row.completed or 0)
    received = int(row.received or 0)
    total_orders = int(row.total_orders or 0)
    total_revenue = float(row.total_revenue or 0)
    completion_rate = round(completed / received * 100, 1) if received else 0.0

    return {
        "form_id": fid,
        "completed": completed,
        "received": received,
        "completion_rate": completion_rate,
        "total_revenue": total_revenue,
        "total_orders": total_orders,
    }
