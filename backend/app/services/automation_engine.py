"""
Automation engine — runs every 60 seconds in a background thread.

Two-phase processing:
  Phase 1 (trigger detection): each handler detects qualifying events and creates
  AutomationEnrollment records. No emails sent here.
  Phase 2 (enrollment processing): _process_enrollments() sends emails for any
  enrollment whose next_send_at has passed, then advances to the next step or
  marks as completed/converted.
"""
import json
import logging
import random
import threading
import time
from datetime import datetime, timedelta

import httpx
import resend
from jinja2 import Environment, ChainableUndefined
from sqlalchemy import text
from sqlmodel import Session, select

from app.core.config import settings
from app.services.sync_shopify_orders import sync_contacts_from_shopify_orders
from app.database import engine as db_engine
from app.models.automation import Automation, AutomationEnrollment, AutomationRun
from app.models.campaign import Campaign, CampaignSend
from app.models.contact import Contact
from app.models.segment import Segment
from app.models.template import Template
from app.services.email_sender import _inject_footer, _unsub_headers, send_campaign_sync, _fmt_nombre
from app.core.unsub_token import unsub_url
from app.services.segment_evaluator import evaluate_segment

logger = logging.getLogger(__name__)


def _get_steps(auto: Automation) -> list:
    """Return the steps list for an automation, handling legacy single-step automations."""
    if auto.steps:
        return auto.steps
    # Backwards compat: convert legacy top-level template_id/subject to a single step
    if auto.template_id and auto.subject:
        config = auto.trigger_config or {}
        delay = float(config.get("delay_hours", 0))
        return [{"step": 1, "delay_hours": delay, "template_id": auto.template_id, "subject": auto.subject, "condition": None}]
    return []


def _already_sent_step(session: Session, automation_id: int, trigger_key: str, step_number: int) -> bool:
    """Check if a specific step was already successfully sent for this trigger_key."""
    return session.exec(
        select(AutomationRun).where(
            AutomationRun.automation_id == automation_id,
            AutomationRun.trigger_key == trigger_key,
            AutomationRun.step_number == step_number,
            AutomationRun.status == "sent",
        )
    ).first() is not None


def _enroll(
    session: Session,
    auto: Automation,
    contact_email: str,
    trigger_key: str,
    first_step_delay_hours: float,
    extra_vars: dict | None = None,
) -> bool:
    """Create an enrollment for a contact. Returns False if already enrolled."""
    existing = session.exec(
        select(AutomationEnrollment).where(
            AutomationEnrollment.automation_id == auto.id,
            AutomationEnrollment.trigger_key == trigger_key,
        )
    ).first()
    if existing:
        return False

    enrollment = AutomationEnrollment(
        automation_id=auto.id,
        contact_email=contact_email.lower(),
        trigger_key=trigger_key,
        enrolled_at=datetime.utcnow(),
        next_send_at=datetime.utcnow() + timedelta(hours=first_step_delay_hours),
        next_step=1,
        status="active",
        extra_vars_json=json.dumps(extra_vars or {}),
    )
    session.add(enrollment)
    session.commit()
    return True


def _normalize_city(city: str) -> str:
    """Lowercase + strip accents for fuzzy city matching."""
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", city.lower().strip())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _resolve_location_delay(city: str, rules: list, default_delay: float) -> float:
    """Return the delay_hours for a shipping city based on location_delay_rules.

    Rules are evaluated in order. The first matching non-default rule wins.
    If no rule matches, the rule marked is_default is used; if none, default_delay.
    """
    if not rules:
        return default_delay
    city_norm = _normalize_city(city) if city else ""
    for rule in rules:
        if rule.get("is_default"):
            continue
        cities_norm = [_normalize_city(c) for c in rule.get("cities", [])]
        if city_norm and city_norm in cities_norm:
            return float(rule.get("delay_hours", default_delay))
    # Fall back to default rule
    for rule in rules:
        if rule.get("is_default"):
            return float(rule.get("delay_hours", default_delay))
    return default_delay


def _passes_order_count_filter(filter_cfg: dict | None, orders_count: int) -> bool:
    """Return True if the contact's order count passes the configured filter.

    operators: eq, lt, lte, gt, gte
    value: integer (Shopify orders_count includes the current order for placed_order events)
    """
    if not filter_cfg:
        return True
    op = filter_cfg.get("operator", "eq")
    val = int(filter_cfg.get("value", 1))
    if op == "eq":  return orders_count == val
    if op == "lt":  return orders_count < val
    if op == "lte": return orders_count <= val
    if op == "gt":  return orders_count > val
    if op == "gte": return orders_count >= val
    return True


def _passes_numeric_filter(filter_cfg: dict | None, value: float | int | None) -> bool:
    """Generic numeric filter (operators: eq, lt, lte, gt, gte). Used for total_spent, ticket_medio, etc."""
    if not filter_cfg:
        return True
    if value is None:
        return False
    op  = filter_cfg.get("operator", "gte")
    val = float(filter_cfg.get("value", 0))
    v   = float(value)
    if op == "eq":  return v == val
    if op == "lt":  return v < val
    if op == "lte": return v <= val
    if op == "gt":  return v > val
    if op == "gte": return v >= val
    return True


def _normalize_str(s: str) -> str:
    """Lowercase + strip accents for fuzzy matching."""
    import unicodedata
    return "".join(
        c for c in unicodedata.normalize("NFKD", (s or "").lower().strip())
        if not unicodedata.combining(c)
    )


