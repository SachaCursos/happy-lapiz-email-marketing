"""Dominio de envío propio por tienda (SES) — ver app/services/ses_domain.py."""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.database import get_session
from app.core.deps import require_admin, get_current_shop
from app.models.user import User
from app.models.shop import Shop
from app.services import ses_domain

router = APIRouter()

_DOMAIN_RE = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63})+$")


class DnsRecord(BaseModel):
    type: str
    name: str
    value: str


class SendingDomainStatus(BaseModel):
    domain: str | None = None
    verified: bool = False
    dns_records: list[DnsRecord] = []


class CreateDomainBody(BaseModel):
    domain: str


@router.get("", response_model=SendingDomainStatus)
def get_sending_domain(
    shop: Shop = Depends(get_current_shop),
    _: User = Depends(require_admin),
):
    if not shop.sending_domain:
        return SendingDomainStatus()
    try:
        status_ = ses_domain.get_domain_status(shop.sending_domain)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"No se pudo consultar SES: {exc}")
    return SendingDomainStatus(
        domain=shop.sending_domain,
        verified=status_["verified"],
        dns_records=status_["dns_records"],
    )


@router.post("", response_model=SendingDomainStatus)
def create_sending_domain(
    body: CreateDomainBody,
    session: Session = Depends(get_session),
    shop: Shop = Depends(get_current_shop),
    _: User = Depends(require_admin),
):
    domain = body.domain.strip().lower()
    if not _DOMAIN_RE.match(domain):
        raise HTTPException(status_code=400, detail="Dominio inválido")
    try:
        dns_records = ses_domain.create_domain_identity(domain)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"No se pudo crear la identidad en SES: {exc}")

    live_shop = session.get(Shop, shop.id)
    live_shop.sending_domain = domain
    live_shop.sending_domain_verified = False
    session.add(live_shop)
    session.commit()

    return SendingDomainStatus(domain=domain, verified=False, dns_records=dns_records)


@router.post("/verify", response_model=SendingDomainStatus)
def verify_sending_domain(
    session: Session = Depends(get_session),
    shop: Shop = Depends(get_current_shop),
    _: User = Depends(require_admin),
):
    if not shop.sending_domain:
        raise HTTPException(status_code=400, detail="Esta tienda no tiene un dominio configurado")
    try:
        status_ = ses_domain.get_domain_status(shop.sending_domain)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"No se pudo consultar SES: {exc}")

    live_shop = session.get(Shop, shop.id)
    live_shop.sending_domain_verified = status_["verified"]
    session.add(live_shop)
    session.commit()

    return SendingDomainStatus(
        domain=shop.sending_domain,
        verified=status_["verified"],
        dns_records=status_["dns_records"],
    )


@router.delete("", response_model=SendingDomainStatus)
def delete_sending_domain(
    session: Session = Depends(get_session),
    shop: Shop = Depends(get_current_shop),
    _: User = Depends(require_admin),
):
    if not shop.sending_domain:
        return SendingDomainStatus()
    try:
        ses_domain.delete_domain_identity(shop.sending_domain)
    except Exception:
        pass  # si ya no existe en SES (o falla la baja), igual limpiamos nuestro lado

    live_shop = session.get(Shop, shop.id)
    live_shop.sending_domain = None
    live_shop.sending_domain_verified = False
    session.add(live_shop)
    session.commit()

    return SendingDomainStatus()
