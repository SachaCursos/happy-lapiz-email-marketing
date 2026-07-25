from datetime import datetime, timedelta
from typing import Optional
import bcrypt
from jose import JWTError, jwt
from app.core.config import settings


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return jwt.encode(
        {"sub": subject, "exp": expire},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


def create_set_password_token(user_email: str, expires_delta: Optional[timedelta] = None) -> str:
    """Token de un solo propósito para que un merchant recién instalado defina
    su contraseña. Lleva un claim `purpose` para que no pueda reusarse como
    token de login (decode_token no lo verifica)."""
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=48))
    return jwt.encode(
        {"sub": user_email, "purpose": "set_password", "exp": expire},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_set_password_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("purpose") != "set_password":
            return None
        return payload.get("sub")
    except JWTError:
        return None


def create_oauth_state_token(shop_domain: str) -> str:
    """CSRF state para el flujo /install → /callback. Corta duración: el
    merchant completa el consentimiento de Shopify en segundos/minutos."""
    expire = datetime.utcnow() + timedelta(minutes=10)
    return jwt.encode(
        {"sub": shop_domain, "purpose": "oauth_state", "exp": expire},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_oauth_state_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("purpose") != "oauth_state":
            return None
        return payload.get("sub")
    except JWTError:
        return None