def _passes_contact_filters(config: dict, contact: "Contact") -> bool:
    """
    Evaluate all extra contact-level filters from trigger_config.

    Supported keys in config:
      total_spent_filter:    { operator, value }   — total spent in CLP
      ticket_medio_filter:   { operator, value }   — avg ticket in CLP
      city_filter:           [str, ...]             — shipping_city whitelist (fuzzy)
      province_filter:       [str, ...]             — shipping_province whitelist (fuzzy)
      accepts_marketing:     true | false           — marketing consent
    """
    if not config:
        return True

    if not _passes_numeric_filter(config.get("total_spent_filter"), contact.total_spent):
        return False

    if not _passes_numeric_filter(config.get("ticket_medio_filter"), contact.ticket_medio):
        return False

    city_filter = config.get("city_filter")
    if city_filter:
        contact_city = _normalize_str(contact.shipping_city or "")
        allowed = [_normalize_str(c) for c in city_filter]
        if contact_city not in allowed:
            return False

    province_filter = config.get("province_filter")
    if province_filter:
        contact_prov = _normalize_str(contact.shipping_province or "")
        allowed = [_normalize_str(p) for p in province_filter]
        if contact_prov not in allowed:
            return False

    accepts_marketing = config.get("accepts_marketing")
    if accepts_marketing is not None:
        if bool(contact.accepts_marketing) != bool(accepts_marketing):
            return False

    return True


def _passes_condition(condition: str | None, enrollment: AutomationEnrollment, session: Session) -> bool:
    """Check enrollment condition before sending a step. Returns True if the step should be sent."""
    if not condition or condition == "always":
        return True

    if condition == "not_purchased":
        # Skip if the contact made a purchase after enrollment
        result = session.execute(text("""
            SELECT 1 FROM shopify_orders
            WHERE LOWER(email) = LOWER(:email)
              AND created_at >= :since
            LIMIT 1
        """), {"email": enrollment.contact_email, "since": enrollment.enrolled_at}).fetchone()
        return result is None  # True = no purchase = still send

    if condition == "not_recovered":
        # For cart abandonment: skip if cart was recovered (purchased)
        extra = json.loads(enrollment.extra_vars_json or "{}")
        checkout_token = enrollment.trigger_key.replace("abandoned_cart:", "")
        result = session.execute(text("""
            SELECT 1 FROM carritos_abandonados
            WHERE checkout_token = :token AND recovered = TRUE
            LIMIT 1
        """), {"token": checkout_token}).fetchone()
        return result is None  # True = not recovered = still send

    return True


def _pick_variant(step: dict) -> tuple[dict, str | None]:
    """If the step has A/B variants, randomly pick one by weight. Returns (effective_step, variant_label)."""
    variants = step.get("variants")
    if not variants or len(variants) < 2:
        return step, None
    total_weight = sum(float(v.get("weight", 1)) for v in variants)
    rand = random.uniform(0, total_weight)
    cumulative = 0.0
    for v in variants:
        cumulative += float(v.get("weight", 1))
        if rand <= cumulative:
            return {**step, "template_id": v["template_id"], "subject": v["subject"]}, str(v["variant"])
    last = variants[-1]
    return {**step, "template_id": last["template_id"], "subject": last["subject"]}, str(last["variant"])


def _fetch_cross_sell_products(
    collection_id: str | None,
    product_ids: list[str],
    exclude_ids: set[str],
    max_products: int = 4,
) -> list[dict]:
    """Fetch recommended products from Shopify for cross-sell; excludes purchased products."""
    token = settings.SHOPIFY_ACCESS_TOKEN
    domain = settings.SHOPIFY_DOMAIN
    if not token:
        return []
    headers = {"X-Shopify-Access-Token": token}
    raw: list[dict] = []
    try:
        with httpx.Client(timeout=8.0) as client:
            if collection_id:
                r = client.get(
                    f"https://{domain}/admin/api/2024-01/collections/{collection_id}/products.json",
                    params={"limit": max_products + len(exclude_ids) + 5, "fields": "id,title,handle,images,variants,status"},
                    headers=headers,
                )
                if r.status_code == 200:
                    raw = r.json().get("products", [])
            elif product_ids:
                r = client.get(
                    f"https://{domain}/admin/api/2024-01/products.json",
                    params={"ids": ",".join(product_ids), "fields": "id,title,handle,images,variants,status"},
                    headers=headers,
                )
                if r.status_code == 200:
                    raw = r.json().get("products", [])
    except Exception as exc:
        logger.warning("cross_sell: product fetch failed: %s", exc)
        return []

    result = []
    for p in raw:
        if p.get("status", "active") != "active":
            continue
        if str(p.get("id", "")) in exclude_ids:
            continue
        variant = (p.get("variants") or [{}])[0]
        try:
            price_fmt = f"${int(float(variant.get('price', 0))):,}".replace(",", ".")
        except Exception:
            price_fmt = ""
        result.append({
            "title": p.get("title", ""),
            "url": f"https://www.happylapiz.cl/products/{p.get('handle', '')}",
            "image_url": (p.get("images") or [{}])[0].get("src", ""),
            "price": price_fmt,
        })
        if len(result) >= max_products:
            break
    return result


