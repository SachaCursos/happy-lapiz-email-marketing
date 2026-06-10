from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select, func, text
from app.database import get_session
from app.core.deps import get_current_user
from app.models.user import User
from app.models.contact import Contact
from app.models.campaign import Campaign, CampaignSend
from app.models.segment import Segment
from app.models.template import Template

router = APIRouter()


@router.get("/overview")
def overview(session: Session = Depends(get_session), _: User = Depends(get_current_user)):
    total_contacts = session.exec(select(func.count(Contact.id))).one()
    opted_in = session.exec(select(func.count(Contact.id)).where(Contact.opted_in == True)).one()  # noqa
    total_campaigns = session.exec(select(func.count(Campaign.id))).one()
    sent_campaigns = session.exec(select(func.count(Campaign.id)).where(Campaign.status == "sent")).one()
    total_sends = session.exec(select(func.count(CampaignSend.id))).one()
    delivered = session.exec(select(func.count(CampaignSend.id)).where(CampaignSend.status == "delivered")).one()
    opened = session.exec(select(func.count(CampaignSend.id)).where(CampaignSend.opened_at.isnot(None))).one()
    total_segments = session.exec(select(func.count(Segment.id))).one()
    total_templates = session.exec(select(func.count(Template.id))).one()

    return {
        "contacts": {"total": total_contacts, "opted_in": opted_in},
        "campaigns": {"total": total_campaigns, "sent": sent_campaigns},
        "sends": {
            "total": total_sends,
            "delivered": delivered,
            "opened": opened,
            "open_rate": round(opened / delivered * 100, 1) if delivered else 0,
        },
        "segments": total_segments,
        "templates": total_templates,
    }


@router.get("/campaigns/recent")
def recent_campaigns(session: Session = Depends(get_session), _: User = Depends(get_current_user)):
    campaigns = session.exec(
        select(Campaign).where(Campaign.status == "sent").order_by(Campaign.sent_at.desc()).limit(5)
    ).all()
    result = []
    for c in campaigns:
        sends = session.exec(select(CampaignSend).where(CampaignSend.campaign_id == c.id)).all()
        total = len(sends)
        opened = sum(1 for s in sends if s.opened_at)
        result.append({
            "id": c.id,
            "name": c.name,
            "subject": c.subject,
            "sent_at": c.sent_at,
            "total": total,
            "open_rate": round(opened / total * 100, 1) if total else 0,
        })
    return result


@router.get("/klaviyo-campaigns")
def klaviyo_campaigns(session: Session = Depends(get_session), _: User = Depends(get_current_user)):
    rows = session.exec(text("""
        SELECT id, name, status, send_time, subject, recipients, delivered,
               open_rate, opens_unique, click_rate, clicks_unique,
               conversion_rate, conversions, conversion_value,
               average_order_value, revenue_per_recipient, audience
        FROM klaviyo_campaigns
        ORDER BY send_time DESC NULLS LAST
    """)).all()
    return [
        {
            "id": r[0], "name": r[1], "status": r[2],
            "send_time": r[3].isoformat() if r[3] else None,
            "subject": r[4], "recipients": r[5], "delivered": r[6],
            "open_rate": float(r[7]) if r[7] else None,
            "opens_unique": r[8],
            "click_rate": float(r[9]) if r[9] else None,
            "clicks_unique": r[10],
            "conversion_rate": float(r[11]) if r[11] else None,
            "conversions": r[12],
            "conversion_value": float(r[13]) if r[13] else None,
            "average_order_value": float(r[14]) if r[14] else None,
            "revenue_per_recipient": float(r[15]) if r[15] else None,
            "audience": r[16],
        }
        for r in rows
    ]


