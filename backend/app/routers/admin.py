import re
import logging
import httpx
import mimetypes
from datetime import datetime
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlmodel import Session, select, text
from app.database import get_session, engine as db_engine

logger = logging.getLogger(__name__)
from app.core.config import settings
from app.core.deps import get_current_user, require_admin
from app.models.user import User
from app.models.template import Template
from app.models.campaign import Campaign, CampaignSend
from app.models.segment import Segment
from app.services.template_compositions import resolve_composition, ensure_managed_block_templates
from app.services.favorite_blocks_seed import (
    GALERIA_NAME,
    VACACIONES_NAME,
    BIENVENIDA_NAME,
)

router = APIRouter()

HL_LOGO = "https://cdn.shopify.com/s/files/1/0556/5343/3495/files/LOGO_HappyLapiz.png?v=1621889822"

FOOTER = """
<div style="border-top:1px solid #f3f4f6;margin-top:40px;padding-top:24px;text-align:center;">
  <img src="__HL_LOGO__" alt="Happy L&#225;piz" width="120" style="height:auto;display:inline-block;margin-bottom:12px;opacity:0.6;" />
  <p style="font-size:12px;color:#9ca3af;margin:4px 0;">Juguetes educativos &middot; Chile</p>
  <p style="font-size:12px;color:#d1d5db;margin:8px 0;">
    <a href="##unsub##" style="color:#d1d5db;">Cancelar suscripci&oacute;n</a>
  </p>
</div>"""

SEED_TEMPLATES = [
    {
        "name":    BIENVENIDA_NAME,
        "subject": "{{nombre or 'amigo/a'}}, bienvenido/a a Happy Lápiz 🎨",
        "preview": "Nos alegra tenerte aquí. Descubre nuestro catálogo de juguetes educativos.",
        "segment": "Todos los suscriptores",
        "composition": "bienvenida",
    },
    {
        "name":    VACACIONES_NAME,
        "subject": "{{nombre or 'Hola'}}, ideas para las vacaciones de tus pequeños ☀️",
        "preview": "Juegos, creatividad y aprendizaje para que disfruten al máximo sus vacaciones.",
        "segment": "Todos los suscriptores",
        "composition": "vacaciones",
    },
    {
        "name":    GALERIA_NAME,
        "subject": "Galería interna — opciones de bloques",
        "preview": "Plantilla de referencia para elegir bloques favoritos. No usar en campañas.",
        "segment": "_none",
        "composition": "galeria",
    },
    {
        "name":    "Cross-sell — Recomendados por compra",
        "subject": "{% if first_product %}¿Compraste {{ first_product }}? También podría interesarte...{% else %}Productos que te van a encantar ✨{% endif %}",
        "preview": "Basado en tu última compra, seleccionamos estos juguetes especialmente para ti.",
        "segment": "_none",
        "html":    "__CROSS_SELL__",
    },
]

