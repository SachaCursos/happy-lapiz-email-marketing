import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        if not settings.SHOPIFY_TOKEN_ENCRYPTION_KEY:
            raise RuntimeError(
                "SHOPIFY_TOKEN_ENCRYPTION_KEY no está configurada. "
                "Generar una con Fernet.generate_key() y setearla como env var."
            )
        _fernet = Fernet(settings.SHOPIFY_TOKEN_ENCRYPTION_KEY.encode())
    return _fernet


def encrypt_token(token: str) -> str:
    return _get_fernet().encrypt(token.encode()).decode()


def decrypt_token(token_encrypted: str) -> str:
    try:
        return _get_fernet().decrypt(token_encrypted.encode()).decode()
    except InvalidToken:
        raise ValueError("No se pudo desencriptar el token de Shopify")


def verify_oauth_hmac(query_params: dict) -> bool:
    """Verifica el HMAC de query string que Shopify envía en /install callback.

    Distinto del HMAC de webhooks: se calcula sobre los params ordenados y
    unidos con '&', no sobre el raw body.
    """
    params = dict(query_params)
    received_hmac = params.pop("hmac", None)
    if not received_hmac:
        return False

    message = "&".join(
        f"{key}={value}" for key, value in sorted(params.items())
    )
    digest = hmac.new(
        settings.SHOPIFY_API_SECRET.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(digest, received_hmac)
