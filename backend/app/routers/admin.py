import re
import httpx
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlmodel import Session, select, text
from app.database import get_session
from app.core.config import settings
from app.core.deps import get_current_user, require_admin
from app.models.user import User
from app.models.template import Template
from app.models.campaign import Campaign, CampaignSend
from app.models.segment import Segment

router = APIRouter()

FOOTER = """
<div style="border-top:1px solid #eee;margin-top:40px;padding-top:24px;text-align:center;">
  <p style="font-size:13px;font-weight:700;color:#111;margin:0 0 4px;">HotBoat</p>
  <p style="font-size:12px;color:#999;margin:4px 0;">Experiencias en el agua &middot; Chile</p>
  <p style="font-size:12px;color:#bbb;margin:8px 0;">
    <a href="##unsub##" style="color:#bbb;">Cancelar suscripci&oacute;n</a>
  </p>
</div>"""

SEED_TEMPLATES = [
    {
        "name":    "Bienvenida — Lista HotBoat",
        "subject": "{{nombre}}, bienvenido/a a HotBoat 🌊",
        "preview": "Nos alegra tenerte aquí. Descubre lo que tenemos preparado para ti.",
        "segment": "Todos los suscriptores",
        "html": """<div style="font-family:Inter,Arial,sans-serif;max-width:600px;margin:0 auto;padding:40px 32px;">
  <div style="background:#f9fafb;border-radius:16px;padding:44px 40px;text-align:center;margin-bottom:32px;border:1px solid #e5e7eb;">
    <img src="__LOGO_PNG__" alt="HotBoat" style="height:80px;width:auto;margin-bottom:20px;display:block;margin-left:auto;margin-right:auto;" />
    <h1 style="color:#111;font-size:20px;font-weight:700;margin:0 0 10px;line-height:1.3;">Bienvenido/a a HotBoat, {{nombre or 'cliente'}}</h1>
    <p style="color:#555;font-size:16px;margin:0;">Nos alegra tenerte en nuestra comunidad</p>
  </div>
  <p style="font-size:16px;color:#333;line-height:1.75;margin-bottom:24px;">
    Hola {{nombre}}, acabas de unirte a la lista de HotBoat.
    Desde aquí te haremos llegar las mejores experiencias en el agua,
    fechas exclusivas y ofertas especiales pensadas para ti.
  </p>
  <div style="background:#f9fafb;border-radius:14px;padding:28px;margin-bottom:28px;">
    <p style="font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;color:#999;margin:0 0 16px;">Qué recibirás</p>
    <div style="display:flex;flex-direction:column;gap:12px;">
      <div style="display:flex;align-items:flex-start;gap:14px;">
        <span style="font-size:22px;line-height:1;flex-shrink:0;">📅</span>
        <div>
          <p style="font-weight:700;color:#111;font-size:15px;margin:0 0 2px;">Nuevas fechas antes que nadie</p>
          <p style="color:#666;font-size:14px;margin:0;">Acceso anticipado cuando abramos nuevos cupos.</p>
        </div>
      </div>
      <div style="display:flex;align-items:flex-start;gap:14px;">
        <span style="font-size:22px;line-height:1;flex-shrink:0;">🎁</span>
        <div>
          <p style="font-weight:700;color:#111;font-size:15px;margin:0 0 2px;">Ofertas y beneficios exclusivos</p>
          <p style="color:#666;font-size:14px;margin:0;">Descuentos y experiencias solo para nuestra lista.</p>
        </div>
      </div>
      <div style="display:flex;align-items:flex-start;gap:14px;">
        <span style="font-size:22px;line-height:1;flex-shrink:0;">🌊</span>
        <div>
          <p style="font-weight:700;color:#111;font-size:15px;margin:0 0 2px;">Contenido del lago y el agua</p>
          <p style="color:#666;font-size:14px;margin:0;">Tips, historias y momentos de la comunidad HotBoat.</p>
        </div>
      </div>
    </div>
  </div>
  <div style="text-align:center;margin:32px 0;">
    <a href="https://hotboat.cl" style="background:#2563eb;color:#fff;font-weight:700;padding:15px 44px;border-radius:11px;text-decoration:none;font-size:16px;display:inline-block;">Ver experiencias disponibles</a>
  </div>
  <p style="font-size:13px;color:#aaa;text-align:center;line-height:1.6;margin-top:32px;">
    Si no quieres recibir nuestros correos, puedes darte de baja en cualquier momento desde el enlace al pie de este mensaje.
  </p>""" + FOOTER + "</div>",
    },
    {
        "name":    "Día de la Madre — Bienvenida Mamás",
        "subject": "{{nombre}}, te damos la bienvenida a HotBoat 🌊",
        "preview": "Nos alegra tenerte aquí. Descubre lo que tenemos preparado para ti.",
        "segment": "Mamás",
        "html": """<div style="font-family:Inter,Arial,sans-serif;max-width:600px;margin:0 auto;padding:40px 32px;">
  <div style="background:#f9fafb;border-radius:16px;padding:40px;text-align:center;margin-bottom:32px;border:1px solid #e5e7eb;">
    <img src="__LOGO_PNG__" alt="HotBoat" style="height:80px;width:auto;margin-bottom:20px;display:block;margin-left:auto;margin-right:auto;" />
    <h1 style="color:#111;font-size:20px;font-weight:700;margin:0 0 8px;">¡Hola, {{nombre or 'cliente'}}! 🌸</h1>
    <p style="color:#555;font-size:16px;margin:0;">Nos alegra tenerte en la familia HotBoat</p>
  </div>
  <p style="font-size:16px;color:#333;line-height:1.7;">En HotBoat creamos experiencias únicas en el agua para que disfrutes momentos inolvidables junto a las personas que más quieres.</p>
  <div style="background:#f9fafb;border-radius:12px;padding:24px;margin:24px 0;">
    <h3 style="font-size:14px;font-weight:700;color:#111;margin:0 0 14px;text-transform:uppercase;letter-spacing:0.5px;">¿Qué encontrarás en HotBoat?</h3>
    <ul style="margin:0;padding:0 0 0 20px;color:#444;font-size:15px;line-height:2.2;">
      <li>Paseos en bote guiados por expertos</li>
      <li>Experiencias a medida para cada ocasión</li>
      <li>Fotos y recuerdos para llevar siempre</li>
      <li>El lago más hermoso de Chile</li>
    </ul>
  </div>
  <div style="text-align:center;margin:32px 0;">
    <a href="https://hotboat.cl" style="background:#2563eb;color:#fff;font-weight:700;padding:14px 36px;border-radius:10px;text-decoration:none;font-size:15px;">Conocer HotBoat</a>
  </div>
  <p style="font-size:14px;color:#666;text-align:center;">Pronto recibirás algo muy especial por el Día de la Madre. ¡Estáte atenta! 🌸</p>""" + FOOTER + "</div>",
    },
    {
        "name":    "Día de la Madre — Oferta especial",
        "subject": "{{nombre}}, tu regalo de Día de la Madre está aquí 🌸",
        "preview": "Video profesional gratis + jugo natural 1L. Solo para ti, con el cupón MAMÁ.",
        "segment": "Mamás",
        "html": """<div style="font-family:Inter,Arial,sans-serif;max-width:600px;margin:0 auto;padding:40px 32px;">
  <div style="background:#fdf2f8;border-radius:16px;padding:40px;text-align:center;margin-bottom:32px;border:1px solid #f9c6e0;">
    <img src="__LOGO_PNG__" alt="HotBoat" style="height:80px;width:auto;margin-bottom:20px;display:block;margin-left:auto;margin-right:auto;" />
    <h1 style="color:#111;font-size:20px;font-weight:700;margin:0 0 8px;">Feliz Día de la Madre 🌸</h1>
    <p style="color:#555;font-size:16px;margin:0;">{{nombre or 'cliente'}}, este día es tuyo. Te lo merecés todo.</p>
  </div>
  <p style="font-size:16px;color:#333;line-height:1.7;text-align:center;">Para celebrarte, preparamos un regalo especial cuando reserves tu experiencia HotBoat:</p>
  <div style="display:flex;gap:16px;margin:28px 0;flex-wrap:wrap;">
    <div style="flex:1;min-width:220px;background:#fff8f0;border:1px solid #ffd6a0;border-radius:12px;padding:20px;text-align:center;">
      <div style="font-size:40px;margin-bottom:8px;">🎬</div>
      <p style="font-weight:700;color:#111;font-size:15px;margin:0 0 4px;">Video profesional</p>
      <p style="color:#888;font-size:13px;margin:0;">Tu experiencia filmada en HD — <strong style="color:#2563eb;">¡GRATIS!</strong></p>
    </div>
    <div style="flex:1;min-width:220px;background:#f0fff4;border:1px solid #a0f0b8;border-radius:12px;padding:20px;text-align:center;">
      <div style="font-size:40px;margin-bottom:8px;">🥤</div>
      <p style="font-weight:700;color:#111;font-size:15px;margin:0 0 4px;">Jugo natural 1 litro</p>
      <p style="color:#888;font-size:13px;margin:0;">Fresco y recién hecho — <strong style="color:#16a34a;">¡GRATIS!</strong></p>
    </div>
  </div>
  <div style="background:#f9fafb;border-radius:16px;padding:28px;text-align:center;margin:28px 0;">
    <p style="font-size:14px;color:#555;margin:0 0 12px;">Ingresa este cupón al reservar:</p>
    <div style="display:inline-block;background:#2563eb;color:#fff;border-radius:12px;padding:16px 40px;">
      <div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:2px;opacity:0.85;margin-bottom:4px;">Código de reserva</div>
      <div style="font-size:42px;font-weight:900;letter-spacing:4px;line-height:1.1;">MAMÁ</div>
    </div>
    <p style="font-size:12px;color:#999;margin-top:12px;">Válido hasta el 11 de mayo de 2026</p>
  </div>
  <div style="text-align:center;margin:32px 0 16px;">
    <a href="https://whatsapp.hotboat.cl/booking" style="background:#2563eb;color:#fff;font-weight:800;padding:16px 44px;border-radius:12px;text-decoration:none;font-size:16px;display:inline-block;">Reservar ahora 🌊</a>
  </div>
  <p style="text-align:center;font-size:14px;color:#888;margin:0;">¿Quieres saber más? <a href="https://hotboat.cl" style="color:#2563eb;font-weight:600;text-decoration:none;">Ver toda la experiencia</a></p>""" + FOOTER + "</div>",
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

    logo_url = "https://hotboatchile.com/logo_hotboat_blanco.png"

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
        html = t["html"].replace("__LOGO_PNG__", logo_url).replace("__CROSS_SELL__", CROSS_SELL_TEMPLATE_HTML)
        if existing_tpl:
            existing_tpl.html_content    = html
            existing_tpl.subject_default = t["subject"]
            existing_tpl.preview_text    = t["preview"]
            existing_tpl.updated_at      = now
            session.add(existing_tpl)
            tpl_id = existing_tpl.id
            updated["templates"].append(t["name"])
        else:
            tpl = Template(name=t["name"], subject_default=t["subject"], preview_text=t["preview"],
                           html_content=html, created_by=current_user.id,
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
    """Replace SVG hotboatchile.com logo with hosted PNG in all templates."""
    logo_url = "https://hotboatchile.com/logo_hotboat_blanco.png"
    old_pattern = re.compile(r'https?://hotboatchile\.com/LOGO_HOTBOAT\.svg')
    now = datetime.utcnow()
    all_templates = session.exec(select(Template)).all()
    fixed = []
    for tpl in all_templates:
        new_html = old_pattern.sub(logo_url, tpl.html_content or "")
        if new_html != tpl.html_content:
            tpl.html_content = new_html
            tpl.updated_at = now
            session.add(tpl)
            fixed.append(tpl.name)
    session.commit()
    return {"ok": True, "fixed": fixed, "logo_url": logo_url}


@router.post("/sync-products")
def sync_shopify_products(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    """Sync all Shopify products to local shopify_products table (tags, type, image, price)."""
    import re as _re
    from app.core.config import settings as _s
    token = _s.SHOPIFY_ACCESS_TOKEN
    domain = _s.SHOPIFY_DOMAIN
    if not token:
        return {"ok": False, "error": "SHOPIFY_ACCESS_TOKEN not configured"}

    headers = {"X-Shopify-Access-Token": token}
    all_products: list[dict] = []
    url = f"https://{domain}/admin/api/2024-01/products.json"
    params: dict = {
        "limit": 250,
        "fields": "id,title,handle,product_type,tags,vendor,images,variants,status",
    }

    with httpx.Client(timeout=30.0) as client:
        while True:
            r = client.get(url, params=params, headers=headers)
            if r.status_code != 200:
                return {"ok": False, "error": f"Shopify API {r.status_code}: {r.text[:200]}"}
            products = r.json().get("products", [])
            all_products.extend(products)
            link_header = r.headers.get("Link", "")
            if 'rel="next"' not in link_header:
                break
            # Extract next page_info from Link header
            next_part = [p for p in link_header.split(",") if 'rel="next"' in p]
            m = _re.search(r'page_info=([^&>]+)', next_part[0]) if next_part else None
            if not m:
                break
            params = {"limit": 250, "page_info": m.group(1)}

    now = datetime.utcnow()
    upserted = 0
    for p in all_products:
        try:
            variant = (p.get("variants") or [{}])[0]
            price = float(variant.get("price") or 0)
            image_url = (p.get("images") or [{}])[0].get("src", "")
            session.execute(text("""
                INSERT INTO shopify_products
                    (shopify_id, title, handle, product_type, tags, vendor, image_url, price, status, synced_at)
                VALUES
                    (:sid, :title, :handle, :ptype, :tags, :vendor, :img, :price, :status, :now)
                ON CONFLICT (shopify_id) DO UPDATE SET
                    title        = EXCLUDED.title,
                    handle       = EXCLUDED.handle,
                    product_type = EXCLUDED.product_type,
                    tags         = EXCLUDED.tags,
                    vendor       = EXCLUDED.vendor,
                    image_url    = EXCLUDED.image_url,
                    price        = EXCLUDED.price,
                    status       = EXCLUDED.status,
                    synced_at    = EXCLUDED.synced_at
            """), {
                "sid":    int(p["id"]),
                "title":  p.get("title", ""),
                "handle": p.get("handle", ""),
                "ptype":  p.get("product_type", ""),
                "tags":   p.get("tags", ""),
                "vendor": p.get("vendor", ""),
                "img":    image_url,
                "price":  price,
                "status": p.get("status", "active"),
                "now":    now,
            })
            upserted += 1
        except Exception:
            pass

    session.commit()
    return {"ok": True, "synced": upserted, "total_fetched": len(all_products)}


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