CROSS_SELL_TEMPLATE_HTML = """\
<div style="font-family:'Helvetica Neue',Arial,sans-serif;max-width:600px;margin:0 auto;background:#ffffff;">

  <!-- Header -->
  <div style="background:#ffffff;padding:28px 32px 0;text-align:center;">
    <a href="https://www.happylapiz.cl" style="display:inline-block;">
      <img src="https://cdn.shopify.com/s/files/1/0556/5343/3495/files/LOGO_HappyLapiz.png?v=1621889822"
           alt="Happy L&#225;piz" width="160"
           style="height:auto;display:block;margin:0 auto;" />
    </a>
  </div>

  <!-- Hero banner -->
  <div style="background:linear-gradient(135deg,#5b21b6 0%,#682ae7 60%,#2a2ee7 100%);
              margin:24px 0 0;padding:36px 32px;text-align:center;">
    <p style="color:#e9d5ff;font-size:13px;font-weight:600;text-transform:uppercase;
              letter-spacing:1.5px;margin:0 0 10px;">Recomendado para ti</p>
    <h1 style="color:#ffffff;font-size:24px;font-weight:800;margin:0 0 12px;line-height:1.3;">
      {% if first_product %}
      Ya tienes {{ first_product }}<br/>&#161;Esto tambi&#233;n te va a encantar!
      {% else %}
      &#161;Hay productos que te pueden interesar!
      {% endif %}
    </h1>
    <p style="color:#ddd6fe;font-size:15px;margin:0;line-height:1.6;">
      Hola {{ first_name or 'amigo/a' }}, basado en tu compra seleccionamos estos juguetes especialmente para ti &#128071;
    </p>
  </div>

  <!-- Recommended products grid -->
  <div style="padding:32px 24px 0;">
    {% if recommended_products_html %}
    {{ recommended_products_html }}
    {% else %}
    <p style="color:#9ca3af;text-align:center;font-size:14px;padding:20px 0;">
      No encontramos productos adicionales por mostrar.
    </p>
    {% endif %}
  </div>

  <!-- CTA button -->
  <div style="text-align:center;padding:28px 32px 12px;">
    <a href="https://www.happylapiz.cl"
       style="background:#682ae7;color:#ffffff;font-weight:700;font-size:15px;
              padding:14px 40px;border-radius:30px;text-decoration:none;
              display:inline-block;letter-spacing:0.3px;">
      Ver toda la tienda &#8594;
    </a>
  </div>

  <!-- Tagline -->
  <p style="text-align:center;color:#9ca3af;font-size:13px;
            padding:0 32px 32px;margin:8px 0 0;line-height:1.6;">
    Juguetes educativos pensados para cada etapa del desarrollo &#127775;
  </p>

  <!-- Footer -->
  <div style="border-top:1px solid #f3f4f6;padding:24px 32px;text-align:center;">
    <a href="https://www.happylapiz.cl" style="display:inline-block;margin-bottom:14px;">
      <img src="https://cdn.shopify.com/s/files/1/0556/5343/3495/files/LOGO_HappyLapiz.png?v=1621889822"
           alt="Happy L&#225;piz" width="100"
           style="height:auto;display:block;margin:0 auto;opacity:0.5;" />
    </a>
    <p style="font-size:12px;color:#d1d5db;margin:0 0 6px;">
      Happy L&#225;piz &middot; Juguetes educativos &middot; Chile
    </p>
    <p style="font-size:12px;color:#d1d5db;margin:0;">
      <a href="##unsub##" style="color:#d1d5db;text-decoration:underline;">Cancelar suscripci&#243;n</a>
    </p>
  </div>

</div>"""

SEED_SEGMENTS = [
    {
        "name": "Todos los suscriptores",
        "description": "Todos los contactos con opt-in activo",
        "conditions": {"operator": "AND", "rules": [{"field": "opted_in", "op": "eq", "value": True}]},
    },
    {
        "name": "Mamás",
        "description": "Contactos etiquetados como mamá (custom_fields.es_mama = true)",
        "conditions": {"operator": "AND", "rules": [
            {"field": "opted_in", "op": "eq", "value": True},
            {"field": "custom_fields.es_mama", "op": "eq", "value": "true"},
        ]},
    },
]