def _fetch_cross_sell_from_db(
    session: Session,
    customer_email: str,
    purchased_product_ids: list[str],
    max_products: int = 4,
) -> list[dict]:
    """DB-based cross-sell: match active products by shared tags/type, exclude customer's history."""
    ids_int = [int(p) for p in purchased_product_ids if p.isdigit()]
    if not ids_int:
        return []

    # Tags and product_type of the purchased products
    tag_rows = session.execute(text("""
        SELECT tags, product_type FROM shopify_products
        WHERE shopify_id = ANY(:ids) AND status = 'active'
    """), {"ids": ids_int}).fetchall()

    if not tag_rows:
        return []

    all_tags: set[str] = set()
    product_types: set[str] = set()
    for row in tag_rows:
        if row[0]:
            for t in row[0].split(","):
                s = t.strip().lower()
                if s:
                    all_tags.add(s)
        if row[1]:
            product_types.add(row[1].strip().lower())

    # All product IDs ever purchased by this customer (from order webhook payloads)
    history_rows = session.execute(text("""
        SELECT payload FROM shopify_events
        WHERE LOWER(email) = LOWER(:email)
          AND event_type = 'placed_order'
          AND payload IS NOT NULL
    """), {"email": customer_email}).fetchall()

    ever_bought: set[str] = set(str(p) for p in purchased_product_ids)
    for row in history_rows:
        try:
            payload_data = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            for item in payload_data.get("line_items", []):
                pid = str(item.get("product_id", ""))
                if pid:
                    ever_bought.add(pid)
        except Exception:
            pass

    excl_ints = [int(p) for p in ever_bought if p.isdigit()]

    if not all_tags and not product_types:
        return []

    params: dict = {"max_n": max_products}
    match_parts: list[str] = []
    for i, tag in enumerate(sorted(all_tags)):
        match_parts.append(f"LOWER(tags) LIKE :t{i}")
        params[f"t{i}"] = f"%{tag}%"
    for i, pt in enumerate(sorted(product_types)):
        match_parts.append(f"LOWER(product_type) = :pt{i}")
        params[f"pt{i}"] = pt

    match_clause = " OR ".join(match_parts)
    excl_clause = "AND shopify_id != ALL(:excl)" if excl_ints else ""
    if excl_ints:
        params["excl"] = excl_ints

    try:
        rows = session.execute(text(f"""
            SELECT shopify_id, title, handle, image_url, price
            FROM shopify_products
            WHERE status = 'active'
              {excl_clause}
              AND ({match_clause})
            ORDER BY RANDOM()
            LIMIT :max_n
        """), params).fetchall()
    except Exception as exc:
        logger.warning("cross_sell_db: query failed: %s", exc)
        return []

    result = []
    for row in rows:
        _, title, handle, image_url, price = row
        try:
            price_fmt = f"${int(float(price or 0)):,}".replace(",", ".")
        except Exception:
            price_fmt = ""
        result.append({
            "title": title or "",
            "url": f"https://www.happylapiz.cl/products/{handle or ''}",
            "image_url": image_url or "",
            "price": price_fmt,
        })
    return result


def _get_purchase_history_items(session: Session, customer_email: str) -> list[dict]:
    """Returns all unique products the customer has ever bought, from shopify_events payloads."""
    rows = session.execute(text("""
        SELECT payload FROM shopify_events
        WHERE LOWER(email) = LOWER(:email)
          AND event_type = 'placed_order'
          AND payload IS NOT NULL
        ORDER BY created_at DESC
    """), {"email": customer_email}).fetchall()

    seen: set[str] = set()
    items: list[dict] = []
    for row in rows:
        try:
            payload = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            for item in payload.get("line_items", []):
                pid = str(item.get("product_id", ""))
                if pid and pid not in seen:
                    seen.add(pid)
                    items.append({
                        "product_id": pid,
                        "title": item.get("title") or item.get("name") or "",
                        "price": item.get("price") or "",
                        "variant_title": item.get("variant_title") or "",
                        "image_url": (item.get("properties") or [{}])[0].get("value") if item.get("properties") else "",
                    })
        except Exception:
            pass
    return items


def _build_products_list_html(items: list[dict]) -> str:
    """Builds a clean HTML list of purchased products."""
    if not items:
        return ""
    parts = ["<ul style='padding:0;margin:0;list-style:none;'>"]
    for item in items:
        title   = item.get("title", "")
        variant = item.get("variant_title", "")
        price   = item.get("price", "")
        label   = f"{title} — {variant}" if variant and variant.lower() != "default title" else title
        try:
            price_str = f" <span style='color:#6b7280;font-size:13px;'>${int(float(price)):,}</span>".replace(",", ".")
        except (ValueError, TypeError):
            price_str = ""
        parts.append(
            f"<li style='padding:8px 0;border-bottom:1px solid #f3f4f6;"
            f"font-size:14px;color:#111;line-height:1.4;'>"
            f"{label}{price_str}</li>"
        )
    parts.append("</ul>")
    return "".join(parts)


def _age_matches(edad_rec: str, age: int) -> bool:
    """Check if an edad_recomendada string (e.g. '3-5', '6+', '4') contains the given age."""
    s = edad_rec.strip()
    if "-" in s:
        lo_s, hi_s = s.split("-", 1)
        try:
            return int(lo_s) <= age <= int(hi_s)
        except ValueError:
            return False
    if s.endswith("+"):
        try:
            return age >= int(s[:-1])
        except ValueError:
            return False
    try:
        return int(s) == age
    except ValueError:
        return False


def _fetch_age_recommended_products(
    session: Session,
    customer_email: str,
    edad_regalon: int,
    max_products: int = 4,
) -> list[dict]:
    """Returns active products whose edad_recomendada matches the gift age, excluding already bought."""
    history_rows = session.execute(text("""
        SELECT payload FROM shopify_events
        WHERE LOWER(email) = LOWER(:email)
          AND event_type = 'placed_order'
          AND payload IS NOT NULL
    """), {"email": customer_email}).fetchall()

    ever_bought: set[int] = set()
    for row in history_rows:
        try:
            payload = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            for item in payload.get("line_items", []):
                pid = item.get("product_id")
                if pid:
                    ever_bought.add(int(pid))
        except Exception:
            pass

    excl_clause = "AND shopify_id != ALL(:excl)" if ever_bought else ""
    params: dict = {}
    if ever_bought:
        params["excl"] = list(ever_bought)

    try:
        all_rows = session.execute(text(f"""
            SELECT shopify_id, title, handle, image_url, price, edad_recomendada
            FROM shopify_products
            WHERE status = 'active'
              AND edad_recomendada IS NOT NULL
              AND edad_recomendada <> ''
              {excl_clause}
        """), params).fetchall()
    except Exception as exc:
        logger.warning("age_recommended: query failed: %s", exc)
        return []

    matched = [
        {
            "shopify_id": r[0],
            "title": r[1],
            "handle": r[2],
            "image_url": r[3],
            "price": float(r[4]) if r[4] else 0,
        }
        for r in all_rows
        if _age_matches(r[5] or "", edad_regalon)
    ]

    import random
    random.shuffle(matched)
    return matched[:max_products]


