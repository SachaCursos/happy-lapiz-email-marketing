"""Resuelve credenciales y URLs de la API de Shopify por tienda (multi-tenant).

Reemplaza las lecturas directas de settings.SHOPIFY_ACCESS_TOKEN /
settings.SHOPIFY_DOMAIN que existían cuando la app era single-tenant.
"""
import httpx

from app.core.config import settings
from app.core.crypto import decrypt_token
from app.models.shop import Shop

API_VERSION = "2024-10"

# Topics de negocio + los 3 topics de compliance obligatorios para toda app
# que accede a datos de clientes (customers/data_request, customers/redact,
# shop/redact) y app/uninstalled para detectar desinstalaciones.
WEBHOOK_TOPICS = [
    "checkouts/create",
    "checkouts/update",
    "carts/create",
    "carts/update",
    "orders/create",
    "orders/fulfilled",
    "orders/partially_fulfilled",
    "orders/cancelled",
    "orders/updated",
    "refunds/create",
    "app/uninstalled",
    "customers/data_request",
    "customers/redact",
    "shop/redact",
]


def get_shopify_credentials(shop: Shop) -> tuple[str, str]:
    """Devuelve (access_token, domain) para la tienda dada."""
    return decrypt_token(shop.access_token_encrypted), shop.shopify_domain


def shopify_headers(shop: Shop) -> dict:
    token, _ = get_shopify_credentials(shop)
    return {"X-Shopify-Access-Token": token, "Content-Type": "application/json"}


def shopify_rest_url(shop: Shop, path: str, version: str = API_VERSION) -> str:
    """path ej: 'products.json', 'customers/123.json'"""
    return f"https://{shop.shopify_domain}/admin/api/{version}/{path.lstrip('/')}"


def shopify_graphql_url(shop: Shop, version: str = API_VERSION) -> str:
    return f"https://{shop.shopify_domain}/admin/api/{version}/graphql.json"


def register_webhooks_for_shop(shop: Shop) -> list[dict]:
    """Registra (o confirma) todos los webhooks de negocio + compliance para
    una tienda recién instalada. Idempotente: Shopify devuelve 422 si un
    webhook con el mismo topic+address ya existe, lo cual tratamos como ok.
    """
    backend_url = f"{settings.BACKEND_PUBLIC_URL}/api/shopify/webhooks"
    headers = shopify_headers(shop)

    results = []
    for topic in WEBHOOK_TOPICS:
        try:
            r = httpx.post(
                shopify_rest_url(shop, "webhooks.json"),
                headers=headers,
                json={"webhook": {"topic": topic, "address": backend_url, "format": "json"}},
                timeout=10,
            )
            if r.status_code in (200, 201):
                wh = r.json().get("webhook", {})
                results.append({"topic": topic, "ok": True, "id": wh.get("id")})
            elif r.status_code == 422:
                results.append({"topic": topic, "ok": True, "note": "ya existía"})
            else:
                results.append({"topic": topic, "ok": False, "error": r.text[:200]})
        except Exception as e:
            results.append({"topic": topic, "ok": False, "error": str(e)})
    return results