@router.post("/seed-templates")
def seed_templates(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    """Crea o actualiza plantillas y campañas de ejemplo. Solo admins. Idempotente."""
    now = datetime.utcnow()
    created = {"segments": [], "templates": [], "campaigns": []}
    updated = {"templates": []}

    logo_url = HL_LOGO

    # Segmentos
    seg_map: dict[str, int] = {}
    for s in SEED_SEGMENTS:
        existing = session.exec(select(Segment).where(Segment.name == s["name"])).first()
        if existing:
            seg_map[s["name"]] = existing.id
        else:
            seg = Segment(name=s["name"], description=s["description"],
                          conditions=s["conditions"], created_by=current_user.id,
                          created_at=now, updated_at=now)
            session.add(seg)
            session.flush()
            seg_map[s["name"]] = seg.id
            created["segments"].append(s["name"])

    # Plantillas y campañas
    for t in SEED_TEMPLATES:
        existing_tpl = session.exec(select(Template).where(Template.name == t["name"])).first()
        composition = t.get("composition")
        if composition:
            json_blocks, html = resolve_composition(composition)
        else:
            json_blocks = None
            html = t["html"].replace("__LOGO_PNG__", logo_url).replace("__HL_LOGO__", logo_url).replace("__CROSS_SELL__", CROSS_SELL_TEMPLATE_HTML)
        if existing_tpl:
            existing_tpl.html_content    = html
            existing_tpl.json_blocks     = json_blocks
            existing_tpl.subject_default = t["subject"]
            existing_tpl.preview_text    = t["preview"]
            existing_tpl.updated_at      = now
            session.add(existing_tpl)
            tpl_id = existing_tpl.id
            updated["templates"].append(t["name"])
        else:
            tpl = Template(name=t["name"], subject_default=t["subject"], preview_text=t["preview"],
                           html_content=html, json_blocks=json_blocks, created_by=current_user.id,
                           created_at=now, updated_at=now)
            session.add(tpl)
            session.flush()
            tpl_id = tpl.id
            created["templates"].append(t["name"])

        seg_id = seg_map.get(t["segment"])
        if seg_id:
            existing_camp = session.exec(select(Campaign).where(Campaign.name == t["name"])).first()
            if not existing_camp:
                camp = Campaign(name=t["name"], subject=t["subject"], template_id=tpl_id,
                                segment_id=seg_id, status="draft", created_by=current_user.id,
                                created_at=now)
                session.add(camp)
                created["campaigns"].append(t["name"])

    # Asegurar unsub en TODAS las plantillas de la BD
    all_templates = session.exec(select(Template)).all()
    added_unsub: list[str] = []
    for tpl in all_templates:
        if "##unsub##" in tpl.html_content:
            continue  # ya actualizada
        if 'href="#" style="color:#bbb;">Cancelar suscripci' in tpl.html_content:
            # Actualizar placeholder viejo
            tpl.html_content = tpl.html_content.replace(
                'href="#" style="color:#bbb;">Cancelar suscripci',
                'href="##unsub##" style="color:#bbb;">Cancelar suscripci',
            )
            tpl.updated_at = now
            session.add(tpl)
            added_unsub.append(tpl.name)
        elif "Cancelar suscripci" not in tpl.html_content:
            # Sin sección de baja → agregar al final
            tpl.html_content = tpl.html_content.rstrip() + FOOTER
            tpl.updated_at = now
            session.add(tpl)
            added_unsub.append(tpl.name)

    # Corregir envíos mal clasificados como "bounced" que en realidad fallaron técnicamente
    # (sin resend_id y sin bounced_at significa que nunca llegaron a Resend)
    bad_sends = session.exec(
        select(CampaignSend).where(
            CampaignSend.status == "bounced",
            CampaignSend.resend_id == None,  # noqa: E711
            CampaignSend.bounced_at == None,  # noqa: E711
        )
    ).all()
    for s in bad_sends:
        s.status = "failed"
        session.add(s)
    fixed_sends = len(bad_sends)

    # Resetear a "draft" las campañas que tienen envíos fallidos pendientes de reintento
    affected_campaign_ids = {s.campaign_id for s in bad_sends}
    for cid in affected_campaign_ids:
        camp = session.get(Campaign, cid)
        if camp and camp.status == "sent":
            camp.status = "draft"
            session.add(camp)

    session.commit()
    return {"ok": True, "created": created, "updated": updated, "unsub_added": added_unsub, "fixed_failed_sends": fixed_sends}


@router.post("/fix-logo")
def fix_logo(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    """Replace old placeholder logos with the Happy Lápiz logo in all templates."""
    old_pattern = re.compile(r'(__LOGO_PNG__|__HL_LOGO__|https?://hotboatchile\.com/[^\s"\']+)')
    now = datetime.utcnow()
    all_templates = session.exec(select(Template)).all()
    fixed = []
    for tpl in all_templates:
        new_html = old_pattern.sub(HL_LOGO, tpl.html_content or "")
        if new_html != tpl.html_content:
            tpl.html_content = new_html
            tpl.updated_at = now
            session.add(tpl)
            fixed.append(tpl.name)
    session.commit()
    return {"ok": True, "fixed": fixed, "logo_url": HL_LOGO}


@router.post("/repair-email-typos")
def repair_email_typos(
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    """Corrige dominios mal escritos en contactos existentes (gmail.con → gmail.com, etc.)."""
    from app.services.email_typo_fix import repair_typo_emails

    return repair_typo_emails(session)


_SHOPIFY_PRODUCTS_CREATE = """
    CREATE TABLE shopify_products (
        id SERIAL PRIMARY KEY,
        shopify_id BIGINT UNIQUE NOT NULL,
        title VARCHAR NOT NULL,
        handle VARCHAR,
        product_type VARCHAR,
        tags TEXT,
        vendor VARCHAR,
        image_url TEXT,
        price NUMERIC(10,2),
        status VARCHAR NOT NULL DEFAULT 'active',
        synced_at TIMESTAMP NOT NULL DEFAULT NOW(),
        edad_recomendada VARCHAR
    )
"""

def _ensure_shopify_products_table() -> None:
    """Ensure shopify_products exists with the correct schema.
    Uses AUTOCOMMIT so DDL can never be blocked by an open transaction.
    Adds missing columns in-place to preserve any dependent views.
    """
    with db_engine.connect() as conn:
        conn = conn.execution_options(isolation_level="AUTOCOMMIT")

        # Create table from scratch if it doesn't exist at all
        table_exists = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name = 'shopify_products'"
        )).scalar()
        if not table_exists:
            logger.warning("shopify_products does not exist — creating table")
            conn.execute(text(_SHOPIFY_PRODUCTS_CREATE))
            return

        # Table exists — add any missing columns in-place (preserves dependent views)
        existing_cols = {
            row[0] for row in conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'shopify_products'"
            ))
        }
        needed = {
            "shopify_id":       "BIGINT",
            "title":            "VARCHAR",
            "handle":           "VARCHAR",
            "product_type":     "VARCHAR",
            "tags":             "TEXT",
            "vendor":           "VARCHAR",
            "image_url":        "TEXT",
            "price":            "NUMERIC(10,2)",
            "status":           "VARCHAR NOT NULL DEFAULT 'active'",
            "synced_at":        "TIMESTAMP NOT NULL DEFAULT NOW()",
            "edad_recomendada": "VARCHAR",
            "inventory_total": "INTEGER NOT NULL DEFAULT 0",
        }
        for col, col_type in needed.items():
            if col not in existing_cols:
                logger.warning("shopify_products: adding missing column %s", col)
                conn.execute(text(f"ALTER TABLE shopify_products ADD COLUMN {col} {col_type}"))

        # Ensure unique index on shopify_id exists
        idx_exists = conn.execute(text(
            "SELECT COUNT(*) FROM pg_indexes "
            "WHERE tablename = 'shopify_products' AND indexname = 'shopify_products_shopify_id_key'"
        )).scalar()
        if not idx_exists:
            conn.execute(text(
                "ALTER TABLE shopify_products ADD CONSTRAINT shopify_products_shopify_id_key "
                "UNIQUE (shopify_id)"
            ))

        try:
            _repair_shopify_products_id_sequence(conn)
        except Exception as exc:
            logger.warning("shopify_products id sequence repair skipped: %s", exc)


