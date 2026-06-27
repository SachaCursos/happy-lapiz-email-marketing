import base64
import hashlib
import hmac
import json
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlmodel import Session, select
from app.database import get_session
from app.core.config import settings
from app.models.campaign import CampaignSend
from app.models.automation import AutomationRun

logger = logging.getLogger(__name__)
router = APIRouter()

STATUS_MAP = {
    "email.sent":       "sent",
    "email.delivered":  "delivered",
    "email.opened":     "opened",
    "email.clicked":    "clicked",
    "email.bounced":    "bounced",
    "email.complained": "complained",
}


def _verify_svix(payload: bytes, svix_id: str, svix_timestamp: str, svix_signature: str) -> bool:
    """Verifica la firma Svix que usa Resend para sus webhooks."""
    secret = settings.RESEND_WEBHOOK_SECRET
    if not secret:
        return True

    # El secret de Resend/Svix empieza con "whsec_" — hay que decodificar el resto en base64
    if secret.startswith("whsec_"):
        secret = secret[6:]
    try:
        secret_bytes = base64.b64decode(secret)
    except Exception:
        return False

    # Contenido firmado: "{svix-id}.{svix-timestamp}.{body}"
    signed = f"{svix_id}.{svix_timestamp}.".encode() + payload

    expected = base64.b64encode(
        hmac.new(secret_bytes, signed, hashlib.sha256).digest()
    ).decode()

    # svix-signature puede contener varias firmas separadas por espacio: "v1,abc123 v1,xyz..."
    for sig in svix_signature.split(" "):
        if sig.startswith("v1,"):
            if hmac.compare_digest(expected, sig[3:]):
                return True
    return False


@router.post("/resend")
async def resend_webhook(
    request: Request,
    svix_id: str = Header(default="", alias="svix-id"),
    svix_timestamp: str = Header(default="", alias="svix-timestamp"),
    svix_signature: str = Header(default="", alias="svix-signature"),
    session: Session = Depends(get_session),
):
    body = await request.body()

    if not _verify_svix(body, svix_id, svix_timestamp, svix_signature):
        logger.warning("Webhook con firma Svix inválida — rechazado")
        raise HTTPException(status_code=401, detail="Firma inválida")

    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="JSON inválido")

    event_type = event.get("type", "")
    data = event.get("data", {})
    resend_id = data.get("email_id") or data.get("id")

    logger.info("Webhook recibido: type=%s resend_id=%s", event_type, resend_id)

    new_status = STATUS_MAP.get(event_type)
    if not new_status or not resend_id:
        return {"ok": True}

    now = datetime.utcnow()

    # Try campaign send first
    send = session.exec(select(CampaignSend).where(CampaignSend.resend_id == resend_id)).first()
    if send:
        send.status = new_status
        if new_status == "delivered":
            send.delivered_at = now
        elif new_status == "opened" and not send.opened_at:
            send.opened_at = now
        elif new_status == "clicked" and not send.clicked_at:
            send.clicked_at = now
        elif new_status == "bounced":
            send.bounced_at = now
        session.add(send)
        session.commit()
        logger.info("CampaignSend actualizado: id=%s status=%s", send.id, new_status)
        return {"ok": True}

    # Try automation run
    run = session.exec(select(AutomationRun).where(AutomationRun.resend_id == resend_id)).first()
    if run:
        if new_status == "opened" and not run.opened_at:
            run.opened_at = now
        elif new_status == "clicked" and not run.clicked_at:
            run.clicked_at = now
        session.add(run)
        session.commit()
        logger.info("AutomationRun actualizado: id=%s status=%s", run.id, new_status)
        return {"ok": True}

    from app.models.evergreen import EvergreenSend
    eg_send = session.exec(select(EvergreenSend).where(EvergreenSend.resend_id == resend_id)).first()
    if eg_send:
        eg_send.status = new_status
        if new_status == "delivered":
            eg_send.delivered_at = now
        elif new_status == "opened" and not eg_send.opened_at:
            eg_send.opened_at = now
        elif new_status == "clicked" and not eg_send.clicked_at:
            eg_send.clicked_at = now
        elif new_status == "bounced":
            eg_send.bounced_at = now
        session.add(eg_send)
        session.commit()
        logger.info("EvergreenSend actualizado: id=%s status=%s", eg_send.id, new_status)
        return {"ok": True}

    logger.warning("Email no encontrado para resend_id=%s", resend_id)
    return {"ok": True}
