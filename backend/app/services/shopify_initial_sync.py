"""Pull inicial de datos al instalar una tienda nueva: customers, orders (para
stats de contacto) y products. Corre una sola vez por instalación, disparado
como BackgroundTask desde el callback de OAuth (routers/shopify_oauth.py).

REST paginado (no GraphQL Bulk Operations): para un pull único al instalar,
el límite de 2 req/s de Shopify es suficiente y evita la complejidad de
someter/pollear/descargar un bulk operation asíncrono. Si en el futuro
instalan tiendas con catálogos/historiales muy grandes, migrar a Bulk
Operations es el siguiente paso natural.

Progreso/errores se trackean en Shop.initial_sync_status/_stats/_error — no
hace falta cola de jobs, es el mismo patrón que ya usa Campaign.status.
"""
import logging
import re
from datetime import datetime, timezone

import httpx
from sqlalchemy import text
from sqlmodel import Session

from app.database import engine
from app.models.shop import Shop
from app.services.shopify_client import shopify_headers, shopify_rest_url

logger = logging.getLogger(__name__)

PAGE_LIMIT = 250


def _paginate(client: httpx.Client, url: str, headers: dict, params: dict, root_key: str):
    """Yield todas las páginas de un endpoint REST de Shopify usando cursor pagination."""
    next_params = dict(params)
    next_url = url
    while True:
        r = client.get(next_url, params=next_params, headers=headers, timeout=30.0)
        if r.status_code != 200:
            raise RuntimeError(f"Shopify API {r.status_code} en {next_url}: {r.text[:200]}")
        items = r.json().get(root_key, [])
        yield items

        link_header = r.headers.get("Link", "")
        if 'rel="next"' not in link_header:
            break
        next_part = [p for p in link_header.split(",") if 'rel="next"' in p]
        m = re.search(r"page_info=([^&>]+)", next_part[0]) if next_part else None
        if not m:
            break
        next_url = url
        next_params = {"limit": PAGE_LIMIT, "page_info": m.group(1)}


def _sync_customers(client: httpx.Client, shop: Shop, session: Session) -> int:
    headers = shopify_headers(shop)
    url = shopify_rest_url(shop, "customers.json")
    params = {
        "limit": PAGE_LIMIT,
        "fields": "id,email,first_name,last_name,phone,orders_count,total_spent,"
                  "default_address,email_marketing_consent,created_at",
    }
    now = datetime.utcnow()
    count = 0
    for page in _paginate(client, url, headers, params, "customers"):
        for c in page:
            email = (c.get("email") or "").lower().strip()
            if not email:
                continue
            try:
                consent = c.get("email_marketing_consent") or {}
                opted_in = consent.get("state") == "subscribed"
                addr = c.get("default_address") or {}
                name = " ".join(filter(None, [c.get("first_name"), c.get("last_name")])).strip()

                existing = session.execute(
                    _contact_select_sql, {"email": email, "shop_id": shop.id}
                ).fetchone()
                if existing:
                    session.execute(_contact_update_sql, {
                        "email": email, "shop_id": shop.id, "name": name or None,
                        "phone": c.get("phone"),
                        "orders_count": int(c.get("orders_count") or 0),
                        "total_spent": float(c.get("total_spent") or 0),
                        "shipping_city": addr.get("city"),
                        "shipping_province": addr.get("province"),
                        "accepts_marketing": opted_in,
                        "now": now,
                    })
                else:
                    session.execute(_contact_insert_sql, {
                        "email": email, "shop_id": shop.id, "name": name or None,
                        "phone": c.get("phone"),
                        "orders_count": int(c.get("orders_count") or 0),
                        "total_spent": float(c.get("total_spent") or 0),
                        "shipping_city": addr.get("city"),
                        "shipping_province": addr.get("province"),
                        "opted_in": opted_in,
                        "accepts_marketing": opted_in,
                        "now": now,
                    })
                # Commit por cliente: si otro shop ya tiene ese email (la
                # constraint global unique de contacts.email no se relaja
                # hasta el deploy 3), esta fila se salta sin abortar el resto.
                session.commit()
                count += 1
            except Exception:
                session.rollback()
                logger.warning("No se pudo sincronizar el customer %s de shop_id=%s", email, shop.id)
    return count


def _sync_products(client: httpx.Client, shop: Shop, session: Session) -> int:
    headers = shopify_headers(shop)
    url = shopify_rest_url(shop, "products.json")
    params = {
        "limit": PAGE_LIMIT,
        "status": "active",
        "fields": "id,title,handle,product_type,tags,vendor,images,variants,status",
    }
    now = datetime.utcnow()
    count = 0
    for page in _paginate(client, url, headers, params, "products"):
        for p in page:
            try:
                variant = (p.get("variants") or [{}])[0]
                image_url = (p.get("images") or [{}])[0].get("src", "")
                session.execute(_product_upsert_sql, {
                    "shop_id": shop.id,
                    "sid": int(p["id"]),
                    "title": p.get("title", ""),
                    "handle": p.get("handle", ""),
                    "ptype": p.get("product_type", ""),
                    "tags": p.get("tags", ""),
                    "vendor": p.get("vendor", ""),
                    "img": image_url,
                    "price": float(variant.get("price") or 0),
                    "status": "active",
                    "now": now,
                })
                session.commit()
                count += 1
            except Exception:
                session.rollback()
                logger.warning("No se pudo sincronizar el producto %s de shop_id=%s", p.get("id"), shop.id)
    return count


