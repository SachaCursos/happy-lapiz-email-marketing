from fastapi import APIRouter, Depends
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
