"""Emails transaccionales de producto (no-campaign), ej: set-password al instalar
la app. Envío directo vía Resend, igual que el resto de call sites ad hoc del
repo (ver email_sender.py, contacts.py, templates.py, campaigns.py)."""
import logging

import resend

from app.core.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)


def send_set_password_email(user: User, token: str) -> None:
    resend.api_key = settings.RESEND_API_KEY
    set_password_url = f"{settings.FRONTEND_URL}/set-password?token={token}"
    html = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:480px;margin:0 auto;">
      <h2>¡Tu tienda ya está conectada!</h2>
      <p>Hola {user.name or user.email}, creamos tu cuenta para que puedas empezar a usar el dashboard de email marketing.</p>
      <p><a href="{set_password_url}" style="display:inline-block;background:#111827;color:#fff;padding:12px 20px;
         border-radius:8px;text-decoration:none;">Elegir mi contraseña</a></p>
      <p style="font-size:12px;color:#9ca3af;">Este link expira en 48 horas.</p>
    </div>
    """
    try:
        resend.Emails.send({
            "from": settings.RESEND_FROM_EMAIL,
            "to": [user.email],
            "subject": "Activa tu cuenta",
            "html": html,
        })
    except Exception:
        logger.exception("No se pudo enviar el email de set-password a %s", user.email)