def _trunc_title(title: str, max_chars: int = 55) -> str:
    """Truncate product title to max_chars chars at a word boundary."""
    if len(title) <= max_chars:
        return title
    return title[:max_chars].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def _build_cross_sell_html(products: list[dict], btn_color: str = "#f97316") -> str:
    """Generate a 2-column responsive product grid for cross-sell emails."""
    if not products:
        return ""
    rows_html = ""
    for i in range(0, len(products), 2):
        pair = products[i:i+2]
        cells = ""
        for p in pair:
            title = _trunc_title(p["title"])
            safe_title = title.replace("'", "&#39;").replace('"', '&quot;')
            img = (
                f'<img src="{p["image_url"]}" alt="{safe_title}" width="200" '
                f'style="width:100%;max-width:200px;height:auto;border-radius:10px;'
                f'display:block;margin:0 auto 12px;" />'
            ) if p.get("image_url") else ""
            cells += (
                f'<td width="50%" style="width:50%;padding:12px 8px;vertical-align:top;text-align:center;">'
                f'<a href="{p["url"]}" style="text-decoration:none;color:#1a1a1a;display:block;">'
                f'{img}'
                f'<p style="font-size:14px;font-weight:600;margin:0 0 5px;line-height:1.3;'
                f'max-height:3.9em;overflow:hidden;">{title}</p>'
                f'<p style="font-size:15px;color:#e85d04;font-weight:700;margin:0 0 12px;">{p["price"]}</p>'
                f'<span style="display:inline-block;background:{btn_color};color:#fff;font-size:12px;'
                f'font-weight:600;padding:7px 18px;border-radius:20px;text-decoration:none;">Ver producto &rarr;</span>'
                f'</a></td>'
            )
        if len(pair) == 1:
            cells += '<td width="50%" style="width:50%;"></td>'
        rows_html += f"<tr>{cells}</tr>"
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="border-collapse:collapse;max-width:560px;margin:0 auto;">'
        f"<tbody>{rows_html}</tbody></table>"
    )


def _send_email_step(
    session: Session,
    auto: Automation,
    contact: Contact,
    trigger_key: str,
    step: dict,
    step_number: int,
    extra_vars: dict | None = None,
    variant: str | None = None,
) -> None:
    """Send the email for a specific step and record the run."""
    tpl = session.get(Template, int(step["template_id"]))
    if not tpl:
        logger.warning("Automation %d step %d: template %d not found", auto.id, step_number, step["template_id"])
        return

    run = AutomationRun(
        automation_id=auto.id,
        contact_id=contact.id,
        contact_email=contact.email,
        trigger_key=trigger_key,
        step_number=step_number,
        triggered_at=datetime.utcnow(),
        status="failed",
        variant_sent=variant,
    )
    try:
        # Generate dynamic coupon if automation has one configured
        coupon_code: str | None = None
        if auto.coupon_campaign_id:
            try:
                from app.routers.forms import _generate_dynamic_coupon
                coupon_code = _generate_dynamic_coupon(session, auto.coupon_campaign_id, contact.email)
            except Exception as exc:
                logger.warning("Coupon generation failed for %s: %s", contact.email, exc)

        nombre = _fmt_nombre(contact.name, contact.email)
        first_name = nombre.split()[0] if contact.name else ""
        cf = contact.custom_fields or {}
        if isinstance(cf, str):
            try:
                cf = json.loads(cf)
            except Exception:
                cf = {}
        vars_ = {
            "nombre": nombre,
            "first_name": first_name,
            "email": contact.email,
            "orders_count": contact.orders_count or 0,
            "ultima_visita": str(contact.ultima_visita) if contact.ultima_visita else "",
            "ticket_medio": contact.ticket_medio or 0,
            "total_spent": contact.total_spent or 0,
            "shipping_city": contact.shipping_city or "",
            "shipping_province": contact.shipping_province or "",
            "coupon_code": coupon_code or "",
            "custom_fields": cf,
            # Spread custom_fields at top level so {{ nombre_regalado }} works directly
            **{k: v for k, v in cf.items() if isinstance(k, str)},
            **(extra_vars or {}),
        }
        # If there's a coupon code and a checkout URL, inject checkout_url_with_coupon
        # so templates can use {{ event.extra.checkout_url_with_coupon }} to get the
        # checkout URL with the discount pre-applied (Shopify supports ?discount=CODE).
        if coupon_code:
            event_extra = vars_.get("event", {}).get("extra", {})
            raw_url = event_extra.get("checkout_url", "")
            if raw_url:
                sep = "&" if "?" in raw_url else "?"
                event_extra["checkout_url_with_coupon"] = f"{raw_url}{sep}discount={coupon_code}"
        # Inject cross-sell product grid if configured
        cross_sell_cfg = (auto.trigger_config or {}).get("cross_sell_config") if auto.trigger_config else None
        if cross_sell_cfg:
            purchased_ids = [str(p) for p in (vars_.get("purchased_product_ids") or [])]
            max_p = int(cross_sell_cfg.get("max_products", 4))
            mode = cross_sell_cfg.get("mode", "db")
            has_explicit = bool(cross_sell_cfg.get("collection_id") or cross_sell_cfg.get("product_ids"))
            if mode == "db" or not has_explicit:
                # Use DB-based matching (tags + product_type + exclude purchase history)
                rec = _fetch_cross_sell_from_db(
                    session=session,
                    customer_email=contact.email,
                    purchased_product_ids=purchased_ids,
                    max_products=max_p,
                )
            else:
                rec = _fetch_cross_sell_products(
                    collection_id=cross_sell_cfg.get("collection_id") or None,
                    product_ids=[str(p) for p in (cross_sell_cfg.get("product_ids") or [])],
                    exclude_ids=set(purchased_ids),
                    max_products=max_p,
                )
            vars_["recommended_products"] = rec
            # Get btn_color from template json_blocks if available
            _cs_btn = "#f97316"
            try:
                _blks = json.loads(tpl.json_blocks) if isinstance(tpl.json_blocks, str) else (tpl.json_blocks or [])
                for _b in (_blks if isinstance(_blks, list) else []):
                    if _b.get("type") == "product_grid" and _b.get("props", {}).get("btn_color"):
                        _cs_btn = _b["props"]["btn_color"]; break
            except Exception:
                pass
            vars_["recommended_products_html"] = _build_cross_sell_html(rec, _cs_btn)

        # Purchase history variables (always available, derived from shopify_events)
        orders_count_val = contact.orders_count or 0
        history_items = _get_purchase_history_items(session, contact.email) if orders_count_val >= 1 else []
        if orders_count_val == 1 and history_items:
            vars_["producto_comprado_html"] = _build_products_list_html(history_items[:1])
            vars_["producto_comprado"] = history_items[0].get("title", "")
        elif orders_count_val > 1 and history_items:
            vars_["productos_comprados_html"] = _build_products_list_html(history_items)
            vars_["primer_producto_comprado"] = history_items[0].get("title", "")

        # Age-based product recommendations (uses custom_fields.edad_regalon OR fecha_nacimiento from form)
        edad_regalon_raw = cf.get("edad_regalon") or (extra_vars or {}).get("edad_regalon")
        if edad_regalon_raw is None:
            # Calculate age from date of birth if provided (form_submitted trigger)
            dob_str = (extra_vars or {}).get("cual_es_su_fecha_de_nacimiento") or cf.get("cual_es_su_fecha_de_nacimiento")
            if dob_str:
                try:
                    from datetime import date as _date
                    dob = _date.fromisoformat(str(dob_str))
                    today = _date.today()
                    edad_regalon_raw = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                except Exception:
                    pass
        if edad_regalon_raw is not None:
            try:
                edad_int = int(edad_regalon_raw)
                # Get btn_color from template json_blocks if available
                btn_color = "#f97316"
                try:
                    blocks = json.loads(tpl.json_blocks) if isinstance(tpl.json_blocks, str) else (tpl.json_blocks or [])
                    for blk in (blocks if isinstance(blocks, list) else []):
                        props = blk.get("props", {})
                        if blk.get("type") == "product_grid" and props.get("btn_color"):
                            btn_color = props["btn_color"]
                            break
                except Exception:
                    pass
                age_rec = _fetch_age_recommended_products(session, contact.email, edad_int)
                vars_["productos_recomendados_edad"] = age_rec
                vars_["productos_recomendados_edad_html"] = _build_cross_sell_html(age_rec, btn_color)
            except (ValueError, TypeError):
                pass

        _env = Environment(undefined=ChainableUndefined)
        raw_html = tpl.html_content.replace("{% unsubscribe %}", unsub_url(contact.email))
        html = _inject_footer(_env.from_string(raw_html).render(**vars_), contact.email)

        preview_text = step.get("preview_text", "")
        if preview_text:
            preheader = (
                f'<span style="display:none;max-height:0;overflow:hidden;'
                f'font-size:1px;line-height:1px;color:#fff;opacity:0">{preview_text}</span>'
            )
            # Insert right after <body ...> tag so email clients pick it up as preheader
            import re as _re
            html = _re.sub(r"(<body[^>]*>)", r"\1" + preheader, html, count=1) if "<body" in html.lower() else preheader + html

        resend.api_key = settings.RESEND_API_KEY
        result = resend.Emails.send({
            "from": settings.RESEND_FROM_EMAIL,
            "to": [contact.email],
            "subject": _env.from_string(str(step.get("subject", ""))).render(**vars_),
            "html": html,
            "headers": _unsub_headers(contact.email),
        })
        resend_id = result.get("id") if isinstance(result, dict) else getattr(result, "id", None)
        run.status = "sent"
        run.resend_id = resend_id
        run.executed_at = datetime.utcnow()
        logger.info("Automation %d step %d variant=%s sent to %s", auto.id, step_number, variant or "-", contact.email)
    except Exception as exc:
        run.error = str(exc)[:500]
        run.executed_at = datetime.utcnow()
        logger.error("Automation %d step %d failed for %s: %s", auto.id, step_number, contact.email, exc)

    session.add(run)
    session.commit()


