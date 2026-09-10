"""Revenue attribution aligned with Klaviyo defaults + coupon codes.

Klaviyo default (email): last-touch, 5-day lookback after open OR click.
An order is attributed to a message if the contact opened or clicked that
message and placed the order within `window_days` of that interaction.
When multiple messages qualify, the most recent open/click wins.

Additionally, orders that redeem a discount code present in the campaign
template (or issued via coupon_sends for that campaign) are attributed to
that campaign if placed after the campaign was sent and within the window.
Automations get the same coupon-redemption path via coupon_sends.automation_id
(windowed off when that specific code was issued, not a single "sent_at" —
automations trigger per-contact, not in one blast). This second path exists
because a lot of real conversions never register an open/click at all (mail
client strips tracking pixels, contact reads the email lockscreen preview,
clicks days outside the window, etc.) — the coupon redemption is often the
only signal that a message actually converted.

Every query here is scoped by shop_id — contacts.email is only unique per
shop_id, not globally, so joining shopify_orders by email alone (without
also matching shop_id) could attribute one tenant's order to another
tenant's campaign/automation when the same email exists as a customer in
more than one shop.
"""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import text
from sqlmodel import Session

# Klaviyo default email open + click lookback
DEFAULT_ATTRIBUTION_DAYS = 5


def _extract_campaign_coupon_codes(session: Session, campaign_id: int, shop_id: int) -> list[str]:
    """Codes linked to this campaign: coupon_sends + static codes in the template body."""
    codes: set[str] = set()

    # Dynamic / issued codes for this campaign
    for (code,) in session.execute(
        text("""
            SELECT DISTINCT UPPER(TRIM(code))
            FROM coupon_sends
            WHERE campaign_id = :cid
              AND shop_id = :shop_id
              AND code IS NOT NULL AND TRIM(code) <> ''
        """),
        {"cid": campaign_id, "shop_id": shop_id},
    ).fetchall():
        if code:
            codes.add(code)

    # Static codes printed in the email template (e.g. PiedrasAgosto25)
    row = session.execute(
        text("""
            SELECT COALESCE(t.html_content, '') || ' ' || COALESCE(t.json_blocks::text, '')
            FROM campaigns c
            LEFT JOIN templates t ON t.id = c.template_id
            WHERE c.id = :cid AND c.shop_id = :shop_id
        """),
        {"cid": campaign_id, "shop_id": shop_id},
    ).fetchone()
    blob = (row[0] if row else "") or ""
    # Prefer explicit coupon-looking tokens (letters + digits, not pure jinja)
    for m in re.finditer(
        r"(?:discount/|cup[oó]n[:\s]*|código[:\s]*|codigo[:\s]*|>)([A-Za-z][A-Za-z0-9_-]{4,40})",
        blob,
        flags=re.IGNORECASE,
    ):
        token = m.group(1).strip().upper()
        if token in {"COUPON_CODE", "CODIGO", "CÓDIGO", "DISCOUNT"}:
            continue
        if "{{" in token or "{%" in token:
            continue
        codes.add(token)

    # Also catch bare campaign-style codes that mix letters+digits (PiedrasAgosto25)
    for m in re.finditer(r"\b([A-Za-z]{3,}[0-9][A-Za-z0-9_-]{0,20})\b", blob):
        token = m.group(1).upper()
        if token not in {"HTML5", "H1", "H2", "H3"}:
            codes.add(token)

    return sorted(codes)


