import base64
import hashlib
import hmac
import json
import logging
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlmodel import Session
from app.database import get_session
from app.core.config import settings
from app.services.send_status_updater import apply_send_status_update

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


def _email_from_resend_payload(data: dict) -> str | None:
    to = data.get("to")
    if isinstance(to, list) and to:
        first = to[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            return first.get("email") or first.get("address")
    if isinstance(to, str):
        return to
    return data.get("email") or data.get("recipient")


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

    apply_send_status_update(
        session, resend_id, new_status, webhook_email=_email_from_resend_payload(data)
    )
    return {"ok": True}