# ── Enrollment processing ──────────────────────────────────────────────────────

def _process_enrollments(session: Session) -> None:
    """Phase 2: send emails for all ready enrollments and advance to next step."""
    now = datetime.utcnow()

    ready = session.exec(
        select(AutomationEnrollment)
        .where(AutomationEnrollment.status == "active")
        .where(AutomationEnrollment.next_send_at <= now)
    ).all()

    for enrollment in ready:
        auto = session.get(Automation, enrollment.automation_id)
        if not auto or auto.status != "active":
            enrollment.status = "cancelled"
            session.add(enrollment)
            session.commit()
            continue

        steps = _get_steps(auto)
        step_idx = enrollment.next_step - 1  # 0-indexed

        if step_idx >= len(steps):
            enrollment.status = "completed"
            session.add(enrollment)
            session.commit()
            continue

        step = steps[step_idx]

        # Check condition — if it fails, the contact converted/shouldn't receive
        if not _passes_condition(step.get("condition"), enrollment, session):
            enrollment.status = "converted"
            logger.info("Enrollment %d: condition '%s' failed, marking converted", enrollment.id, step.get("condition"))
            session.add(enrollment)
            session.commit()
            continue

        # Guard against double-send (e.g. if engine ran twice concurrently)
        if _already_sent_step(session, auto.id, enrollment.trigger_key, enrollment.next_step):
            logger.warning("Enrollment %d step %d already sent, advancing", enrollment.id, enrollment.next_step)
        else:
            contact = session.exec(
                select(Contact).where(Contact.email == enrollment.contact_email.lower())
            ).first()
            if not contact:
                extra = json.loads(enrollment.extra_vars_json or "{}")
                contact = Contact(
                    email=enrollment.contact_email,
                    name=extra.get("nombre", enrollment.contact_email),
                    opted_in=True,
                    orders_count=0,
                )

            extra_vars = json.loads(enrollment.extra_vars_json or "{}")
            effective_step, variant_label = _pick_variant(step)
            _send_email_step(session, auto, contact, enrollment.trigger_key, effective_step, enrollment.next_step, extra_vars, variant_label)

        # Advance to next step
        next_step_num = enrollment.next_step + 1
        if next_step_num > len(steps):
            enrollment.status = "completed"
        else:
            next_step = steps[next_step_num - 1]
            delay = float(next_step.get("delay_hours", 24))
            enrollment.next_step = next_step_num
            enrollment.next_send_at = now + timedelta(hours=delay)

        session.add(enrollment)
        session.commit()