def _repair_shopify_products_id_sequence(conn) -> None:
    """Ensure shopify_products.id auto-increments (legacy tables may lack SERIAL default)."""
    has_id = conn.execute(text(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_name = 'shopify_products' AND column_name = 'id'"
    )).scalar()
    if not has_id:
        return

    seq = conn.execute(text(
        "SELECT pg_get_serial_sequence('shopify_products', 'id')"
    )).scalar()

    if not seq:
        conn.execute(text("CREATE SEQUENCE IF NOT EXISTS shopify_products_id_seq"))
        conn.execute(text(
            "ALTER TABLE shopify_products "
            "ALTER COLUMN id SET DEFAULT nextval('shopify_products_id_seq')"
        ))
        conn.execute(text(
            "ALTER SEQUENCE shopify_products_id_seq OWNED BY shopify_products.id"
        ))
        seq = "shopify_products_id_seq"

    max_id = conn.execute(text(
        "SELECT MAX(id) FROM shopify_products"
    )).scalar()
    if max_id is None:
        conn.execute(text(f"SELECT setval('{seq}', 1, false)"))
    else:
        conn.execute(text(f"SELECT setval('{seq}', :max_id, true)"), {"max_id": int(max_id)})


def _fetch_inventory_levels_map(token: str, domain: str, item_ids: list[int]) -> dict[int, int]:
    """Sum available stock per inventory_item_id across Shopify locations."""
    if not item_ids:
        return {}
    headers = {"X-Shopify-Access-Token": token}
    url = f"https://{domain}/admin/api/2024-01/inventory_levels.json"
    totals: dict[int, int] = {}
    unique_ids = list({int(i) for i in item_ids if i})

    with httpx.Client(timeout=60.0) as client:
        for offset in range(0, len(unique_ids), 50):
            batch = unique_ids[offset : offset + 50]
            r = client.get(
                url,
                params={"inventory_item_ids": ",".join(str(x) for x in batch), "limit": 250},
                headers=headers,
            )
            if r.status_code != 200:
                logger.warning("inventory_levels API %s: %s", r.status_code, r.text[:200])
                continue
            for level in r.json().get("inventory_levels") or []:
                iid = int(level.get("inventory_item_id") or 0)
                if not iid:
                    continue
                avail = level.get("available")
                if avail is None:
                    continue
                totals[iid] = totals.get(iid, 0) + int(avail)
    return totals