@router.get("/revenue")
def revenue_stats(
    date_from: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """Revenue attribution: Shopify total vs email-attributed sales (campaigns + automations)."""
    now = datetime.now(timezone.utc)
    if date_from:
        dt_from = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
    else:
        dt_from = now - timedelta(days=30)
    if date_to:
        dt_to = datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc) + timedelta(days=1)
    else:
        dt_to = now

    # ── 1. Shopify total ───────────────────────────────────────────────────────
    row = session.execute(text("""
        SELECT COALESCE(SUM(total_price::numeric), 0), COUNT(*)
        FROM shopify_orders
        WHERE created_at >= :from AND created_at < :to
    """), {"from": dt_from, "to": dt_to}).fetchone()
    shopify_total = float(row[0])
    shopify_orders_count = int(row[1])

    prev_from = dt_from - (dt_to - dt_from)
    prev_row = session.execute(text("""
        SELECT COALESCE(SUM(total_price::numeric), 0)
        FROM shopify_orders
        WHERE created_at >= :from AND created_at < :to
    """), {"from": prev_from, "to": dt_from}).fetchone()
    shopify_prev = float(prev_row[0])

    # ── 2. Campaign attributed revenue (orders in window attributed to a campaign send) ─
    camp_rows = session.execute(text("""
        SELECT
            c.id,
            c.name,
            COUNT(DISTINCT cs.contact_id)            AS recipients,
            COUNT(DISTINCT so.id)                    AS orders,
            COALESCE(SUM(so.total_price::numeric), 0) AS revenue
        FROM campaign_sends cs
        JOIN contacts ct ON ct.id = cs.contact_id
        JOIN campaigns c  ON c.id  = cs.campaign_id
        LEFT JOIN shopify_orders so
            ON LOWER(so.email) = LOWER(ct.email)
            AND so.created_at >= :from AND so.created_at < :to
            AND cs.sent_at IS NOT NULL
            AND so.created_at >= cs.sent_at
            AND so.created_at <= cs.sent_at + INTERVAL '7 days'
        WHERE cs.sent_at IS NOT NULL
        GROUP BY c.id, c.name
        ORDER BY revenue DESC
    """), {"from": dt_from, "to": dt_to}).fetchall()

    campaigns_list = [
        {
            "id": r[0], "name": r[1],
            "recipients": int(r[2]), "orders": int(r[3]),
            "revenue": float(r[4]),
        }
        for r in camp_rows
    ]
    campaigns_total = sum(c["revenue"] for c in campaigns_list)
    campaigns_recipients = sum(c["recipients"] for c in campaigns_list)

    # ── 3. Automation attributed revenue ──────────────────────────────────────
    auto_rows = session.execute(text("""
        SELECT
            a.id,
            a.name,
            COUNT(DISTINCT ar.contact_email)          AS sends,
            COUNT(DISTINCT so.id)                     AS orders,
            COALESCE(SUM(so.total_price::numeric), 0)  AS revenue
        FROM automation_runs ar
        JOIN automations a ON a.id = ar.automation_id
        LEFT JOIN shopify_orders so
            ON LOWER(so.email) = LOWER(ar.contact_email)
            AND so.created_at >= :from AND so.created_at < :to
            AND ar.executed_at IS NOT NULL
            AND so.created_at >= ar.executed_at
            AND so.created_at <= ar.executed_at + INTERVAL '7 days'
        WHERE ar.status = 'sent' AND ar.executed_at IS NOT NULL
        GROUP BY a.id, a.name
        ORDER BY revenue DESC
    """), {"from": dt_from, "to": dt_to}).fetchall()

    automations_list = [
        {
            "id": r[0], "name": r[1],
            "sends": int(r[2]), "orders": int(r[3]),
            "revenue": float(r[4]),
        }
        for r in auto_rows
    ]
    automations_total = sum(a["revenue"] for a in automations_list)
    automations_recipients = sum(a["sends"] for a in automations_list)

    # ── 4. Klaviyo campaigns (historical data) ─────────────────────────────────
    klav_rows = session.execute(text("""
        SELECT
            id, name, send_time,
            COALESCE(recipients, 0)       AS recipients,
            COALESCE(conversion_value, 0) AS revenue,
            COALESCE(revenue_per_recipient, 0) AS rpr
        FROM klaviyo_campaigns
        WHERE send_time >= :from AND send_time < :to
          AND conversion_value IS NOT NULL
        ORDER BY conversion_value DESC
    """), {"from": dt_from, "to": dt_to}).fetchall()

    klaviyo_list = [
        {
            "id": r[0], "name": r[1],
            "send_time": r[2].isoformat() if r[2] else None,
            "recipients": int(r[3]), "revenue": float(r[4]), "rpr": float(r[5]),
        }
        for r in klav_rows
    ]
    klaviyo_total = sum(k["revenue"] for k in klaviyo_list)
    klaviyo_recipients = sum(k["recipients"] for k in klaviyo_list)

    # ── 5. Totals ──────────────────────────────────────────────────────────────
    email_total = campaigns_total + automations_total + klaviyo_total
    email_pct   = round(email_total / shopify_total * 100, 2) if shopify_total else 0

    total_recipients = campaigns_recipients + automations_recipients + klaviyo_recipients
    per_recipient = round(email_total / total_recipients, 0) if total_recipients else 0

    shopify_change = round((shopify_total - shopify_prev) / shopify_prev * 100, 1) if shopify_prev else None

    return {
        "date_from": dt_from.date().isoformat(),
        "date_to": (dt_to - timedelta(days=1)).date().isoformat(),
        "shopify_total": shopify_total,
        "shopify_orders": shopify_orders_count,
        "shopify_change_pct": shopify_change,
        "email_total": email_total,
        "email_pct": email_pct,
        "campaigns_total": campaigns_total,
        "automations_total": automations_total,
        "klaviyo_total": klaviyo_total,
        "total_recipients": total_recipients,
        "per_recipient": per_recipient,
        "campaigns": campaigns_list,
        "automations": automations_list,
        "klaviyo_campaigns": klaviyo_list,
    }


@router.get("/asuntos")
def asuntos(session: Session = Depends(get_session), _: User = Depends(get_current_user)):
    rows = session.exec(text("""
        SELECT id, subject, preview_text, campaign_name, campaign_id,
               open_rate, click_rate, recipients, opens_unique, send_time, notas
        FROM asuntos_email
        WHERE subject IS NOT NULL AND subject != ''
        ORDER BY open_rate DESC NULLS LAST
    """)).all()
    return [
        {
            "id": r[0], "subject": r[1], "preview_text": r[2],
            "campaign_name": r[3], "campaign_id": r[4],
            "open_rate": float(r[5]) if r[5] is not None else None,
            "click_rate": float(r[6]) if r[6] is not None else None,
            "recipients": r[7], "opens_unique": r[8],
            "send_time": r[9].isoformat() if r[9] else None,
            "notas": r[10],
        }
        for r in rows
    ]
