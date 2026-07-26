"""Aplica un cambio de estado de entrega (sent/delivered/opened/clicked/bounced/
complained) a la fila de envío que corresponda, sin importar qué proveedor lo
generó — Resend (app/routers/webhooks.py) y SES (app/routers/ses_webhooks.py)
comparten esta lógica porque ambos terminan escribiendo sobre las mismas tres
tablas (CampaignSend/AutomationRun/EvergreenSend) buscando por el id de mensaje
guardado en la columna `resend_id`."""
import logging
from datetime import datetime

from sqlmodel import Session, select

from app.models.campaign import CampaignSend
from app.models.automation import AutomationRun

logger = logging.getLogger(__name__)


def _maybe_fix_typo_on_bounce(session: Session, new_status: str, bounced_email: str | None) -> None:
    if new_status != "bounced" or not bounced_email:
        return
    try:
        from app.services.email_typo_fix import apply_bounce_typo_fix

        result = apply_bounce_typo_fix(session, bounced_email)
        if result:
            logger.info(
                "Bounce typo auto-fix: %s → %s (%s)",
                result["from"], result["to"], result["action"],
            )
    except Exception:
        logger.exception("Error auto-corrigiendo typo tras bounce: %s", bounced_email)


def apply_send_status_update(
    session: Session,
    message_id: str,
    new_status: str,
    *,
    webhook_email: str | None = None,
) -> bool:
    """Busca message_id en CampaignSend/AutomationRun/EvergreenSend (en ese orden)
    y actualiza su estado + timestamps + dispara el auto-fix de typos en bounce.
    Devuelve True si encontró y actualizó alguna fila."""
    now = datetime.utcnow()

    send = session.exec(select(CampaignSend).where(CampaignSend.resend_id == message_id)).first()
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
        if new_status == "bounced":
            from app.models.contact import Contact

            contact = session.get(Contact, send.contact_id)
            _maybe_fix_typo_on_bounce(
                session, new_status, webhook_email or (contact.email if contact else None)
            )
        return True

    run = session.exec(select(AutomationRun).where(AutomationRun.resend_id == message_id)).first()
    if run:
        if new_status == "opened" and not run.opened_at:
            run.opened_at = now
        elif new_status == "clicked" and not run.clicked_at:
            run.clicked_at = now
        elif new_status == "bounced":
            run.status = "bounced"
        session.add(run)
        session.commit()
        logger.info("AutomationRun actualizado: id=%s status=%s", run.id, new_status)
        if new_status == "bounced":
            _maybe_fix_typo_on_bounce(session, new_status, webhook_email or run.contact_email)
        return True

    from app.models.evergreen import EvergreenSend

    eg_send = session.exec(select(EvergreenSend).where(EvergreenSend.resend_id == message_id)).first()
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
        if new_status == "bounced":
            from app.models.contact import Contact

            contact = session.get(Contact, eg_send.contact_id)
            _maybe_fix_typo_on_bounce(
                session, new_status, webhook_email or (contact.email if contact else None)
            )
        return True

    if new_status == "bounced":
        _maybe_fix_typo_on_bounce(session, new_status, webhook_email)

    logger.warning("Email no encontrado para message_id=%s", message_id)
    return False
