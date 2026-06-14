import csv
import io
import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy import create_engine, text
from sqlmodel import Session, select
import resend
from app.database import get_session
from app.core.config import settings
from app.core.deps import get_current_user, require_editor
from app.core.unsub_token import verify_unsub_token
from app.models.user import User
from app.models.contact import Contact, ContactCreate, ContactRead, ContactUpdate
from app.models.campaign import Campaign, CampaignSend
from app.models.automation import AutomationRun
from app.models.segment import Segment
from app.services.segment_evaluator import _build_clause

logger = logging.getLogger(__name__)

router = APIRouter()


_SORT_COLUMNS = {
    "name": Contact.name,
    "email": Contact.email,
    "orders_count": Contact.orders_count,
    "total_spent": Contact.total_spent,
    "last_purchase": Contact.last_purchase,
    "created_at": Contact.created_at,
    "accepts_marketing": Contact.accepts_marketing,
}


@router.get("/stats")
def contacts_stats(session: Session = Depends(get_session), _: User = Depends(get_current_user)):
    from sqlmodel import func
    total = session.exec(select(func.count(Contact.id))).one()
    active = session.exec(select(func.count(Contact.id)).where(Contact.accepts_marketing == True)).one()  # noqa
    unsubscribed = session.exec(select(func.count(Contact.id)).where(Contact.accepts_marketing == False)).one()  # noqa
    opted_in = session.exec(select(func.count(Contact.id)).where(Contact.opted_in == True)).one()  # noqa
    return {"total": total, "active": active, "unsubscribed": unsubscribed, "opted_in": opted_in}


@router.get("", response_model=List[ContactRead])
def list_contacts(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=200),
    search: Optional[str] = None,
    opted_in: Optional[bool] = None,
    sort_by: Optional[str] = Query(None),
    sort_dir: Optional[str] = Query("desc"),
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    query = select(Contact)
    if search:
        query = query.where(
            Contact.email.ilike(f"%{search}%") | Contact.name.ilike(f"%{search}%")
        )
    if opted_in is not None:
        query = query.where(Contact.opted_in == opted_in)
    col = _SORT_COLUMNS.get(sort_by or "created_at", Contact.created_at)
    query = query.order_by(col.desc() if sort_dir != "asc" else col.asc())
    query = query.offset(skip).limit(limit)
    return session.exec(query).all()


@router.get("/count")
def count_contacts(session: Session = Depends(get_session), _: User = Depends(get_current_user)):
    return {"count": session.exec(select(Contact)).all().__len__()}


def _do_unsubscribe(email: str, session: Session) -> None:
    contact = session.exec(select(Contact).where(Contact.email == email.lower())).first()
    if contact and contact.opted_in:
        contact.opted_in = False
        contact.opted_out_at = datetime.utcnow()
        session.add(contact)
        session.commit()
        _notify_unsubscribe(contact)


def _notify_unsubscribe(contact: Contact) -> None:
    if not settings.NOTIFY_EMAIL:
        return
    try:
        resend.api_key = settings.RESEND_API_KEY
        name = contact.name or contact.email
        resend.Emails.send({
            "from": settings.RESEND_FROM_EMAIL,
            "to": [settings.NOTIFY_EMAIL],
            "subject": f"Desuscripción: {name}",
            "html": (
                f"<p><strong>{name}</strong> ({contact.email}) "
                f"se ha dado de baja de la lista de Happy Lápiz.</p>"
                f"<p style='color:#999;font-size:13px;'>Puedes ver su perfil en "
                f"<a href='{settings.FRONTEND_URL}/contacts/{contact.id}'>el panel</a>.</p>"
            ),
        })
    except Exception as exc:
        logger.warning("No se pudo enviar notificación de desuscripción: %s", exc)


@router.get("/unsubscribe")
def unsubscribe_get(email: str = Query(...), token: str = Query(...), session: Session = Depends(get_session)):
    """Enlace de baja desde el cuerpo del email (click del usuario)."""
    if not verify_unsub_token(email, token):
        raise HTTPException(status_code=400, detail="Token inválido o expirado")
    _do_unsubscribe(email, session)
    return {"ok": True}


@router.post("/unsubscribe")
def unsubscribe_one_click(email: str = Query(...), token: str = Query(...), session: Session = Depends(get_session)):
    """One-click unsubscribe para clientes de email (Gmail List-Unsubscribe-Post)."""
    if not verify_unsub_token(email, token):
        raise HTTPException(status_code=400, detail="Token inválido o expirado")
    _do_unsubscribe(email, session)
    return {"ok": True}


