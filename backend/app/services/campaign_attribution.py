"""Revenue attribution aligned with Klaviyo defaults.

Klaviyo default (email): last-touch, 5-day lookback after open OR click.
An order is attributed to a message if the contact opened or clicked that
message and placed the order within `window_days` of that interaction.
When multiple messages qualify, the most recent open/click wins.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlmodel import Session

# Klaviyo default email open + click lookback
DEFAULT_ATTRIBUTION_DAYS = 5


def get_campaign_attribution(
    session: Session,
    campaign_id: int,
    *,
    window_days: int = DEFAULT_ATTRIBUTION_DAYS,
    order_date_from: datetime | None = None,
    order_date_to: datetime | None = None,
) -> dict:
    """
    Attribute Shopify orders to a campaign (Klaviyo-style):
      - contact opened or clicked the email, and
      - order was placed within `window_days` after that open/click, and
      - this campaign was the last email touch among campaigns for that order.
    """
    params: dict = {"campaign_id": campaign_id, "window_days": window_days}
    date_filter = ""
    if order_date_from is not None:
        date_filter += " AND so.created_at >= :order_from"
        params["order_from"] = order_date_from
    if order_date_to is not None:
        date_filter += " AND so.created_at < :order_to"
        params["order_to"] = order_date_to

    row = session.execute(
        text(f"""
            WITH touches AS (
                SELECT
                    cs.campaign_id,
                    so.id AS order_id,
                    so.total_price::numeric AS total_price,
                    LOWER(ct.email) AS email,
                    GREATEST(
                        CASE
                            WHEN cs.clicked_at IS NOT NULL
                             AND so.created_at >= cs.clicked_at
                             AND so.created_at <= cs.clicked_at
                                 + make_interval(days => :window_days)
                            THEN cs.clicked_at
                        END,
                        CASE
                            WHEN cs.opened_at IS NOT NULL
                             AND so.created_at >= cs.opened_at
                             AND so.created_at <= cs.opened_at
                                 + make_interval(days => :window_days)
                            THEN cs.opened_at
                        END
                    ) AS touch_at
                FROM campaign_sends cs
                JOIN contacts ct ON ct.id = cs.contact_id
                JOIN shopify_orders so ON LOWER(so.email) = LOWER(ct.email)
                WHERE (cs.clicked_at IS NOT NULL OR cs.opened_at IS NOT NULL)
                  {date_filter}
            ),
            attributed AS (
                SELECT DISTINCT ON (order_id)
                    campaign_id, order_id, total_price, email
                FROM touches
                WHERE touch_at IS NOT NULL
                ORDER BY order_id, touch_at DESC NULLS LAST
            )
            SELECT
                COUNT(*)::int AS bookings,
                COALESCE(SUM(total_price), 0)::float AS revenue,
                COUNT(DISTINCT email)::int AS converted_contacts
            FROM attributed
            WHERE campaign_id = :campaign_id
        """),
        params,
    ).one()

    return {
        "bookings": int(row.bookings or 0),
        "revenue": float(row.revenue or 0),
        "converted_contacts": int(row.converted_contacts or 0),
    }


def list_campaign_attribution_summary(
    session: Session,
    *,
    order_date_from: datetime,
    order_date_to: datetime,
    window_days: int = DEFAULT_ATTRIBUTION_DAYS,
) -> list[dict]:
    """Per-campaign last-touch open/click attribution for dashboard."""
    rows = session.execute(
        text("""
            WITH touches AS (
                SELECT
                    cs.campaign_id,
                    so.id AS order_id,
                    so.total_price::numeric AS total_price,
                    GREATEST(
                        CASE
                            WHEN cs.clicked_at IS NOT NULL
                             AND so.created_at >= cs.clicked_at
                             AND so.created_at <= cs.clicked_at
                                 + make_interval(days => :window_days)
                            THEN cs.clicked_at
                        END,
                        CASE
                            WHEN cs.opened_at IS NOT NULL
                             AND so.created_at >= cs.opened_at
                             AND so.created_at <= cs.opened_at
                                 + make_interval(days => :window_days)
                            THEN cs.opened_at
                        END
                    ) AS touch_at
                FROM campaign_sends cs
                JOIN contacts ct ON ct.id = cs.contact_id
                JOIN shopify_orders so ON LOWER(so.email) = LOWER(ct.email)
                WHERE (cs.clicked_at IS NOT NULL OR cs.opened_at IS NOT NULL)
                  AND so.created_at >= :order_from
                  AND so.created_at < :order_to
            ),
            attributed AS (
                SELECT DISTINCT ON (order_id)
                    campaign_id, order_id, total_price
                FROM touches
                WHERE touch_at IS NOT NULL
                ORDER BY order_id, touch_at DESC NULLS LAST
            ),
            agg AS (
                SELECT
                    campaign_id,
                    COUNT(*)::int AS orders,
                    COALESCE(SUM(total_price), 0)::float AS revenue
                FROM attributed
                GROUP BY campaign_id
            ),
            recipients AS (
                SELECT campaign_id, COUNT(DISTINCT contact_id)::int AS recipients
                FROM campaign_sends
                WHERE sent_at IS NOT NULL
                GROUP BY campaign_id
            )
            SELECT c.id, c.name, r.recipients, a.orders, a.revenue
            FROM agg a
            JOIN campaigns c ON c.id = a.campaign_id
            JOIN recipients r ON r.campaign_id = c.id
            ORDER BY a.revenue DESC
        """),
        {
            "order_from": order_date_from,
            "order_to": order_date_to,
            "window_days": window_days,
        },
    ).fetchall()

    return [
        {
            "id": r[0],
            "name": r[1],
            "recipients": int(r[2]),
            "orders": int(r[3]),
            "revenue": float(r[4]),
        }
        for r in rows
    ]


def list_automation_attribution_summary(
    session: Session,
    *,
    order_date_from: datetime,
    order_date_to: datetime,
    window_days: int = DEFAULT_ATTRIBUTION_DAYS,
) -> list[dict]:
    """Per-automation last-touch open/click attribution for dashboard."""
    rows = session.execute(
        text("""
            WITH touches AS (
                SELECT
                    ar.automation_id,
                    so.id AS order_id,
                    so.total_price::numeric AS total_price,
                    LOWER(ar.contact_email) AS email,
                    GREATEST(
                        CASE
                            WHEN ar.clicked_at IS NOT NULL
                             AND so.created_at >= ar.clicked_at
                             AND so.created_at <= ar.clicked_at
                                 + make_interval(days => :window_days)
                            THEN ar.clicked_at
                        END,
                        CASE
                            WHEN ar.opened_at IS NOT NULL
                             AND so.created_at >= ar.opened_at
                             AND so.created_at <= ar.opened_at
                                 + make_interval(days => :window_days)
                            THEN ar.opened_at
                        END
                    ) AS touch_at
                FROM automation_runs ar
                JOIN shopify_orders so ON LOWER(so.email) = LOWER(ar.contact_email)
                WHERE ar.status = 'sent'
                  AND (ar.clicked_at IS NOT NULL OR ar.opened_at IS NOT NULL)
                  AND so.created_at >= :order_from
                  AND so.created_at < :order_to
            ),
            attributed AS (
                SELECT DISTINCT ON (order_id)
                    automation_id, order_id, total_price, email
                FROM touches
                WHERE touch_at IS NOT NULL
                ORDER BY order_id, touch_at DESC NULLS LAST
            ),
            agg AS (
                SELECT
                    automation_id,
                    COUNT(*)::int AS orders,
                    COALESCE(SUM(total_price), 0)::float AS revenue
                FROM attributed
                GROUP BY automation_id
            ),
            sends AS (
                SELECT automation_id, COUNT(DISTINCT contact_email)::int AS sends
                FROM automation_runs
                WHERE status = 'sent' AND executed_at IS NOT NULL
                GROUP BY automation_id
            )
            SELECT a.id, a.name, s.sends, agg.orders, agg.revenue
            FROM agg
            JOIN automations a ON a.id = agg.automation_id
            JOIN sends s ON s.automation_id = a.id
            ORDER BY agg.revenue DESC
        """),
        {
            "order_from": order_date_from,
            "order_to": order_date_to,
            "window_days": window_days,
        },
    ).fetchall()

    return [
        {
            "id": r[0],
            "name": r[1],
            "sends": int(r[2]),
            "orders": int(r[3]),
            "revenue": float(r[4]),
        }
        for r in rows
    ]


def get_automation_attribution(
    session: Session,
    automation_id: int,
    *,
    window_days: int = DEFAULT_ATTRIBUTION_DAYS,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict:
    """Klaviyo-style open/click last-touch attribution for one automation."""
    params: dict = {"aid": automation_id, "window_days": window_days}
    run_filter = ""
    order_filter = ""
    if date_from is not None:
        run_filter += " AND ar.triggered_at >= :date_from"
        order_filter += " AND so.created_at >= :date_from"
        params["date_from"] = date_from
    if date_to is not None:
        run_filter += " AND ar.triggered_at < :date_to"
        order_filter += " AND so.created_at < :date_to"
        params["date_to"] = date_to

    row = session.execute(
        text(f"""
            WITH touches AS (
                SELECT
                    ar.automation_id,
                    so.id AS order_id,
                    so.total_price::numeric AS total_price,
                    GREATEST(
                        CASE
                            WHEN ar.clicked_at IS NOT NULL
                             AND so.created_at >= ar.clicked_at
                             AND so.created_at <= ar.clicked_at
                                 + make_interval(days => :window_days)
                            THEN ar.clicked_at
                        END,
                        CASE
                            WHEN ar.opened_at IS NOT NULL
                             AND so.created_at >= ar.opened_at
                             AND so.created_at <= ar.opened_at
                                 + make_interval(days => :window_days)
                            THEN ar.opened_at
                        END
                    ) AS touch_at
                FROM automation_runs ar
                JOIN shopify_orders so ON LOWER(so.email) = LOWER(ar.contact_email)
                WHERE ar.status = 'sent'
                  AND (ar.clicked_at IS NOT NULL OR ar.opened_at IS NOT NULL)
                  {run_filter}
                  {order_filter}
            ),
            attributed AS (
                SELECT DISTINCT ON (order_id)
                    automation_id, order_id, total_price
                FROM touches
                WHERE touch_at IS NOT NULL
                ORDER BY order_id, touch_at DESC NULLS LAST
            )
            SELECT
                COUNT(*)::int AS orders,
                COALESCE(SUM(total_price), 0)::float AS revenue
            FROM attributed
            WHERE automation_id = :aid
        """),
        params,
    ).one()

    return {
        "orders": int(row.orders or 0),
        "revenue": float(row.revenue or 0),
    }
