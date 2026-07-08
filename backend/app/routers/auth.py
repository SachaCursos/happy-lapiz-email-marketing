from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlmodel import Session, select
from app.database import get_session
from app.core.security import verify_password, hash_password, create_access_token, decode_set_password_token
from app.core.deps import get_current_user
from app.models.user import User, UserCreate, UserRead

router = APIRouter()


class SetPasswordPayload(BaseModel):
    token: str
    password: str


@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    user = session.exec(select(User).where(User.email == form_data.username)).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
    token = create_access_token(user.email)
    return {"access_token": token, "token_type": "bearer"}


@router.post("/register", response_model=UserRead, status_code=201)
def register(payload: UserCreate, session: Session = Depends(get_session)):
    existing = session.exec(select(User).where(User.email == payload.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email ya registrado")
    user = User(
        email=payload.email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/set-password")
def set_password(payload: SetPasswordPayload, session: Session = Depends(get_session)):
    """Usado por merchants recién instalados (ver routers/shopify_oauth.py) para
    definir su contraseña a partir del link enviado por email. El token es de
    un solo propósito (purpose=set_password) y no sirve como token de login."""
    email = decode_set_password_token(payload.token)
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Link inválido o expirado")
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    if len(payload.password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La contraseña debe tener al menos 8 caracteres")
    user.password_hash = hash_password(payload.password)
    session.add(user)
    session.commit()
    return {"ok": True}
