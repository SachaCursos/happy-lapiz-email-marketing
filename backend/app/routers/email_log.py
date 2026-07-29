"""Visor de correos enviados: lista unificada de campaign_sends + automation_runs +
evergreen_sends, con filtros y detalle (asunto/HTML tal como se mandó)."""
from datetime import datetime, timedelta
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session

from app.database import get_session
from app.core.deps import get_current_user, get_current_shop
from app.models.user import User
from app.models.shop import Shop

router = APIRouter()

Source = Literal["campaign", "automation", "evergreen"]

_SOURCE_QUERIES = {
    "campaign": """
        SELECT cs.id, 'campaign' AS source, cs.campaign_id AS source_id,
               c.name AS source_name, cs.contact_id, ct.email AS contact_email,
               cs.subject, cs.status, cs.send_provider,
               COALESCE(cs.sent_at, cs.delivered_at) AS sent_at,
               (cs.html_snapshot IS NOT NULL) AS has_snapshot
        FROM campaign_sends cs
        JOIN campaigns c ON c.id = cs.campaign_id
        JOIN contacts ct ON ct.id = cs.contact_id
        WHERE cs.shop_id = :shop_id
    """,
    "automation": """
        SELECT ar.id, 'automation' AS source, ar.automation_id AS source_id,
               a.name AS source_name, ar.contact_id, ar.contact_email,
               ar.subject, ar.status, ar.send_provider,
               COALESCE(ar.executed_at, ar.triggered_at) AS sent_at,
               (ar.html_snapshot IS NOT NULL) AS has_snapshot
        FROM automation_runs ar
        JOIN automations a ON a.id = ar.automation_id
        WHERE ar.shop_id = :shop_id
    """,
    "evergreen": """
        SELECT es.id, 'evergreen' AS source, es.evergreen_id AS source_id,
               eg.name AS source_name, es.contact_id, ct.email AS contact_email,
               es.subject, es.status, es.send_provider,
               COALESCE(es.sent_at, es.delivered_at) AS sent_at,
               (es.html_snapshot IS NOT NULL) AS has_snapshot
        FROM evergreen_sends es
        JOIN evergreen_campaigns eg ON eg.id = es.evergreen_id
        JOIN contacts ct ON ct.id = es.contact_id
        WHERE ct.shop_id = :shop_id
    """,
}

_DETAIL_QUERIES = {
    "campaign": """
        SELECT cs.campaign_id AS source_id, cs.subject, cs.html_snapshot,
               ct.email AS contact_email, cs.status, cs.send_provider, cs.sent_at,
               cs.delivered_at, cs.opened_at, cs.clicked_at, cs.bounced_at,
               c.name AS source_name
        FROM campaign_sends cs
        JOIN campaigns c ON c.id = cs.campaign_id
        JOIN contacts ct ON ct.id = cs.contact_id
        WHERE cs.id = :id AND cs.shop_id = :shop_id
    """,
    "automation": """
        SELECT ar.automation_id AS source_id, ar.subject, ar.html_snapshot,
               ar.contact_email, ar.status, ar.send_provider,
               ar.executed_at AS sent_at, NULL AS delivered_at,
               ar.opened_at, ar.clicked_at, NULL AS bounced_at, a.name AS source_name
        FROM automation_runs ar
        JOIN automations a ON a.id = ar.automation_id
        WHERE ar.id = :id AND ar.shop_id = :shop_id
    """,
    "evergreen": """
        SELECT es.evergreen_id AS source_id, es.subject, es.html_snapshot,
               ct.email AS contact_email, es.status, es.send_provider, es.sent_at,
               es.delivered_at, es.opened_at, es.clicked_at, es.bounced_at,
               eg.name AS source_name
        FROM evergreen_sends es
        JOIN evergreen_campaigns eg ON eg.id = es.evergreen_id
        JOIN contacts ct ON ct.id = es.contact_id
        WHERE es.id = :id AND ct.shop_id = :shop_id
    """,
}


