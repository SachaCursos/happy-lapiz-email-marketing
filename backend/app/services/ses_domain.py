"""Verificación de dominios de envío propios por tienda (SES, Easy DKIM).

Cada tienda que quiera mandar desde su propio dominio (en vez de la
dirección compartida hola@happylapiz.cl) crea acá una identidad de dominio
en SES y agrega los 3 CNAME de DKIM que devuelve a su propio DNS — nosotros
no tenemos ni necesitamos acceso a ese DNS, es un paso manual de la tienda.
No guardamos los tokens DKIM: se piden en vivo a SES cada vez que hace falta
mostrarlos, así nunca quedan desactualizados."""
from typing import List, TypedDict

import boto3

from app.core.config import settings


class DnsRecord(TypedDict):
    type: str
    name: str
    value: str


def _client():
    return boto3.client(
        "sesv2",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
    )


def _dkim_records(domain: str, tokens: List[str]) -> List[DnsRecord]:
    return [
        {
            "type": "CNAME",
            "name": f"{token}._domainkey.{domain}",
            "value": f"{token}.dkim.amazonses.com",
        }
        for token in tokens
    ]


def create_domain_identity(domain: str) -> List[DnsRecord]:
    resp = _client().create_email_identity(EmailIdentity=domain)
    tokens = resp.get("DkimAttributes", {}).get("Tokens", [])
    return _dkim_records(domain, tokens)


def get_domain_status(domain: str) -> dict:
    resp = _client().get_email_identity(EmailIdentity=domain)
    dkim = resp.get("DkimAttributes", {})
    tokens = dkim.get("Tokens", [])
    return {
        "verified": dkim.get("Status") == "SUCCESS",
        "dkim_status": dkim.get("Status", "NOT_STARTED"),
        "dns_records": _dkim_records(domain, tokens),
    }


def delete_domain_identity(domain: str) -> None:
    _client().delete_email_identity(EmailIdentity=domain)
