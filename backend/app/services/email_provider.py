"""Único punto de entrada para mandar cualquier email, sea cual sea el proveedor
(Resend hoy, AWS SES de forma gradual y opt-in por tienda vía Shop.email_provider).

Todos los call sites de envío (campañas, automatizaciones, evergreen,
transaccionales, test-sends) deben pasar por send_email() acá — así
EMAIL_OVERRIDE_TO se aplica en un solo lugar y ningún call site nuevo puede
olvidarlo (ver email_typo_fix / el incidente de envíos duplicados)."""
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

import resend

from app.core.config import settings

logger = logging.getLogger(__name__)


def apply_email_override(to: List[str], subject: str) -> tuple[List[str], str]:
    """When EMAIL_OVERRIDE_TO is set (staging), redirect every outgoing email
    to that single inbox instead of the real recipient(s), tagging the
    original recipient(s) into the subject so test sends stay traceable."""
    if not settings.EMAIL_OVERRIDE_TO:
        return to, subject
    return [settings.EMAIL_OVERRIDE_TO], f"[{', '.join(to)}] {subject}"


def resolve_provider(shop_id: Optional[int]) -> str:
    """Shop.email_provider (si está seteado) manda sobre el default global
    settings.EMAIL_PROVIDER. Sin shop_id, o sin el flag seteado, usa el default
    global — hoy "resend" para toda tienda que no se haya migrado explícitamente."""
    if shop_id:
        try:
            from sqlmodel import Session
            from app.database import engine
            from app.models.shop import Shop

            with Session(engine) as session:
                shop = session.get(Shop, shop_id)
                if shop and shop.email_provider:
                    return shop.email_provider
        except Exception:
            logger.exception(
                "resolve_provider: no se pudo leer Shop.email_provider para shop_id=%s", shop_id
            )
    return settings.EMAIL_PROVIDER or "resend"


def _send_via_resend(
    from_email: str, to: List[str], subject: str, html: str,
    headers: Optional[dict], tags: Optional[List[dict]],
) -> str:
    resend.api_key = settings.RESEND_API_KEY
    payload = {"from": from_email, "to": to, "subject": subject, "html": html}
    if headers:
        payload["headers"] = headers
    if tags:
        payload["tags"] = tags
    response = resend.Emails.send(payload)
    return response.get("id") if isinstance(response, dict) else getattr(response, "id", None)


def _send_via_ses(
    from_email: str, to: List[str], subject: str, html: str,
    headers: Optional[dict], tags: Optional[List[dict]],
) -> str:
    import boto3

    client = boto3.client(
        "sesv2",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
    )

    # SESv2's simple send_email() doesn't support custom headers (List-Unsubscribe,
    # etc.) — hay que armar el MIME crudo, igual que exige la API "Raw" de SES.
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = ", ".join(to)
    for key, value in (headers or {}).items():
        msg[key] = value
    msg.attach(MIMEText(html, "html", "utf-8"))

    kwargs = {
        "Destination": {"ToAddresses": to},
        "Content": {"Raw": {"Data": msg.as_bytes()}},
    }
    if tags:
        ses_tags = [
            {"Name": t["name"], "Value": t["value"]}
            for t in tags if t.get("name") and t.get("value")
        ]
        if ses_tags:
            kwargs["EmailTags"] = ses_tags

    response = client.send_email(**kwargs)
    return response.get("MessageId")


def send_email(
    *,
    shop_id: Optional[int] = None,
    from_email: str,
    to: List[str],
    subject: str,
    html: str,
    headers: Optional[dict] = None,
    tags: Optional[List[dict]] = None,
) -> tuple[str, str]:
    """Manda un email por el proveedor que corresponda a esa tienda. Devuelve
    (provider, message_id) — el caller guarda ambos junto al registro de envío
    (CampaignSend/AutomationRun/EvergreenSend)."""
    to, subject = apply_email_override(to, subject)
    provider = resolve_provider(shop_id)
    if provider == "ses":
        # Call sites hardcode RESEND_FROM_EMAIL — si el remitente verificado en SES
        # es otro, SES_FROM_EMAIL lo pisa acá, en el único lugar que lo necesita.
        ses_from = settings.SES_FROM_EMAIL or from_email
        message_id = _send_via_ses(ses_from, to, subject, html, headers, tags)
        return "ses", message_id
    message_id = _send_via_resend(from_email, to, subject, html, headers, tags)
    return "resend", message_id