# ── Trigger handlers (Phase 1 — enroll only, don't send) ─────────────────────

_BATCH_ORIGINS = {"Formulario T&C", "Sincronización Shopify", "importación CSV", ""}


def _check_welcome(auto: Automation, session: Session) -> None:
    config = auto.trigger_config or {}
    steps = _get_steps(auto)
    if not steps:
        return
    first_delay = float(steps[0].get("delay_hours", float(config.get("delay_hours", 0))))

    delay_hours = float(config.get("delay_hours", 0))
    window_end = datetime.utcnow() - timedelta(hours=delay_hours)
    window_start = window_end - timedelta(minutes=20)

    contacts = session.exec(
        select(Contact).where(
            Contact.created_at >= window_start,
            Contact.created_at <= window_end,
            Contact.opted_in == True,
        )
    ).all()

    order_count_filter = config.get("order_count_filter")
    for contact in contacts:
        origin = (contact.origin_utm or "").strip()
        if origin in _BATCH_ORIGINS or origin.startswith("Formulario #"):
            continue
        if order_count_filter and not _passes_order_count_filter(order_count_filter, contact.orders_count or 0):
            continue
        if not _passes_contact_filters(config, contact):
            continue
        trigger_key = f"welcome:{contact.id}"
        extra_vars = {"nombre": contact.name or contact.email, "first_name": (contact.name or contact.email).split()[0]}
        _enroll(session, auto, contact.email, trigger_key, first_delay, extra_vars)


def _check_post_visit(auto: Automation, session: Session) -> None:
    config = auto.trigger_config or {}
    steps = _get_steps(auto)
    if not steps:
        return
    first_delay = float(steps[0].get("delay_hours", 0))
    delay_days = int(config.get("delay_days", 3))
    target_date = (datetime.utcnow() - timedelta(days=delay_days)).date()

    contacts = session.exec(
        select(Contact).where(
            Contact.ultima_visita == target_date,
            Contact.opted_in == True,
        )
    ).all()

    order_count_filter = config.get("order_count_filter")
    for contact in contacts:
        if order_count_filter and not _passes_order_count_filter(order_count_filter, contact.orders_count or 0):
            continue
        if not _passes_contact_filters(config, contact):
            continue
        trigger_key = f"postvisit:{contact.id}:{target_date}"
        extra_vars = {"nombre": contact.name or contact.email, "first_name": (contact.name or contact.email).split()[0]}
        _enroll(session, auto, contact.email, trigger_key, first_delay, extra_vars)


def _check_reactivation(auto: Automation, session: Session) -> None:
    config = auto.trigger_config or {}
    steps = _get_steps(auto)
    if not steps:
        return
    first_delay = float(steps[0].get("delay_hours", 0))

    inactivity_days = int(config.get("inactivity_days", 90))
    cooldown_days = int(config.get("cooldown_days", 180))
    cutoff_date = (datetime.utcnow() - timedelta(days=inactivity_days)).date()
    cooldown_start = datetime.utcnow() - timedelta(days=cooldown_days)

    contacts = session.exec(
        select(Contact).where(
            Contact.ultima_visita != None,
            Contact.ultima_visita <= cutoff_date,
            Contact.opted_in == True,
        )
    ).all()

    order_count_filter = config.get("order_count_filter")
    for contact in contacts:
        recent_run = session.exec(
            select(AutomationRun).where(
                AutomationRun.automation_id == auto.id,
                AutomationRun.contact_id == contact.id,
                AutomationRun.triggered_at >= cooldown_start,
                AutomationRun.status == "sent",
            )
        ).first()
        if recent_run:
            continue
        if order_count_filter and not _passes_order_count_filter(order_count_filter, contact.orders_count or 0):
            continue
        if not _passes_contact_filters(config, contact):
            continue
        week = datetime.utcnow().strftime("%Y-W%W")
        trigger_key = f"reactivation:{contact.id}:{week}"
        extra_vars = {"nombre": contact.name or contact.email, "first_name": (contact.name or contact.email).split()[0]}
        _enroll(session, auto, contact.email, trigger_key, first_delay, extra_vars)


def _check_abandoned_cart(auto: Automation, session: Session) -> None:
    config = auto.trigger_config or {}
    lookback_hours = float(config.get("lookback_hours", 24))
    now = datetime.utcnow()
    cutoff_recent = now - timedelta(hours=lookback_hours)

    steps = _get_steps(auto)
    if not steps:
        return
    first_delay = float(steps[0].get("delay_hours", float(config.get("delay_hours", 1))))

    rows = session.execute(text("""
        SELECT id, checkout_token, email, first_name, last_name,
               subtotal_price, line_items, checkout_url
        FROM carritos_abandonados
        WHERE recovered = FALSE
          AND abandoned_email_sent = FALSE
          AND email IS NOT NULL AND email <> ''
          AND created_at >= :recent
        ORDER BY created_at ASC
        LIMIT 200
    """), {"recent": cutoff_recent}).fetchall()

    for row in rows:
        email = (row[2] or "").lower().strip()
        if not email:
            continue

        contact = session.exec(select(Contact).where(Contact.email == email)).first()
        if contact and contact.opted_in is False:
            continue

        # Apply order count filter (uses completed orders so far; for abandoned_cart
        # value 0 = nunca ha comprado, 1 = ya compró una vez antes, etc.)
        order_count_filter = config.get("order_count_filter")
        if order_count_filter and contact:
            if not _passes_order_count_filter(order_count_filter, contact.orders_count or 0):
                continue
        if contact and not _passes_contact_filters(config, contact):
            continue

        # Atomically claim the cart to prevent concurrent duplicate enrollments
        claimed = session.execute(text("""
            UPDATE carritos_abandonados
            SET abandoned_email_sent = TRUE
            WHERE id = :id AND abandoned_email_sent = FALSE
        """), {"id": row[0]})
        session.commit()
        if claimed.rowcount == 0:
            continue

        trigger_key = f"abandoned_cart:{row[1]}"
        first_name = (row[3] or "").strip()
        last_name  = (row[4] or "").strip()
        full_name  = f"{first_name} {last_name}".strip() or email
        items = row[6] or []
        first_item = items[0].get("title", "") if items else ""
        subtotal = float(row[5] or 0)
        checkout_url = row[7] or "https://happylapiz.cl/cart"

        extra_vars = {
            "nombre":        full_name,
            "first_name":    first_name or full_name.split()[0],
            "cart_total":    f"${int(subtotal):,}".replace(",", "."),
            "first_product": first_item,
            "cart_url":      checkout_url,
            "event":         {"extra": {"checkout_url": checkout_url}},
        }
        _enroll(session, auto, email, trigger_key, first_delay, extra_vars)