@router.post("", response_model=ContactRead, status_code=201)
def create_contact(
    payload: ContactCreate,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
):
    existing = session.exec(select(Contact).where(Contact.email == payload.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email ya existe")
    contact = Contact(**payload.model_dump(), opted_in_at=datetime.utcnow() if payload.opted_in else None)
    session.add(contact)
    session.commit()
    session.refresh(contact)
    return contact


@router.get("/{contact_id}", response_model=ContactRead)
def get_contact(contact_id: int, session: Session = Depends(get_session), _: User = Depends(get_current_user)):
    contact = session.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")
    return contact


@router.patch("/{contact_id}", response_model=ContactRead)
def update_contact(
    contact_id: int,
    payload: ContactUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
):
    contact = session.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")
    data = payload.model_dump(exclude_unset=True)
    if "opted_in" in data:
        if data["opted_in"] and not contact.opted_in:
            contact.opted_in_at = datetime.utcnow()
            contact.opted_out_at = None
        elif not data["opted_in"] and contact.opted_in:
            contact.opted_out_at = datetime.utcnow()
    for k, v in data.items():
        setattr(contact, k, v)
    contact.updated_at = datetime.utcnow()
    session.add(contact)
    session.commit()
    session.refresh(contact)
    return contact


@router.delete("/{contact_id}", status_code=204)
def delete_contact(
    contact_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
):
    contact = session.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")
    # Delete FK-referencing rows first to avoid constraint violations
    for row in session.exec(select(CampaignSend).where(CampaignSend.contact_id == contact_id)).all():
        session.delete(row)
    for row in session.exec(select(AutomationRun).where(AutomationRun.contact_id == contact_id)).all():
        session.delete(row)
    session.delete(contact)
    session.commit()


@router.get("/{contact_id}/segments")
def contact_segments(
    contact_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """Devuelve los segmentos a los que pertenece el contacto."""
    contact = session.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")

    all_segs = session.exec(select(Segment)).all()
    matching = []
    for seg in all_segs:
        q = select(Contact).where(Contact.id == contact_id, Contact.opted_in == True)  # noqa: E712
        if seg.conditions:
            clause = _build_clause(seg.conditions)
            if clause is not None:
                q = q.where(clause)
        if session.exec(q).first():
            matching.append({"id": seg.id, "name": seg.name, "description": seg.description})
    return matching


@router.get("/{contact_id}/bookings")
def contact_bookings(
    contact_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """Historial de compras del contacto."""
    contact = session.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")

    src_url = settings.HOTBOAT_DATABASE_URL or settings.DATABASE_URL
    try:
        engine = create_engine(src_url)
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT
                    fecha,
                    status,
                    ingreso_total,
                    como_supieron,
                    extras_json
                FROM all_appointments
                WHERE email = :email
                ORDER BY fecha DESC
                LIMIT 50
            """), {"email": contact.email}).fetchall()
        return [
            {
                "fecha": str(r.fecha),
                "status": r.status,
                "ingreso_total": float(r.ingreso_total) if r.ingreso_total else None,
                "como_supieron": r.como_supieron,
                "extras": r.extras_json if r.extras_json else {},
            }
            for r in rows
        ]
    except Exception as exc:
        # Source DB not available — return empty without crashing
        return []


@router.get("/{contact_id}/email_activity")
def contact_email_activity(
    contact_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """Feed de eventos de email para el contacto (enviados, abiertos, clics)."""
    contact = session.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")

    sends = session.exec(
        select(CampaignSend)
        .where(CampaignSend.contact_id == contact_id)
        .order_by(CampaignSend.sent_at.desc())
    ).all()
    if not sends:
        return []

    campaign_ids = list({s.campaign_id for s in sends})
    camps = {c.id: c for c in session.exec(select(Campaign).where(Campaign.id.in_(campaign_ids))).all()}

    events = []
    for s in sends:
        camp = camps.get(s.campaign_id)
        base = {
            "campaign_id": s.campaign_id,
            "campaign_name": camp.name if camp else f"Campaña #{s.campaign_id}",
        }
        if s.clicked_at:
            events.append({**base, "type": "clicked",   "timestamp": s.clicked_at.isoformat()})
        if s.opened_at:
            events.append({**base, "type": "opened",    "timestamp": s.opened_at.isoformat()})
        if s.delivered_at:
            events.append({**base, "type": "delivered", "timestamp": s.delivered_at.isoformat()})
        if s.bounced_at:
            events.append({**base, "type": "bounced",   "timestamp": s.bounced_at.isoformat()})
        if s.sent_at:
            events.append({**base, "type": "sent",      "timestamp": s.sent_at.isoformat()})

    events.sort(key=lambda x: x["timestamp"], reverse=True)
    return events[:60]


@router.get("/{contact_id}/email_sends")
def contact_email_sends(
    contact_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """Resumen por campaña: qué le enviamos, si abrió, si hizo clic."""
    contact = session.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")

    sends = session.exec(
        select(CampaignSend)
        .where(CampaignSend.contact_id == contact_id)
        .order_by(CampaignSend.sent_at.desc())
    ).all()
    if not sends:
        return []

    campaign_ids = list({s.campaign_id for s in sends})
    camps = {c.id: c for c in session.exec(select(Campaign).where(Campaign.id.in_(campaign_ids))).all()}

    return [
        {
            "campaign_id":   s.campaign_id,
            "campaign_name": camps[s.campaign_id].name if s.campaign_id in camps else f"Campaña #{s.campaign_id}",
            "status":        s.status,
            "sent_at":       s.sent_at.isoformat()       if s.sent_at       else None,
            "delivered_at":  s.delivered_at.isoformat()  if s.delivered_at  else None,
            "opened_at":     s.opened_at.isoformat()     if s.opened_at     else None,
            "clicked_at":    s.clicked_at.isoformat()    if s.clicked_at    else None,
            "bounced_at":    s.bounced_at.isoformat()    if s.bounced_at    else None,
        }
        for s in sends
    ]


@router.post("/import/csv", status_code=201)
def import_csv(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
):
    """Importa contactos desde CSV. Columnas requeridas: email. Opcionales: name, phone, origin_utm."""
    content = file.file.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))
    created = 0
    skipped = 0
    for row in reader:
        email = row.get("email", "").strip().lower()
        if not email:
            skipped += 1
            continue
        existing = session.exec(select(Contact).where(Contact.email == email)).first()
        if existing:
            skipped += 1
            continue
        contact = Contact(
            email=email,
            name=row.get("name", "").strip() or None,
            phone=row.get("phone", "").strip() or None,
            origin_utm=row.get("origin_utm", "").strip() or None,
            opted_in=True,
            opted_in_at=datetime.utcnow(),
        )
        session.add(contact)
        created += 1
    session.commit()
    return {"created": created, "skipped": skipped}