def get_campaign_attribution(
    session: Session,
    campaign_id: int,
    shop_id: int,
    *,
    window_days: int = DEFAULT_ATTRIBUTION_DAYS,
    order_date_from: datetime | None = None,
    order_date_to: datetime | None = None,
) -> dict:
    """
    Attribute Shopify orders to a campaign:
      1) Open/click last-touch within `window_days` (Klaviyo-style), and/or
      2) Order used a coupon code from this campaign's template / coupon_sends
         after the campaign was sent (within `window_days` of sent_at, or of
         the open/click if present).
    """
    params: dict = {"campaign_id": campaign_id, "window_days": window_days, "shop_id": shop_id}
    date_filter = ""
    if order_date_from is not None:
        date_filter += " AND so.created_at >= :order_from"
        params["order_from"] = order_date_from
    if order_date_to is not None:
        date_filter += " AND so.created_at < :order_to"
        params["order_to"] = order_date_to

    coupon_codes = _extract_campaign_coupon_codes(session, campaign_id, shop_id)
    params["coupon_codes"] = coupon_codes

    # shop_id match OR legacy NULL rows (pre-fix webhooks) for this tenant's orders
    shop_match = "(so.shop_id = :shop_id OR so.shop_id IS NULL)"

    coupon_cte = ""
    coupon_union = ""
    if coupon_codes:
        coupon_cte = f"""
            , coupon_orders AS (
                SELECT
                    CAST(:campaign_id AS INTEGER) AS campaign_id,
                    so.id AS order_id,
                    so.total_price::numeric AS total_price,
                    LOWER(so.email) AS email,
                    so.created_at AS touch_at
                FROM shopify_orders so
                JOIN campaigns c ON c.id = :campaign_id AND c.shop_id = :shop_id
                WHERE {shop_match}
                  AND so.email IS NOT NULL AND so.email <> ''
                  AND so.cancelled_at IS NULL
                  AND COALESCE(so.financial_status, '') NOT IN ('voided', 'refunded')
                  AND c.sent_at IS NOT NULL
                  AND so.created_at >= c.sent_at
                  AND so.created_at <= c.sent_at + make_interval(days => :window_days)
                  AND EXISTS (
                      SELECT 1
                      FROM jsonb_array_elements(COALESCE(so.raw->'discount_codes', '[]'::jsonb)) dc
                      WHERE UPPER(TRIM(dc->>'code')) = ANY(:coupon_codes)
                  )
                  {date_filter}
            )
        """
        coupon_union = """
                UNION ALL
                SELECT campaign_id, order_id, total_price, email, touch_at FROM coupon_orders
        """

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
                     AND {shop_match}
                WHERE (cs.clicked_at IS NOT NULL OR cs.opened_at IS NOT NULL)
                  AND cs.shop_id = :shop_id
                  {date_filter}
            )
            {coupon_cte}
            , combined AS (
                SELECT campaign_id, order_id, total_price, email, touch_at FROM touches
                WHERE touch_at IS NOT NULL
                {coupon_union}
            ),
            attributed AS (
                SELECT DISTINCT ON (order_id)
                    campaign_id, order_id, total_price, email
                FROM combined
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
        "coupon_codes": coupon_codes,
    }