class EmailLogEntry(BaseModel):
    id: int
    source: Source
    source_id: int
    source_name: str
    contact_id: Optional[int] = None
    contact_email: str
    subject: Optional[str] = None
    status: str
    send_provider: Optional[str] = None
    sent_at: Optional[datetime] = None
    has_snapshot: bool


class EmailLogList(BaseModel):
    total: int
    items: List[EmailLogEntry]


class EmailLogDetail(BaseModel):
    source: Source
    source_id: int
    source_name: str
    contact_email: str
    subject: Optional[str] = None
    html: Optional[str] = None
    status: str
    send_provider: Optional[str] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    clicked_at: Optional[datetime] = None
    bounced_at: Optional[datetime] = None
    has_snapshot: bool


@router.get("", response_model=EmailLogList)
def list_email_log(
    email: Optional[str] = Query(default=None),
    subject: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    source: Optional[Source] = Query(default=None),
    date_from: Optional[str] = Query(default=None, description="YYYY-MM-DD inclusive"),
    date_to: Optional[str] = Query(default=None, description="YYYY-MM-DD inclusive"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
    shop: Shop = Depends(get_current_shop),
):
    sources = [source] if source else list(_SOURCE_QUERIES.keys())
    union_sql = " UNION ALL ".join(_SOURCE_QUERIES[s] for s in sources)

    params: dict = {"shop_id": shop.id}
    filters = ""
    if email:
        filters += " AND u.contact_email ILIKE :email"
        params["email"] = f"%{email}%"
    if subject:
        filters += " AND u.subject ILIKE :subject"
        params["subject"] = f"%{subject}%"
    if status:
        filters += " AND u.status = :status"
        params["status"] = status
    if date_from:
        params["date_from"] = datetime.strptime(date_from, "%Y-%m-%d")
        filters += " AND u.sent_at >= :date_from"
    if date_to:
        params["date_to"] = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
        filters += " AND u.sent_at < :date_to"

    count_row = session.execute(
        text(f"SELECT COUNT(*) FROM ({union_sql}) u WHERE 1=1{filters}"), params
    ).fetchone()
    total = int(count_row[0] or 0)

    params["limit"] = page_size
    params["offset"] = (page - 1) * page_size
    rows = session.execute(
        text(
            f"SELECT * FROM ({union_sql}) u WHERE 1=1{filters} "
            "ORDER BY u.sent_at DESC NULLS LAST LIMIT :limit OFFSET :offset"
        ),
        params,
    ).fetchall()

    items = [
        EmailLogEntry(
            id=row.id,
            source=row.source,
            source_id=row.source_id,
            source_name=row.source_name,
            contact_id=row.contact_id,
            contact_email=row.contact_email,
            subject=row.subject,
            status=row.status,
            send_provider=row.send_provider,
            sent_at=row.sent_at,
            has_snapshot=row.has_snapshot,
        )
        for row in rows
    ]
    return EmailLogList(total=total, items=items)


@router.get("/{source}/{entry_id}", response_model=EmailLogDetail)
def get_email_log_detail(
    source: Source,
    entry_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
    shop: Shop = Depends(get_current_shop),
):
    if source not in _DETAIL_QUERIES:
        raise HTTPException(status_code=404, detail="Origen inválido")

    row = session.execute(
        text(_DETAIL_QUERIES[source]), {"id": entry_id, "shop_id": shop.id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Envío no encontrado")

    return EmailLogDetail(
        source=source,
        source_id=row.source_id,
        source_name=row.source_name,
        contact_email=row.contact_email,
        subject=row.subject,
        html=row.html_snapshot,
        status=row.status,
        send_provider=row.send_provider,
        sent_at=row.sent_at,
        delivered_at=row.delivered_at,
        opened_at=row.opened_at,
        clicked_at=row.clicked_at,
        bounced_at=row.bounced_at,
        has_snapshot=row.html_snapshot is not None,
    )
