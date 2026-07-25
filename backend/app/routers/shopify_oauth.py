"""Flujo de instalación OAuth para la app multi-tenant de Shopify.

GET /install   → redirige al merchant a la pantalla de consentimiento de Shopify
GET /callback  → intercambia el code por un access token, crea/actualiza el Shop,
                 registra webhooks, dispara el sync inicial y deja al merchant
                 con credenciales para entrar al dashboard existente.
"""
import logging
import re
import secrets
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.core.config import settings
from app.core.crypto import encrypt_token, verify_oauth_hmac
from app.core.security import create_oauth_state_token, decode_oauth_state_token, create_set_password_token, hash_password
from app.database import get_session
from app.models.shop import Shop
from app.models.user import User
from app.services.shopify_client import register_webhooks_for_shop
from app.services.shopify_initial_sync import run_initial_sync
from app.services.transactional_email import send_set_password_email

logger = logging.getLogger(__name__)
router = APIRouter()

SHOP_DOMAIN_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-]*\.myshopify\.com$")


def _validate_shop_domain(shop: str) -> str:
    if not shop or not SHOP_DOMAIN_RE.match(shop):
        raise HTTPException(status_code=400, detail="Parámetro shop inválido")
    return shop


@router.get("/install")
def install(shop: str):
    shop = _validate_shop_domain(shop)
    state = create_oauth_state_token(shop)
    redirect_uri = f"{settings.BACKEND_PUBLIC_URL}/api/shopify/callback"
    authorize_url = (
        f"https://{shop}/admin/oauth/authorize"
        f"?client_id={settings.SHOPIFY_API_KEY}"
        f"&scope={settings.SHOPIFY_SCOPES}"
        f"&redirect_uri={redirect_uri}"
        f"&state={state}"
    )
    return RedirectResponse(authorize_url)


@router.get("/callback")
async def callback(
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    params = dict(request.query_params)
    shop_domain = _validate_shop_domain(params.get("shop", ""))
    code = params.get("code")
    state = params.get("state")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Faltan parámetros code/state")

    if decode_oauth_state_token(state) != shop_domain:
        raise HTTPException(status_code=401, detail="state inválido o expirado")

    if not verify_oauth_hmac(params):
        raise HTTPException(status_code=401, detail="HMAC inválido")

    # ── Intercambiar el code por un access token permanente ──────────────────
    async with httpx.AsyncClient(timeout=15.0) as client:
        token_resp = await client.post(
            f"https://{shop_domain}/admin/oauth/access_token",
            json={
                "client_id": settings.SHOPIFY_API_KEY,
                "client_secret": settings.SHOPIFY_API_SECRET,
                "code": code,
            },
        )
    if token_resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Shopify token exchange falló: {token_resp.text[:200]}")

    token_data = token_resp.json()
    access_token = token_data.get("access_token")
    granted_scopes = token_data.get("scope", "")
    if not access_token:
        raise HTTPException(status_code=502, detail="Shopify no devolvió access_token")

    # ── Datos de la tienda (owner email, plan, currency) ──────────────────────
    shop_info = {}
    async with httpx.AsyncClient(timeout=15.0) as client:
        info_resp = await client.get(
            f"https://{shop_domain}/admin/api/2024-10/shop.json",
            headers={"X-Shopify-Access-Token": access_token},
        )
    if info_resp.status_code == 200:
        shop_info = info_resp.json().get("shop", {})

    now = datetime.now(timezone.utc)
    shop = session.exec(select(Shop).where(Shop.shopify_domain == shop_domain)).first()
    is_new_shop = shop is None
    if not shop:
        shop = Shop(shopify_domain=shop_domain, installed_at=now)

    shop.access_token_encrypted = encrypt_token(access_token)
    shop.scopes = granted_scopes
    shop.status = "active"
    shop.uninstalled_at = None
    shop.shopify_shop_id = str(shop_info.get("id") or "") or shop.shopify_shop_id
    shop.name = shop_info.get("name") or shop.name
    shop.shop_owner_email = shop_info.get("email") or shop.shop_owner_email
    shop.plan_name = shop_info.get("plan_name") or shop.plan_name
    shop.currency = shop_info.get("currency") or shop.currency
    shop.updated_at = now
    session.add(shop)
    session.commit()
    session.refresh(shop)

    # ── Webhooks (negocio + compliance) ───────────────────────────────────────
    register_webhooks_for_shop(shop)

    # ── Sync inicial de customers/orders/products (background) ───────────────
    if shop.initial_sync_status in ("pending", "failed") or is_new_shop:
        background_tasks.add_task(run_initial_sync, shop.id)

    # ── Usuario dueño de la tienda (para entrar al dashboard existente) ──────
    owner_email = shop.shop_owner_email or f"owner@{shop_domain}"
    user = session.exec(select(User).where(User.email == owner_email)).first()
    if not user:
        user = User(
            email=owner_email,
            name=shop_info.get("shop_owner") or owner_email,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            role="admin",
            shop_id=shop.id,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    elif user.shop_id != shop.id:
        # Usuario existente (ej. reinstalación) pero sin vincular todavía
        user.shop_id = shop.id
        session.add(user)
        session.commit()

    set_password_token = create_set_password_token(user.email)
    try:
        send_set_password_email(user, set_password_token)
    except Exception:
        logger.exception("No se pudo enviar el email de set-password para %s", user.email)

    return RedirectResponse(f"{settings.FRONTEND_URL}/login?installed=1")