def _check_shopify_event(auto: Automation, session: Session, trigger_type: str) -> None:
    config = auto.trigger_config or {}
    lookback_hours = float(config.get("lookback_hours", 48))
    now = datetime.utcnow()
    cutoff_recent = now - timedelta(hours=lookback_hours)

    steps = _get_steps(auto)
    if not steps:
        return
    first_delay = float(steps[0].get("delay_hours", float(config.get("delay_hours", 0))))

    topic_map = {
        "placed_order":    "orders/create",
        "ordered_product": "orders/create",
        "fulfilled_order": "orders/fulfilled",
        "cancelled_order": "orders/cancelled",
    }
    topic = topic_map.get(trigger_type)
    if not topic:
        return

    # For event-based triggers, only enroll events that haven't been enrolled yet
    rows = session.execute(text("""
        SELECT se.id, se.email, se.payload
        FROM shopify_events se
        WHERE se.topic = :topic
          AND se.processed = FALSE
          AND se.email IS NOT NULL
          AND se.created_at >= :recent
        ORDER BY se.created_at ASC LIMIT 200
    """), {"topic": topic, "recent": cutoff_recent}).fetchall()

    order_count_filter = config.get("order_count_filter")
    location_delay_rules = config.get("location_delay_rules", [])

    for row in rows:
        email = (row[1] or "").lower().strip()
        if not email:
            continue
        contact = session.exec(select(Contact).where(Contact.email == email)).first()
        if not contact or not contact.opted_in:
            continue
        trigger_key = f"{trigger_type}:{row[0]}"
        payload = row[2] or {}

        # Apply order count filter before enrolling.
        # For Shopify order events the payload includes customer.orders_count which
        # already reflects the current order (e.g. 1 for a first-time buyer).
        if order_count_filter:
            cust_count = payload.get("customer", {}).get("orders_count")
            count_to_check = int(cust_count) if cust_count is not None else (contact.orders_count or 0)
            if not _passes_order_count_filter(order_count_filter, count_to_check):
                session.execute(text("UPDATE shopify_events SET processed = TRUE WHERE id = :id"), {"id": row[0]})
                session.commit()
                continue
        if not _passes_contact_filters(config, contact):
            session.execute(text("UPDATE shopify_events SET processed = TRUE WHERE id = :id"), {"id": row[0]})
            session.commit()
            continue

        items = payload.get("line_items", [])

        # Apply product filter for ordered_product trigger
        product_filter_ids = config.get("product_filter_ids", [])
        if product_filter_ids and trigger_type == "ordered_product":
            item_product_ids = {str(item.get("product_id", "")) for item in items}
            filter_ids = {str(p) for p in product_filter_ids}
            if not item_product_ids.intersection(filter_ids):
                session.execute(text("UPDATE shopify_events SET processed = TRUE WHERE id = :id"), {"id": row[0]})
                session.commit()
                continue

        # Resolve delay based on shipping city (overrides the step default when rules exist)
        shipping_city = payload.get("shipping_address", {}).get("city", "")
        effective_delay = _resolve_location_delay(shipping_city, location_delay_rules, first_delay)
        first_item = items[0].get("title", "") if items else ""
        tracking = ""
        if trigger_type == "fulfilled_order":
            for f in payload.get("fulfillments", []):
                tracking = f.get("tracking_number", "") or ""
                break
        extra_vars = {
            "nombre": contact.name or email,
            "first_name": (contact.name or email).split()[0],
            "order_number": str(payload.get("order_number", "")),
            "order_total": f"${int(float(payload.get('total_price', 0))):,}".replace(",", "."),
            "first_product": first_item,
            "tracking_number": tracking,
            "shipping_city": shipping_city,
            "shipping_province": payload.get("shipping_address", {}).get("province", ""),
            "purchased_product_ids": [str(item.get("product_id", "")) for item in items],
        }
        enrolled = _enroll(session, auto, email, trigger_key, effective_delay, extra_vars)
        if enrolled:
            session.execute(text("UPDATE shopify_events SET processed = TRUE WHERE id = :id"), {"id": row[0]})
            session.commit()