def list_campaign_attribution_summary(
    session: Session,
    shop_id: int,
    *,
    order_date_from: datetime,
    order_date_to: datetime,
    window_days: int = DEFAULT_ATTRIBUTION_DAYS,
) -> list[dict]:
    """Per-campaign last-touch open/click + coupon-redemption attribution for dashboard."""
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
                     AND (so.shop_id = :shop_id OR so.shop_id IS NULL)
                WHERE (cs.clicked_at IS NOT NULL OR cs.opened_at IS NOT NULL)
                  AND cs.shop_id = :shop_id
                  AND so.created_at >= :order_from
                  AND so.created_at < :order_to
            ),
            coupon_orders AS (
                SELECT
                    csend.campaign_id,
                    so.id AS order_id,
                    so.total_price::numeric AS total_price,
                    csend.created_at AS touch_at
                FROM shopify_orders so
                JOIN coupon_sends csend
                     ON csend.campaign_id IS NOT NULL
                    AND csend.shop_id = :shop_id
                    AND LOWER(csend.contact_email) = LOWER(so.email)
                WHERE (so.shop_id = :shop_id OR so.shop_id IS NULL)
                  AND so.cancelled_at IS NULL
                  AND COALESCE(so.financial_status, '') NOT IN ('voided', 'refunded')
                  AND so.created_at >= csend.created_at
                  AND so.created_at <= csend.created_at + make_interval(days => :window_days)
                  AND so.created_at >= :order_from
                  AND so.created_at < :order_to
                  AND EXISTS (
                      SELECT 1
                      FROM jsonb_array_elements(COALESCE(so.raw->'discount_codes', '[]'::jsonb)) dc
                      WHERE UPPER(TRIM(dc->>'code')) = UPPER(TRIM(csend.code))
                  )
            ),
            combined AS (
                SELECT campaign_id, order_id, total_price, touch_at FROM touches
                WHERE touch_at IS NOT NULL
                UNION ALL
                SELECT campaign_id, order_id, total_price, touch_at FROM coupon_orders
            ),
            attributed AS (
                SELECT DISTINCT ON (order_id)
                    campaign_id, order_id, total_price
                FROM combined
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
                WHERE sent_at IS NOT NULL AND shop_id = :shop_id
                GROUP BY campaign_id
            )
            SELECT c.id, c.name, r.recipients, a.orders, a.revenue
            FROM agg a
            JOIN campaigns c ON c.id = a.campaign_id AND c.shop_id = :shop_id
            JOIN recipients r ON r.campaign_id = c.id
            ORDER BY a.revenue DESC
        """),
        {
            "order_from": order_date_from,
            "order_to": order_date_to,
            "window_days": window_days,
            "shop_id": shop_id,
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
    shop_id: int,
    *,
    order_date_from: datetime,
    order_date_to: datetime,
    window_days: int = DEFAULT_ATTRIBUTION_DAYS,
) -> list[dict]:
    """Per-automation last-touch open/click + coupon-redemption attribution for dashboard."""
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
                     AND (so.shop_id = :shop_id OR so.shop_id IS NULL)
                WHERE ar.status = 'sent'
                  AND (ar.clicked_at IS NOT NULL OR ar.opened_at IS NOT NULL)
                  AND ar.shop_id = :shop_id
                  AND so.created_at >= :order_from
                  AND so.created_at < :order_to
            ),
            coupon_orders AS (
                SELECT
                    csend.automation_id,
                    so.id AS order_id,
                    so.total_price::numeric AS total_price,
                    LOWER(so.email) AS email,
                    csend.created_at AS touch_at
                FROM shopify_orders so
                JOIN coupon_sends csend
                     ON csend.automation_id IS NOT NULL
                    AND csend.shop_id = :shop_id
                    AND LOWER(csend.contact_email) = LOWER(so.email)
                WHERE (so.shop_id = :shop_id OR so.shop_id IS NULL)
                  AND so.cancelled_at IS NULL
                  AND COALESCE(so.financial_status, '') NOT IN ('voided', 'refunded')
                  AND so.created_at >= csend.created_at
                  AND so.created_at <= csend.created_at + make_interval(days => :window_days)
                  AND so.created_at >= :order_from
                  AND so.created_at < :order_to
                  AND EXISTS (
                      SELECT 1
                      FROM jsonb_array_elements(COALESCE(so.raw->'discount_codes', '[]'::jsonb)) dc
                      WHERE UPPER(TRIM(dc->>'code')) = UPPER(TRIM(csend.code))
                  )
            ),
            combined AS (
                SELECT automation_id, order_id, total_price, email, touch_at FROM touches
                WHERE touch_at IS NOT NULL
                UNION ALL
                SELECT automation_id, order_id, total_price, email, touch_at FROM coupon_orders
            ),
            attributed AS (
                SELECT DISTINCT ON (order_id)
                    automation_id, order_id, total_price, email
                FROM combined
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
                WHERE status = 'sent' AND executed_at IS NOT NULL AND shop_id = :shop_id
                GROUP BY automation_id
            )
            SELECT a.id, a.name, s.sends, agg.orders, agg.revenue
            FROM agg
            JOIN automations a ON a.id = agg.automation_id AND a.shop_id = :shop_id
            JOIN sends s ON s.automation_id = a.id
            ORDER BY agg.revenue DESC
        """),
        {
            "order_from": order_date_from,
            "order_to": order_date_to,
            "window_days": window_days,
            "shop_id": shop_id,
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
    shop_id: int,
    *,
    window_days: int = DEFAULT_ATTRIBUTION_DAYS,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict:
    """
    Attribute Shopify orders to an automation:
      1) Open/click last-touch within `window_days` (Klaviyo-style), and/or
      2) Order redeemed the coupon code coupon_sends issued to that contact for
         this automation, within `window_days` of when that code was issued.
         Needed because a lot of automation conversions (a birthday coupon used
         days later, opened in a client that strips open tracking, etc.) never
         register a click — the coupon redemption is the only signal.
    """
    params: dict = {"aid": automation_id, "window_days": window_days, "shop_id": shop_id}
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

    # shop_id match OR legacy NULL rows (pre-fix webhooks) for this tenant's orders
    shop_match = "(so.shop_id = :shop_id OR so.shop_id IS NULL)"

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
                     AND {shop_match}
                WHERE ar.status = 'sent'
                  AND (ar.clicked_at IS NOT NULL OR ar.opened_at IS NOT NULL)
                  AND ar.shop_id = :shop_id
                  {run_filter}
                  {order_filter}
            ),
            coupon_orders AS (
                SELECT
                    CAST(:aid AS INTEGER) AS automation_id,
                    so.id AS order_id,
                    so.total_price::numeric AS total_price,
                    csend.created_at AS touch_at
                FROM shopify_orders so
                JOIN coupon_sends csend
                     ON csend.automation_id = :aid
                    AND csend.shop_id = :shop_id
                    AND LOWER(csend.contact_email) = LOWER(so.email)
                WHERE {shop_match}
                  AND so.cancelled_at IS NULL
                  AND COALESCE(so.financial_status, '') NOT IN ('voided', 'refunded')
                  AND so.created_at >= csend.created_at
                  AND so.created_at <= csend.created_at + make_interval(days => :window_days)
                  AND EXISTS (
                      SELECT 1
                      FROM jsonb_array_elements(COALESCE(so.raw->'discount_codes', '[]'::jsonb)) dc
                      WHERE UPPER(TRIM(dc->>'code')) = UPPER(TRIM(csend.code))
                  )
                  {order_filter}
            ),
            combined AS (
                SELECT automation_id, order_id, total_price, touch_at FROM touches
                WHERE touch_at IS NOT NULL
                UNION ALL
                SELECT automation_id, order_id, total_price, touch_at FROM coupon_orders
            ),
            attributed AS (
                SELECT DISTINCT ON (order_id)
                    automation_id, order_id, total_price
                FROM combined
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