def run_initial_sync(shop_id: int) -> None:
    # shopify_products may already exist from before this app owned it (e.g.
    # Happy Lápiz's original table, integrated with the WhatsApp catalog bot)
    # with a stale global-unique constraint or missing columns — self-heal
    # before syncing so a fresh shop's first sync can't silently upsert 0
    # rows against a schema this code no longer matches.
    try:
        from app.routers.admin import _ensure_shopify_products_table
        _ensure_shopify_products_table()
    except Exception:
        logger.exception("run_initial_sync: no se pudo verificar el schema de shopify_products")

    with Session(engine) as session:
        shop = session.get(Shop, shop_id)
        if not shop:
            logger.error("run_initial_sync: shop_id=%s no existe", shop_id)
            return

        shop.initial_sync_status = "running"
        shop.initial_sync_started_at = datetime.now(timezone.utc)
        session.add(shop)
        session.commit()

        stats = {"customers": 0, "products": 0}
        try:
            with httpx.Client() as client:
                stats["customers"] = _sync_customers(client, shop, session)
                stats["products"] = _sync_products(client, shop, session)

            shop.initial_sync_status = "complete"
            shop.initial_sync_completed_at = datetime.now(timezone.utc)
            shop.initial_sync_stats = stats
            shop.initial_sync_error = None
            session.add(shop)
            session.commit()
            logger.info("Initial sync completo para shop_id=%s: %s", shop_id, stats)

            # Contenido inicial para tiendas nuevas: Happy Lápiz tiene sus propias
            # automatizaciones de marca (cumpleaños/REGALO, cross-sell), pero el
            # resto arranca sin nada que enviar. generate_yearly_plan ya es
            # brand-neutral (usa los productos/color de esta tienda) e idempotente
            # (salta las entradas que ya existen), así que es seguro dispararlo acá.
            if shop.shopify_domain != "happy-lapiz.myshopify.com":
                try:
                    from sqlmodel import select
                    from app.models.user import User
                    from app.services.yearly_plan_generator import generate_yearly_plan

                    admin = session.exec(
                        select(User).where(User.shop_id == shop.id).order_by(User.id)
                    ).first()
                    generate_yearly_plan(session, shop, admin.id if admin else None)
                    logger.info("Plan de contenido anual generado para shop_id=%s", shop_id)
                except Exception:
                    logger.exception("No se pudo generar el plan de contenido anual para shop_id=%s", shop_id)
        except Exception as exc:
            logger.exception("Initial sync falló para shop_id=%s", shop_id)
            shop.initial_sync_status = "failed"
            shop.initial_sync_error = str(exc)[:500]
            shop.initial_sync_stats = stats
            session.add(shop)
            session.commit()


# ── Raw SQL (mismo estilo que el resto del repo para estas tablas) ──────────────
_contact_select_sql = text("SELECT id FROM contacts WHERE email = :email AND shop_id = :shop_id")

_contact_update_sql = text("""
    UPDATE contacts SET
        name = COALESCE(:name, name),
        phone = COALESCE(:phone, phone),
        orders_count = :orders_count,
        total_spent = :total_spent,
        shipping_city = COALESCE(:shipping_city, shipping_city),
        shipping_province = COALESCE(:shipping_province, shipping_province),
        accepts_marketing = :accepts_marketing,
        updated_at = :now
    WHERE email = :email AND shop_id = :shop_id
""")

_contact_insert_sql = text("""
    INSERT INTO contacts (
        shop_id, email, name, phone, orders_count, total_spent,
        shipping_city, shipping_province, opted_in, accepts_marketing,
        origin_utm, created_at, updated_at
    ) VALUES (
        :shop_id, :email, :name, :phone, :orders_count, :total_spent,
        :shipping_city, :shipping_province, :opted_in, :accepts_marketing,
        'shopify', :now, :now
    )
""")

_product_upsert_sql = text("""
    INSERT INTO shopify_products
        (shop_id, shopify_id, title, handle, product_type, tags, vendor, image_url, price, status, synced_at)
    VALUES
        (:shop_id, :sid, :title, :handle, :ptype, :tags, :vendor, :img, :price, :status, :now)
    ON CONFLICT (shop_id, shopify_id) DO UPDATE SET
        title        = EXCLUDED.title,
        handle       = EXCLUDED.handle,
        product_type = EXCLUDED.product_type,
        tags         = EXCLUDED.tags,
        vendor       = EXCLUDED.vendor,
        image_url    = EXCLUDED.image_url,
        price        = EXCLUDED.price,
        status       = EXCLUDED.status,
        synced_at    = EXCLUDED.synced_at
""")