def _check_birthday_reminder(auto: Automation, session: Session) -> None:
    """
    Triggers for contacts whose custom_fields contains a child birthday (fecha_nacimiento)
    that falls exactly `days_before` days from today (checked daily).
    Each contact+year combination fires once. custom_fields keys configured via trigger_config:
      days_before: int            — how many days before birthday to send (default 30)
      birthday_field: str         — key inside custom_fields for the date (default "fecha_nacimiento")
      name_field: str             — key inside custom_fields for the child's name (default "nombre_regalado")
      relation_field: str         — key inside custom_fields for relationship (default "relacion")
    """
    config = auto.trigger_config or {}
    days_before = int(config.get("days_before", 30))
    birthday_field = config.get("birthday_field", "fecha_nacimiento")
    name_field = config.get("name_field", "nombre_regalado")
    relation_field = config.get("relation_field", "relacion")

    steps = _get_steps(auto)
    if not steps:
        return
    first_delay = float(steps[0].get("delay_hours", 0))

    today = datetime.utcnow().date()
    target = today + timedelta(days=days_before)  # the birthday date we're looking for
    target_mmdd = f"{target.month:02d}-{target.day:02d}"  # MM-DD, ignoring year

    # Query contacts that have custom_fields with the birthday field set
    rows = session.execute(text("""
        SELECT id, email, name, custom_fields
        FROM contacts
        WHERE opted_in = TRUE
          AND custom_fields IS NOT NULL
          AND custom_fields::text LIKE :pattern
    """), {"pattern": f"%{birthday_field}%"}).fetchall()

    for row in rows:
        cf = row[3] or {}
        if isinstance(cf, str):
            try:
                cf = json.loads(cf)
            except Exception:
                continue

        raw_date = cf.get(birthday_field, "")
        if not raw_date:
            continue

        # Accept YYYY-MM-DD or DD-MM-YYYY or DD/MM/YYYY
        try:
            if len(raw_date) == 10 and raw_date[4] in ("-", "/"):
                # YYYY-MM-DD
                bday = datetime.strptime(raw_date, "%Y-%m-%d").date()
                bday_mmdd = f"{bday.month:02d}-{bday.day:02d}"
            else:
                for fmt in ("%d-%m-%Y", "%d/%m/%Y"):
                    try:
                        bday = datetime.strptime(raw_date, fmt).date()
                        bday_mmdd = f"{bday.month:02d}-{bday.day:02d}"
                        break
                    except ValueError:
                        continue
                else:
                    continue
        except Exception:
            continue

        if bday_mmdd != target_mmdd:
            continue

        child_name = cf.get(name_field, "")
        relation = cf.get(relation_field, "")
        contact_name = row[2] or row[1]
        first = contact_name.split()[0]

        trigger_key = f"birthday:{row[0]}:{target.year}:{days_before}"
        extra_vars = {
            "nombre": contact_name,
            "first_name": first,
            "nombre_regalado": child_name,
            "relacion": relation,
            "dias_para_cumpleanos": days_before,
            "fecha_cumpleanos": str(target),
        }
        _enroll(session, auto, row[1], trigger_key, first_delay, extra_vars)


def _make_shopify_handler(trigger_type: str):
    def handler(auto, session): _check_shopify_event(auto, session, trigger_type)
    handler.__name__ = f"_check_{trigger_type}"
    return handler


HANDLERS = {
    "checkout_started":         _make_shopify_handler("checkout_started"),
    "abandoned_cart":           _check_abandoned_cart,
    "placed_order":             _make_shopify_handler("placed_order"),
    "ordered_product":          _make_shopify_handler("ordered_product"),
    "fulfilled_order":          _make_shopify_handler("fulfilled_order"),
    "fulfilled_partial_order":  _make_shopify_handler("fulfilled_partial_order"),
    "confirmed_shipment":       _make_shopify_handler("confirmed_shipment"),
    "delivered_shipment":       _make_shopify_handler("delivered_shipment"),
    "marked_out_for_delivery":  _make_shopify_handler("marked_out_for_delivery"),
    "cancelled_order":          _make_shopify_handler("cancelled_order"),
    "refunded_order":           _make_shopify_handler("refunded_order"),
    "added_to_cart":            _make_shopify_handler("added_to_cart"),
    "coupon_assigned":          _make_shopify_handler("coupon_assigned"),
    "coupon_used":              _make_shopify_handler("coupon_used"),
    "subscribed_to_back_in_stock": _make_shopify_handler("subscribed_to_back_in_stock"),
    "viewed_product":           _make_shopify_handler("viewed_product"),
    "active_on_site":           _make_shopify_handler("active_on_site"),
    "welcome":                  _check_welcome,
    "post_visit":               _check_post_visit,
    "reactivation":             _check_reactivation,
    "birthday_reminder":        _check_birthday_reminder,
}


def run_scheduled_campaigns() -> None:
    with Session(db_engine) as session:
        now = datetime.utcnow()
        due = session.exec(
            select(Campaign).where(
                Campaign.status == "scheduled",
                Campaign.scheduled_at <= now,
            )
        ).all()
        for campaign in due:
            try:
                seg = session.get(Segment, campaign.segment_id)
                if not seg:
                    continue
                contacts = evaluate_segment(seg.conditions, session)
                if campaign.exclude_segment_ids:
                    excluded_ids: set = set()
                    for excl_id in campaign.exclude_segment_ids:
                        excl_seg = session.get(Segment, excl_id)
                        if excl_seg:
                            excluded_ids.update(ct.id for ct in evaluate_segment(excl_seg.conditions, session))
                    contacts = [ct for ct in contacts if ct.id not in excluded_ids]
                if not contacts:
                    continue
                already_sent = set(session.exec(
                    select(CampaignSend.contact_id).where(
                        CampaignSend.campaign_id == campaign.id,
                        CampaignSend.status != "failed",
                    )
                ).all())
                to_send = [c for c in contacts if c.id not in already_sent]
                if not to_send:
                    campaign.status = "sent"
                    session.add(campaign)
                    session.commit()
                    continue
                campaign.status = "sending"
                session.add(campaign)
                session.commit()
                contact_ids = [c.id for c in to_send]
                send_campaign_sync(campaign.id, contact_ids, len(contacts))
            except Exception as exc:
                logger.exception("Scheduled campaign %d error: %s", campaign.id, exc)


def run_automations() -> None:
    with Session(db_engine) as session:
        automations = session.exec(
            select(Automation).where(Automation.status == "active")
        ).all()
        # Phase 1: detect triggers → enroll
        for auto in automations:
            handler = HANDLERS.get(auto.trigger_type)
            if handler:
                try:
                    handler(auto, session)
                except Exception as exc:
                    logger.exception("Automation %d (%s) trigger error: %s", auto.id, auto.trigger_type, exc)
        # Phase 2: process ready enrollments → send emails
        try:
            _process_enrollments(session)
        except Exception as exc:
            logger.exception("Enrollment processing error: %s", exc)


def start_scheduler() -> None:
    def loop():
        time.sleep(10)
        while True:
            try:
                run_automations()
                run_scheduled_campaigns()
                sync_contacts_from_shopify_orders()
            except Exception as exc:
                logger.exception("Automation scheduler error: %s", exc)
            time.sleep(60)

    t = threading.Thread(target=loop, daemon=True, name="automation-scheduler")
    t.start()
    logger.info("Automation scheduler started (interval: 1 min)")