def _fetch_rest_product_inventory_map(token: str, domain: str) -> dict[int, int]:
    """Fallback: product shopify_id -> total inventory from REST (full variant payload)."""
    import re as _re

    headers = {"X-Shopify-Access-Token": token}
    url = f"https://{domain}/admin/api/2024-01/products.json"
    params: dict = {"limit": 250, "status": "active"}
    result: dict[int, int] = {}

    with httpx.Client(timeout=60.0) as client:
        while True:
            r = client.get(url, params=params, headers=headers)
            if r.status_code != 200:
                logger.warning("REST products inventory fallback %s: %s", r.status_code, r.text[:200])
                break
            for p in r.json().get("products") or []:
                pid = int(p.get("id") or 0)
                if not pid:
                    continue
                variants = p.get("variants") or []
                result[pid] = sum(int(v.get("inventory_quantity") or 0) for v in variants)
            link_header = r.headers.get("Link", "")
            if 'rel="next"' not in link_header:
                break
            next_part = [part for part in link_header.split(",") if 'rel="next"' in part]
            m = _re.search(r"page_info=([^&>]+)", next_part[0]) if next_part else None
            if not m:
                break
            params = {"limit": 250, "page_info": m.group(1)}
    return result


def _fetch_shopify_products_for_sync(token: str, domain: str) -> tuple[list[dict], str | None]:
    """Fetch active products from Shopify (GraphQL + inventory_levels for accurate stock)."""
    gql_url = f"https://{domain}/admin/api/2024-01/graphql.json"
    headers = {"X-Shopify-Access-Token": token, "Content-Type": "application/json"}
    query = """
    query SyncProducts($cursor: String) {
      products(first: 100, query: "status:active", after: $cursor) {
        pageInfo { hasNextPage endCursor }
        edges {
          node {
            legacyResourceId
            title
            handle
            productType
            tags
            vendor
            status
            featuredImage { url }
            variants(first: 100) {
              edges {
                node {
                  price
                  inventoryQuantity
                  inventoryItem { legacyResourceId }
                }
              }
            }
          }
        }
      }
    }
    """
    parsed: list[dict] = []
    all_item_ids: list[int] = []
    cursor: str | None = None

    with httpx.Client(timeout=60.0) as client:
        while True:
            r = client.post(
                gql_url,
                headers=headers,
                json={"query": query, "variables": {"cursor": cursor}},
            )
            if r.status_code != 200:
                return [], f"Shopify GraphQL {r.status_code}: {r.text[:200]}"
            payload = r.json()
            if payload.get("errors"):
                return [], f"Shopify GraphQL: {payload['errors'][0].get('message', payload['errors'])}"
            data = (payload.get("data") or {}).get("products") or {}
            for edge in data.get("edges") or []:
                node = edge.get("node") or {}
                legacy_id = node.get("legacyResourceId")
                if not legacy_id:
                    continue
                variant_edges = (node.get("variants") or {}).get("edges") or []
                price = 0.0
                variant_item_ids: list[int] = []
                variant_qty_sum = 0
                if variant_edges:
                    try:
                        price = float(variant_edges[0]["node"].get("price") or 0)
                    except (TypeError, ValueError, KeyError):
                        price = 0.0
                    for ve in variant_edges:
                        vn = ve.get("node") or {}
                        variant_qty_sum += int(vn.get("inventoryQuantity") or 0)
                        iid = (vn.get("inventoryItem") or {}).get("legacyResourceId")
                        if iid:
                            variant_item_ids.append(int(iid))
                            all_item_ids.append(int(iid))
                tags = node.get("tags") or []
                parsed.append({
                    "id": int(legacy_id),
                    "title": node.get("title") or "",
                    "handle": node.get("handle") or "",
                    "product_type": node.get("productType") or "",
                    "tags": ", ".join(tags) if isinstance(tags, list) else str(tags or ""),
                    "vendor": node.get("vendor") or "",
                    "image_url": (node.get("featuredImage") or {}).get("url") or "",
                    "price": price,
                    "status": "active" if (node.get("status") or "").upper() == "ACTIVE" else "draft",
                    "variant_item_ids": variant_item_ids,
                    "variant_qty_sum": variant_qty_sum,
                })
            page_info = data.get("pageInfo") or {}
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")
            if not cursor:
                break

    inventory_by_item = _fetch_inventory_levels_map(token, domain, all_item_ids)
    rest_inventory_by_product = _fetch_rest_product_inventory_map(token, domain)

    all_products: list[dict] = []
    for p in parsed:
        from_levels = sum(inventory_by_item.get(iid, 0) for iid in p["variant_item_ids"])
        from_rest = rest_inventory_by_product.get(p["id"], 0)
        from_variants = p["variant_qty_sum"]
        inventory_total = max(from_levels, from_rest, from_variants)
        row = {k: v for k, v in p.items() if k not in ("variant_item_ids", "variant_qty_sum")}
        row["inventory_total"] = inventory_total
        all_products.append(row)

    return all_products, None


