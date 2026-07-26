"""Emails transaccionales de producto (no-campaign), ej: set-password al instalar
la app. Envío vía app.services.email_provider (Resend o SES según la tienda)."""
import logging

from app.core.config import settings
from app.models.user import User
from app.services.email_provider import send_email

logger = logging.getLogger(__name__)


def send_set_password_email(user: User, token: str) -> None:
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
        send_email(
            shop_id=user.shop_id,
            from_email=settings.RESEND_FROM_EMAIL,
            to=[user.email],
            subject="Activa tu cuenta",
            html=html,
        )
    except Exception:
        logger.exception("No se pudo enviar el email de set-password a %s", user.email)
