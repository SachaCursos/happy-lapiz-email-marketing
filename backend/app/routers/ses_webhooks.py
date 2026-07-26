"""Eventos SES (Send/Delivery/Bounce/Complaint/Open/Click) entregados vía SNS.

SES no tiene un webhook simple como el Svix de Resend (ver app/routers/webhooks.py)
— publica a un SNS Topic, y SNS empuja notificaciones HTTPS a quien esté
suscripto. Ver Fase 0/2 del plan de migración a AWS SES para el setup del topic
y el Configuration Set."""
import base64
import json
import logging
import re
from typing import Optional

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session

from app.database import get_session
from app.services.send_status_updater import apply_send_status_update

logger = logging.getLogger(__name__)
router = APIRouter()

# Solo se confía en certificados servidos desde un host real de SNS — evita que un
# payload arbitrario apunte SigningCertURL a un servidor propio (spoofing/SSRF).
_SNS_CERT_HOST_RE = re.compile(r"^sns\.[a-zA-Z0-9-]+\.amazonaws\.com$")

_cert_cache: dict[str, bytes] = {}

SES_EVENT_STATUS_MAP = {
    "Send": "sent",
    "Delivery": "delivered",
    "Open": "opened",
    "Click": "clicked",
    "Bounce": "bounced",
    "Complaint": "complained",
}


def _fetch_cert(url: str) -> bytes:
    if url in _cert_cache:
        return _cert_cache[url]
    resp = httpx.get(url, timeout=10.0)
    resp.raise_for_status()
    _cert_cache[url] = resp.content
    return resp.content


def _verify_sns_signature(msg: dict) -> bool:
    cert_url = msg.get("SigningCertURL", "")
    try:
        host = httpx.URL(cert_url).host
    except Exception:
        host = None
    if not host or not _SNS_CERT_HOST_RE.match(host):
        logger.warning("SNS SigningCertURL con host no confiable: %s", cert_url)
        return False

    msg_type = msg.get("Type", "")
    if msg_type in ("SubscriptionConfirmation", "UnsubscribeConfirmation"):
        fields = ["Message", "MessageId", "SubscribeURL", "Timestamp", "Token", "TopicArn", "Type"]
    else:
        fields = ["Message", "MessageId", "Subject", "Timestamp", "TopicArn", "Type"]

    parts = []
    for f in fields:
        if f == "Subject" and "Subject" not in msg:
            continue
        if f not in msg:
            return False
        parts.append(f)
        parts.append(str(msg[f]))
    string_to_sign = ("\n".join(parts) + "\n").encode("utf-8")

    try:
        cert_bytes = _fetch_cert(cert_url)
        cert = x509.load_pem_x509_certificate(cert_bytes)
        signature = base64.b64decode(msg.get("Signature", ""))
        digest = hashes.SHA256() if msg.get("SignatureVersion") == "2" else hashes.SHA1()
        cert.public_key().verify(signature, string_to_sign, padding.PKCS1v15(), digest)
        return True
    except Exception:
        logger.exception("Firma SNS inválida")
        return False


def _extract_email(event: dict, event_type: Optional[str]) -> Optional[str]:
    if event_type == "Bounce":
        recipients = (event.get("bounce") or {}).get("bouncedRecipients") or []
        if recipients:
            return recipients[0].get("emailAddress")
    elif event_type == "Complaint":
        recipients = (event.get("complaint") or {}).get("complainedRecipients") or []
        if recipients:
            return recipients[0].get("emailAddress")
    destinations = (event.get("mail") or {}).get("destination") or []
    return destinations[0] if destinations else None


@router.post("/ses")
async def ses_webhook(request: Request, session: Session = Depends(get_session)):
    try:
        msg = json.loads(await request.body())
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="JSON inválido")

    if not _verify_sns_signature(msg):
        raise HTTPException(status_code=401, detail="Firma SNS inválida")

    msg_type = msg.get("Type", "")

    if msg_type == "SubscriptionConfirmation":
        # A propósito no confirmamos automáticamente (evita un code path que
        # visite URLs externas por HTTP) — se confirma una sola vez a mano al
        # armar el SNS topic, pegando el SubscribeURL logueado acá.
        logger.warning(
            "SNS SubscriptionConfirmation pendiente de confirmar manualmente: %s",
            msg.get("SubscribeURL"),
        )
        return {"ok": True}

    if msg_type != "Notification":
        return {"ok": True}

    try:
        event = json.loads(msg.get("Message", "{}"))
    except json.JSONDecodeError:
        logger.warning("SES event: Message no es JSON válido")
        return {"ok": True}

    event_type = event.get("eventType") or event.get("notificationType")
    new_status = SES_EVENT_STATUS_MAP.get(event_type)
    message_id = (event.get("mail") or {}).get("messageId")

    logger.info("SES webhook: eventType=%s messageId=%s", event_type, message_id)

    if not new_status or not message_id:
        return {"ok": True}

    apply_send_status_update(
        session, message_id, new_status, webhook_email=_extract_email(event, event_type)
    )
    return {"ok": True}