@router.post("/sync-products")
def sync_shopify_products(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    """Sync all Shopify products to local shopify_products table (tags, type, image, price, inventory)."""
    from app.core.config import settings as _s
    token = _s.SHOPIFY_ACCESS_TOKEN
    domain = _s.SHOPIFY_DOMAIN
    if not token:
        return {"ok": False, "error": "SHOPIFY_ACCESS_TOKEN not configured"}

    all_products, fetch_error = _fetch_shopify_products_for_sync(token, domain)
    if fetch_error:
        return {"ok": False, "error": fetch_error}

    try:
        _ensure_shopify_products_table()
    except Exception as exc:
        logger.error("_ensure_shopify_products_table failed: %s", exc, exc_info=True)
        return {"ok": False, "error": f"Error preparando tabla: {exc}"}

    now = datetime.utcnow()
    upserted = 0
    errors: list[str] = []
    sql = text("""
        INSERT INTO shopify_products
            (shopify_id, title, handle, product_type, tags, vendor, image_url, price, status, synced_at, inventory_total)
        VALUES
            (:sid, :title, :handle, :ptype, :tags, :vendor, :img, :price, :status, :now, :inventory)
        ON CONFLICT (shopify_id) DO UPDATE SET
            title        = EXCLUDED.title,
            handle       = EXCLUDED.handle,
            product_type = EXCLUDED.product_type,
            tags         = EXCLUDED.tags,
            vendor       = EXCLUDED.vendor,
            image_url    = EXCLUDED.image_url,
            price        = EXCLUDED.price,
            status       = EXCLUDED.status,
            synced_at    = EXCLUDED.synced_at,
            inventory_total = EXCLUDED.inventory_total
    """)
    for p in all_products:
        try:
            session.execute(sql, {
                "sid":    int(p["id"]),
                "title":  p.get("title", ""),
                "handle": p.get("handle", ""),
                "ptype":  p.get("product_type", ""),
                "tags":   p.get("tags", ""),
                "vendor": p.get("vendor", ""),
                "img":    p.get("image_url", ""),
                "price":  p.get("price", 0),
                "status": p.get("status", "active"),
                "now":    now,
                "inventory": int(p.get("inventory_total") or 0),
            })
            session.commit()  # commit each product individually so one failure doesn't abort the rest
            upserted += 1
        except Exception as exc:
            session.rollback()  # reset transaction state so next insert can proceed
            errors.append(f"{p.get('id')}: {str(exc)[:120]}")
    return {
        "ok": upserted > 0 or len(all_products) == 0,
        "synced": upserted,
        "total_fetched": len(all_products),
        "errors": errors[:10],  # first 10 errors for diagnosis
    }


_SORT_COLUMNS = {
    "title": "title",
    "product_type": "product_type",
    "tags": "tags",
    "price": "price",
    "status": "status",
    "edad_recomendada": "edad_recomendada",
    "inventory_total": "inventory_total",
}

@router.get("/products")
def list_synced_products(
    search: str = "",
    product_type: str = "",
    page: int = 1,
    per_page: int = 50,
    sort_by: str = "title",
    sort_dir: str = "asc",
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    """Devuelve los productos sincronizados desde Shopify."""
    try:
        _ensure_shopify_products_table()
    except Exception as exc:
        logger.error("_ensure_shopify_products_table failed: %s", exc, exc_info=True)
        return {"total": 0, "page": page, "per_page": per_page, "products": [], "product_types": [], "error": str(exc)}

    col = _SORT_COLUMNS.get(sort_by, "title")
    direction = "DESC" if sort_dir.lower() == "desc" else "ASC"

    where_clauses = ["1=1"]
    params: dict = {}
    if search:
        where_clauses.append("(title ILIKE :search OR tags ILIKE :search)")
        params["search"] = f"%{search}%"
    if product_type:
        where_clauses.append("product_type = :ptype")
        params["ptype"] = product_type
    where = " AND ".join(where_clauses)

    total_row = session.execute(text(f"SELECT COUNT(*) FROM shopify_products WHERE {where}"), params).fetchone()
    total = int(total_row[0]) if total_row else 0

    params["offset"] = (page - 1) * per_page
    params["limit"] = per_page
    rows = session.execute(
        text(f"""
            SELECT shopify_id, title, handle, product_type, tags, vendor, image_url, price, status, synced_at, edad_recomendada, inventory_total
            FROM shopify_products WHERE {where}
            ORDER BY {col} {direction} NULLS LAST
            LIMIT :limit OFFSET :offset
        """),
        params,
    ).fetchall()

    types_rows = session.execute(
        text("SELECT DISTINCT product_type FROM shopify_products WHERE product_type IS NOT NULL AND product_type <> '' ORDER BY product_type")
    ).fetchall()

    products = [
        {
            "shopify_id": r[0], "title": r[1], "handle": r[2],
            "product_type": r[3], "tags": r[4], "vendor": r[5],
            "image_url": r[6], "price": float(r[7] or 0),
            "status": r[8], "synced_at": str(r[9]) if r[9] else None,
            "edad_recomendada": r[10],
            "inventory_total": int(r[11] or 0),
        }
        for r in rows
    ]
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "products": products,
        "product_types": [r[0] for r in types_rows],
    }


@router.post("/register-shopify-webhooks")
def register_shopify_webhooks(current_user: User = Depends(require_admin)):
    """Registra los webhooks de Shopify en la tienda usando el token del backend."""
    token = settings.SHOPIFY_ACCESS_TOKEN
    if not token:
        return {"ok": False, "error": "SHOPIFY_ACCESS_TOKEN no configurado en Railway"}

    domain = settings.SHOPIFY_DOMAIN
    backend_url = f"{settings.BACKEND_PUBLIC_URL}/api/shopify/webhooks"
    headers = {"X-Shopify-Access-Token": token, "Content-Type": "application/json"}

    topics = [
        # Shopify order lifecycle
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
    ]

    results = []
    for topic in topics:
        try:
            r = httpx.post(
                f"https://{domain}/admin/api/2024-10/webhooks.json",
                headers=headers,
                json={"webhook": {"topic": topic, "address": backend_url, "format": "json"}},
                timeout=10,
            )
            if r.status_code in (200, 201):
                wh = r.json().get("webhook", {})
                results.append({"topic": topic, "ok": True, "id": wh.get("id")})
            elif r.status_code == 422:
                # Already registered
                results.append({"topic": topic, "ok": True, "note": "ya existía"})
            else:
                results.append({"topic": topic, "ok": False, "error": r.text[:100]})
        except Exception as e:
            results.append({"topic": topic, "ok": False, "error": str(e)})

    all_ok = all(r["ok"] for r in results)
    return {"ok": all_ok, "endpoint": backend_url, "webhooks": results}


@router.post("/register-shopify-script-tag")
def register_shopify_script_tag(current_user: User = Depends(require_admin)):
    """Registra el script tag de tracking en la tienda Shopify."""
    token = settings.SHOPIFY_ACCESS_TOKEN
    if not token:
        return {"ok": False, "error": "SHOPIFY_ACCESS_TOKEN no configurado"}

    domain = settings.SHOPIFY_DOMAIN
    script_url = f"{settings.BACKEND_PUBLIC_URL}/api/forms/track.js"
    headers = {"X-Shopify-Access-Token": token, "Content-Type": "application/json"}

    # Check if already registered
    existing = httpx.get(f"https://{domain}/admin/api/2024-10/script_tags.json",
                         headers=headers, timeout=10)
    if existing.status_code == 200:
        tags = existing.json().get("script_tags", [])
        for tag in tags:
            if tag.get("src") == script_url:
                return {"ok": True, "note": "ya existía", "id": tag["id"], "src": script_url}

    r = httpx.post(
        f"https://{domain}/admin/api/2024-10/script_tags.json",
        headers=headers,
        json={"script_tag": {"event": "onload", "src": script_url}},
        timeout=10,
    )
    if r.status_code in (200, 201):
        tag = r.json().get("script_tag", {})
        return {"ok": True, "id": tag.get("id"), "src": script_url}
    return {"ok": False, "error": r.text[:200]}


@router.post("/sync-shopify-form-embeds")
def sync_shopify_form_embeds(
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    """Actualiza en Shopify el script del formulario (loader.js con tracking)."""
    from app.services.form_embed_snippet import sync_form_embed_to_shopify
    return sync_form_embed_to_shopify(session)


@router.post("/upload-image")
async def upload_image_to_shopify(
    file: UploadFile = File(...),
    _: User = Depends(get_current_user),
):
    """
    Sube una imagen a Shopify Files y devuelve la URL cdn.shopify.com.
    Flujo: stagedUploadsCreate → PUT al S3 presignado → fileCreate.
    """
    token  = settings.SHOPIFY_ACCESS_TOKEN
    domain = settings.SHOPIFY_DOMAIN
    if not token:
        raise HTTPException(status_code=500, detail="SHOPIFY_ACCESS_TOKEN no configurado")

    content   = await file.read()
    mime_type = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "image/jpeg"
    filename  = file.filename or "image.jpg"
    file_size = len(content)

    gql_url = f"https://{domain}/admin/api/2024-01/graphql.json"
    headers = {"X-Shopify-Access-Token": token, "Content-Type": "application/json"}

    # 1. Request a staged upload target from Shopify
    stage_query = """
    mutation stagedUploadsCreate($input: [StagedUploadInput!]!) {
      stagedUploadsCreate(input: $input) {
        stagedTargets {
          url
          resourceUrl
          parameters { name value }
        }
        userErrors { field message }
      }
    }
    """
    stage_vars = {"input": [{
        "filename":   filename,
        "mimeType":   mime_type,
        "resource":   "FILE",
        "fileSize":   str(file_size),
        "httpMethod": "POST",
    }]}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(gql_url, headers=headers, json={"query": stage_query, "variables": stage_vars})

    data = r.json()
    targets = data.get("data", {}).get("stagedUploadsCreate", {}).get("stagedTargets", [])
    errors  = data.get("data", {}).get("stagedUploadsCreate", {}).get("userErrors", [])
    if errors or not targets:
        raise HTTPException(status_code=500, detail=f"Shopify staged upload error: {errors or data}")

    target       = targets[0]
    upload_url   = target["url"]
    resource_url = target["resourceUrl"]
    params       = {p["name"]: p["value"] for p in target["parameters"]}

    # 2. POST the file to the presigned S3 URL
    async with httpx.AsyncClient(timeout=60) as client:
        r2 = await client.post(
            upload_url,
            data=params,
            files={"file": (filename, content, mime_type)},
        )
    if r2.status_code not in (200, 201, 204):
        raise HTTPException(status_code=500, detail=f"S3 upload failed: {r2.status_code} {r2.text[:200]}")

    # 3. Register the file in Shopify Files
    create_query = """
    mutation fileCreate($files: [FileCreateInput!]!) {
      fileCreate(files: $files) {
        files {
          ... on MediaImage { image { url } }
          ... on GenericFile  { url }
        }
        userErrors { field message }
      }
    }
    """
    create_vars = {"files": [{"originalSource": resource_url, "contentType": "IMAGE"}]}

    async with httpx.AsyncClient(timeout=30) as client:
        r3 = await client.post(gql_url, headers=headers, json={"query": create_query, "variables": create_vars})

    data3  = r3.json()
    files  = data3.get("data", {}).get("fileCreate", {}).get("files", [])
    errors3 = data3.get("data", {}).get("fileCreate", {}).get("userErrors", [])

    cdn_url = None
    if files:
        f = files[0]
        cdn_url = f.get("image", {}).get("url") or f.get("url")

    if not cdn_url:
        # Shopify sometimes takes a moment to process — return the resource_url as fallback
        cdn_url = resource_url

    return {"ok": True, "url": cdn_url}


@router.get("/shopify-images")
def list_shopify_images(
    after: str = None,
    _: User = Depends(get_current_user),
):
    """List images from Shopify Files for the in-editor image picker."""
    token  = settings.SHOPIFY_ACCESS_TOKEN
    domain = settings.SHOPIFY_DOMAIN
    if not token:
        raise HTTPException(status_code=500, detail="SHOPIFY_ACCESS_TOKEN no configurado")

    gql = """
    query getImages($after: String) {
      files(first: 30, after: $after, sortKey: CREATED_AT, reverse: true, query: "media_type:IMAGE") {
        pageInfo { hasNextPage endCursor }
        nodes {
          ... on MediaImage {
            image { url width height altText }
          }
        }
      }
    }"""
    variables = {"after": after} if after else {}
    resp = httpx.post(
        f"https://{domain}/admin/api/2024-01/graphql.json",
        headers={"X-Shopify-Access-Token": token, "Content-Type": "application/json"},
        json={"query": gql, "variables": variables},
        timeout=20,
    )
    data   = resp.json().get("data", {}).get("files", {})
    nodes  = [n for n in data.get("nodes", []) if n]
    images = []
    for n in nodes:
        img = n.get("image") or {}
        url = img.get("url", "")
        if url:
            images.append({"url": url, "width": img.get("width"), "height": img.get("height"), "alt": img.get("altText") or ""})
    return {"images": images, "pageInfo": data.get("pageInfo", {})}


@router.get("/brand")
def get_brand_assets(
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """Devuelve los activos de marca: colores, logos y tipografía."""
    rows = session.exec(
        text("SELECT id, categoria, nombre, valor, descripcion FROM plantillas_de_la_marca ORDER BY categoria, id")
    ).all()
    result: dict = {"colores": [], "logos": [], "tipografia": []}
    for r in rows:
        item = {"id": r[0], "nombre": r[2], "valor": r[3], "descripcion": r[4]}
        if r[1] == "color":
            result["colores"].append(item)
        elif r[1] == "logo":
            result["logos"].append(item)
        elif r[1] == "tipografia":
            result["tipografia"].append(item)
    return result
