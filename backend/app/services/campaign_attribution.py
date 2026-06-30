"""Revenue attribution for campaigns — order must follow each recipient's send."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlmodel import Session

DEFAULT_ATTRIBUTION_DAYS = 7


def get_campaign_attribution(
    session: Session,
    campaign_id: int,
    *,
    window_days: int = DEFAULT_ATTRIBUTION_DAYS,
    order_date_from: datetime | None = None,
    order_date_to: datetime | None = None,
) -> dict:
    """
    Attribute Shopify orders to a campaign when:
      - the contact received the campaign (campaign_sends.sent_at set), and
      - the order was placed at or after that send, and
      - the order is within `window_days` after that send.
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
            SELECT
                COUNT(*)::int AS bookings,
                COALESCE(SUM(total_price), 0)::float AS revenue,
                COUNT(DISTINCT email)::int AS converted_contacts
            FROM (
                SELECT DISTINCT ON (so.id)
                    so.id,
                    so.total_price::numeric AS total_price,
                    LOWER(ct.email) AS email
                FROM campaign_sends cs
                JOIN contacts ct ON ct.id = cs.contact_id
                JOIN shopify_orders so ON LOWER(so.email) = LOWER(ct.email)
                WHERE cs.campaign_id = :campaign_id
                  AND cs.sent_at IS NOT NULL
                  AND so.created_at >= cs.sent_at
                  AND so.created_at <= cs.sent_at + make_interval(days => :window_days)
                  {date_filter}
                ORDER BY so.id
            ) attributed
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
    """Per-campaign attribution for dashboard (distinct orders per campaign)."""
    rows = session.execute(
        text("""
            WITH attributed AS (
                SELECT DISTINCT ON (so.id, cs.campaign_id)
                    cs.campaign_id,
                    so.id AS order_id,
                    so.total_price::numeric AS total_price
                FROM campaign_sends cs
                JOIN contacts ct ON ct.id = cs.contact_id
                JOIN shopify_orders so ON LOWER(so.email) = LOWER(ct.email)
                WHERE cs.sent_at IS NOT NULL
                  AND so.created_at >= :order_from
                  AND so.created_at < :order_to
                  AND so.created_at >= cs.sent_at
                  AND so.created_at <= cs.sent_at + make_interval(days => :window_days)
                ORDER BY so.id, cs.campaign_id
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
