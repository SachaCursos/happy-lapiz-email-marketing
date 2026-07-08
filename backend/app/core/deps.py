from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select
from app.database import get_session
from app.core.security import decode_token
from app.models.user import User
from app.models.shop import Shop

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    email = decode_token(token)
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado")
    return user


def get_current_shop(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Shop:
    if not current_user.shop_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario no vinculado a ninguna tienda")
    shop = session.get(Shop, current_user.shop_id)
    if not shop or shop.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tienda no encontrada o desinstalada")
    return shop


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Se requiere rol admin")
    return current_user


def require_editor(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role == "viewer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Se requiere rol editor o admin")
    return current_user
