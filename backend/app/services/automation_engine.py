"""
Automation engine — background tasks run on staggered intervals via scheduler.py.

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
import time
from datetime import datetime, timedelta

import httpx
import resend
from jinja2 import Environment, ChainableUndefined
from sqlalchemy import text
from sqlmodel import Session, select

from app.core.config import settings
from app.database import engine as db_engine
from app.models.automation import Automation, AutomationEnrollment, AutomationRun
from app.models.campaign import Campaign, CampaignSend
from app.models.contact import Contact
from app.models.segment import Segment
from app.models.template import Template
from app.services.email_sender import _inject_footer, _unsub_headers, send_campaign_batch, _fmt_nombre, replace_unsub_tag, resolve_relative_timers, resume_pending_campaign_sends
from app.core.unsub_token import unsub_url
from app.services.segment_evaluator import evaluate_segment, evaluate_segment_ids

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

    if condition == "has_no_gift_recipients":
        result = session.execute(text(
            "SELECT 1 FROM gift_recipients WHERE LOWER(email) = LOWER(:email) LIMIT 1"
        ), {"email": enrollment.contact_email}).fetchone()
        return result is None  # True = no gift recipients = still send

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
            merged = {**step, "template_id": v["template_id"], "subject": v["subject"]}
            if "preview_text" in v:
                merged["preview_text"] = v["preview_text"]
            return merged, str(v["variant"])
    last = variants[-1]
    merged = {**step, "template_id": last["template_id"], "subject": last["subject"]}
    if "preview_text" in last:
        merged["preview_text"] = last["preview_text"]
    return merged, str(last["variant"])


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
          AND topic = 'orders/create'
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
          AND topic = 'orders/create'
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


_FEMALE_NAMES = {
    'maria','ana','valentina','sofia','isabella','catalina','camila','gabriela','natalia',
    'paula','andrea','carolina','fernanda','alejandra','jessica','daniela','claudia',
    'patricia','veronica','monica','laura','isabel','carmen','rosa','elena','teresa',
    'marcela','viviana','lorena','beatriz','silvia','susana','magdalena','pilar','luz',
    'gloria','alicia','ines','esperanza','mercedes','antonia','cecilia','adriana','liliana',
    'paola','vanessa','priscila','fabiola','macarena','javiera','karla','barbara',
    'constanza','isidora','trinidad','florencia','martina','emilia','renata','antonieta',
    'ximena','francisca','nicole','tamara','pamela','stephanie','karen','sandra','irene',
    'rebeca','rachel','sara','nathaly','nataly','rocio','piedad','yolanda','melanie',
    'victoria','valeria','ignacia','josefina','montserrat','bernardita','violeta',
    'amanda','lisbeth','marisol','miriam','milagros','giuliana','fernanda','lucia',
    'luca',  # exception: luca can be male (handled by first-name list)
}
_MALE_NAMES = {
    'carlos','juan','pedro','jose','luis','miguel','francisco','antonio','manuel',
    'jorge','roberto','sergio','diego','pablo','alvaro','nicolas','andres','cristian',
    'sebastian','alejandro','rodrigo','victor','mario','raul','hector','jaime','gabriel',
    'ignacio','matias','benjamin','tomas','maximiliano','felipe','enrique','david',
    'daniel','renzo','richard','claudio','marcelo','hugo','hernan','patricio','gonzalo',
    'gustavo','ernesto','alfredo','fernando','martin','emilio','leandro','fabian',
    'christian','alberto','alan','alex','alexis','angelo','arturo','augusto','braulio',
    'camilo','cesar','dante','dario','esteban','eugenio','ezequiel','federico','franco',
    'freddy','fredy','gerardo','gilberto','guillermo','ivan','joaquin','jonathan','julian',
    'kevin','lautaro','lazaro','leonardo','lucas','marco','marcos','mauro','maximo',
    'mauricio','nicolas','omar','oscar','oswaldo','rafael','ramon','reinaldo','renato',
    'ricardo','rolando','ruben','samuel','santiago','saul','simon','stefan','tiago',
    'valentin','walter','wilmer','xavier','yerlan','luka',
}

def _detect_name_gender(full_name: str) -> str | None:
    """Return 'M' or 'F' based on the first name. Returns None if unknown."""
    if not full_name:
        return None
    first = full_name.strip().split()[0].lower()
    # Remove accents for matching
    import unicodedata
    first_norm = ''.join(c for c in unicodedata.normalize('NFD', first) if unicodedata.category(c) != 'Mn')
    if first_norm in _FEMALE_NAMES:
        return 'F'
    if first_norm in _MALE_NAMES:
        return 'M'
    # Suffix heuristic for Spanish names
    if first_norm.endswith('a') and not first_norm.endswith('oa'):
        return 'F'
    if first_norm.endswith(('o', 'el', 'er', 'on', 'an', 'in', 'os')):
        return 'M'
    return None


def _detect_gender_from_para_quien(para_quien: str) -> str | None:
    """Infer recipient gender from the relationship field in the popup form."""
    s = (para_quien or '').lower()
    if any(k in s for k in ['hija', 'nieta', 'sobrina', 'para mí', 'para mi ']):
        # 'para mi' alone is ambiguous but feminine options are hija/nieta/sobrina
        pass
    female = ['hija', 'nieta', 'sobrina']
    male   = ['hijo', 'nieto', 'sobrino']
    if any(k in s for k in female):
        return 'F'
    if any(k in s for k in male):
        return 'M'
    return None


def _age_matches(edad_rec: str, age: int) -> bool:
    """Check if an edad_recomendada string (e.g. '3-5 años', '+6 años', '4') contains the given age."""
    import re as _re
    # Strip non-numeric chars except + and - so '0-2 años' → '0-2', '+3 años' → '+3'
    s = _re.sub(r"[^\d+\-]", "", edad_rec.strip())
    if not s:
        return False
    if s.startswith("+"):
        try:
            return age >= int(s[1:])
        except ValueError:
            return False
    if s.endswith("+"):
        try:
            return age >= int(s[:-1])
        except ValueError:
            return False
    if "-" in s:
        lo_s, hi_s = s.split("-", 1)
        try:
            return int(lo_s) <= age <= int(hi_s)
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
    gender: str | None = None,
) -> list[dict]:
    """Returns active products matching age (and optionally gender), sorted by best sellers, excluding already bought."""
    history_rows = session.execute(text("""
        SELECT payload FROM shopify_events
        WHERE LOWER(email) = LOWER(:email)
          AND topic = 'orders/create'
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

    excl_clause = "AND sp.shopify_id != ALL(:excl)" if ever_bought else ""
    params: dict = {}
    if ever_bought:
        params["excl"] = list(ever_bought)

    try:
        all_rows = session.execute(text(f"""
            WITH order_counts AS (
                SELECT (item->>'product_id')::bigint AS product_id, COUNT(*) AS n
                FROM shopify_events,
                     jsonb_array_elements(payload->'line_items') AS item
                WHERE topic = 'orders/create'
                  AND jsonb_typeof(payload->'line_items') = 'array'
                GROUP BY 1
            )
            SELECT
                sp.shopify_id,
                sp.title,
                sp.handle,
                COALESCE(sp.imagen_url, sp.image_url) AS img,
                COALESCE(
                    sp.price,
                    sp.precio_min,
                    (sp.raw->'variants'->0->>'price')::numeric
                ) AS price,
                sp.edad_recomendada,
                sp.gender,
                COALESCE(oc.n, 0) AS sales
            FROM shopify_products sp
            LEFT JOIN order_counts oc ON oc.product_id = sp.shopify_id
            WHERE sp.status = 'active'
              AND sp.edad_recomendada IS NOT NULL
              AND sp.edad_recomendada <> ''
              {excl_clause}
            ORDER BY sales DESC
        """), params).fetchall()
    except Exception as exc:
        logger.warning("age_recommended: query failed: %s", exc)
        return []

    result = []
    for r in all_rows:
        if not _age_matches(r[5] or "", edad_regalon):
            continue
        prod_gender = r[6]  # 'M', 'F', or None
        # Gender filter: skip male products for female recipients and vice versa
        if gender and prod_gender and prod_gender != gender:
            continue
        price_val = float(r[4]) if r[4] else 0
        result.append({
            "shopify_id": r[0],
            "title": r[1],
            "handle": r[2],
            "image_url": r[3],
            "price": f"${price_val:,.0f}".replace(",", ".") if price_val else "",
            "url": f"https://www.happylapiz.cl/products/{r[2] or ''}",
            "sales": int(r[7]),
        })
        if len(result) >= max_products:
            break

    return result


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
            from app.services.dynamic_html_blocks import render_html_block
            vars_["recommended_products_html"] = render_html_block(
                session, "recommended_products_html", rec, _cs_btn
            ) or _build_cross_sell_html(rec, _cs_btn)

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
                genero_regalado = (extra_vars or {}).get("genero_regalado") or contact.gender
                age_rec = _fetch_age_recommended_products(session, contact.email, edad_int, gender=genero_regalado)
                vars_["productos_recomendados_edad"] = age_rec
                from app.services.dynamic_html_blocks import render_html_block
                vars_["productos_recomendados_edad_html"] = render_html_block(
                    session, "recommended_products_html", age_rec, btn_color
                ) or _build_cross_sell_html(age_rec, btn_color)
            except (ValueError, TypeError):
                pass

        from app.services.regalado_vars import prepare_regalado_vars, preprocess_regalado_template
        prepare_regalado_vars(vars_)

        # Product of the month — featured product block for template
        fp = vars_.get("featured_product")
        if isinstance(fp, dict) and fp.get("title"):
            _fp_btn = "#f97316"
            try:
                _blks = json.loads(tpl.json_blocks) if isinstance(tpl.json_blocks, str) else (tpl.json_blocks or [])
                for _b in (_blks if isinstance(_blks, list) else []):
                    if _b.get("type") == "product_grid" and _b.get("props", {}).get("btn_color"):
                        _fp_btn = _b["props"]["btn_color"]
                        break
            except Exception:
                pass
            if "descuento_producto_mes" not in vars_:
                pom_cfg = (auto.trigger_config or {}) if auto.trigger_type == "product_of_month" else {}
                vars_["descuento_producto_mes"] = int(pom_cfg.get("discount_percent", 20))
            from app.services.dynamic_html_blocks import render_html_block
            vars_["featured_product_html"] = render_html_block(
                session,
                "featured_product_html",
                [fp],
                _fp_btn,
                extra_vars={"descuento_producto_mes": vars_.get("descuento_producto_mes", 20)},
            ) or _build_cross_sell_html([fp], _fp_btn)
            vars_["producto_del_mes"] = fp.get("title", vars_.get("producto_del_mes", ""))
            vars_["producto_del_mes_url"] = fp.get("url", vars_.get("producto_del_mes_url", ""))

        _env = Environment(undefined=ChainableUndefined)
        from app.services.template_block_compiler import resolve_template_html
        raw_html = preprocess_regalado_template(replace_unsub_tag(resolve_template_html(tpl), contact.email))
        raw_html = resolve_relative_timers(raw_html)
        html = _inject_footer(_env.from_string(raw_html).render(**vars_), contact.email)

        preview_text = _env.from_string(
            preprocess_regalado_template(str(step.get("preview_text", "")))
        ).render(**vars_)
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
            "subject": _env.from_string(
                preprocess_regalado_template(str(step.get("subject", "")))
            ).render(**vars_),
            "html": html,
            "headers": _unsub_headers(contact.email),
        })
        resend_id = result.get("id") if isinstance(result, dict) else getattr(result, "id", None)
        run.status = "sent"
        run.resend_id = resend_id
        run.executed_at = datetime.utcnow()
        logger.info("Automation %d step %d variant=%s sent to %s", auto.id, step_number, variant or "-", contact.email)
        session.add(run)
        session.commit()
        return True
    except Exception as exc:
        run.error = str(exc)[:500]
        run.executed_at = datetime.utcnow()
        logger.error("Automation %d step %d failed for %s: %s", auto.id, step_number, contact.email, exc)
        session.add(run)
        session.commit()
        return False


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
        try:
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
                sent_ok = _send_email_step(session, auto, contact, enrollment.trigger_key, effective_step, enrollment.next_step, extra_vars, variant_label)
                if not sent_ok:
                    continue

            # Advance to next step
            next_step_num = enrollment.next_step + 1
            if next_step_num > len(steps):
                enrollment.status = "completed"
            else:
                if auto.trigger_type == "product_of_month":
                    extra = json.loads(enrollment.extra_vars_json or "{}")
                    schedules = extra.get("step_schedules") or {}
                    sched_key = str(next_step_num)
                    if sched_key in schedules:
                        enrollment.next_step = next_step_num
                        enrollment.next_send_at = datetime.fromisoformat(schedules[sched_key])
                    else:
                        enrollment.status = "completed"
                else:
                    next_step = steps[next_step_num - 1]
                    delay = float(next_step.get("delay_hours", 24))
                    enrollment.next_step = next_step_num
                    enrollment.next_send_at = now + timedelta(hours=delay)

            session.add(enrollment)
            session.commit()
        except Exception as exc:
            logger.exception("Enrollment %d (auto %d, %s) processing error: %s",
                             enrollment.id, enrollment.automation_id, enrollment.contact_email, exc)
            try:
                session.rollback()
            except Exception:
                pass


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
        SELECT se.id, se.email, se.payload, se.shopify_id
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
        # Use shopify_id (Shopify's own order/event ID) when available so that webhook-
        # created and sync-backfilled events for the same order share the same trigger_key
        # and deduplication in _enroll() prevents double enrollment.
        trigger_key = f"{trigger_type}:{row[3] or row[0]}"
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
    Birthday reminder enrollment. Early preview in «Próximos envíos» (enroll_early_days)
    only applies when data_source is form or gift_popup.
    trigger_config keys:
      data_source: str        — contacts (default) | form | gift_popup
      form_id: int            — required when data_source=form
      days_before: int        — days before birthday to send (default 30)
      enroll_early_days: int  — only used with form / gift_popup sources
      birthday_field: str     — date field (default "fecha_nacimiento")
      name_field: str         — name field (default "nombre_regalado")
      relation_field: str     — relation field (default "relacion")
    """
    from app.models.contact import Contact
    from app.services.birthday_triggers import (
        iter_contacts_on_mmdd,
        iter_form_on_mmdd,
        iter_gift_flow_on_mmdd,
    )
    from app.services.birthday_config import (
        repair_birthday_automation_if_needed,
        resolve_birthday_data_source,
        resolve_enroll_early_days,
    )
    from app.services.regalado_vars import (
        get_regalado_field,
        infer_relation_field,
        parse_birthday_mmdd,
        prepare_regalado_vars,
    )

    repair_birthday_automation_if_needed(auto, session)
    config = auto.trigger_config or {}
    days_before = int(config.get("days_before", 30))
    data_source = resolve_birthday_data_source(auto)
    enroll_early_days = resolve_enroll_early_days(auto, data_source)
    birthday_field = config.get("birthday_field", "fecha_nacimiento")
    name_field = config.get("name_field", "nombre_regalado")
    relation_field = infer_relation_field(
        name_field,
        config.get("relation_field", "relacion"),
    )

    steps = _get_steps(auto)
    if not steps:
        return
    first_delay = float(steps[0].get("delay_hours", 0))
    if enroll_early_days > 0:
        first_delay = enroll_early_days * 24

    today = datetime.utcnow().date()
    enroll_when_days_before = days_before + enroll_early_days
    target = today + timedelta(days=enroll_when_days_before)
    target_mmdd = f"{target.month:02d}-{target.day:02d}"

    seen: set[tuple] = set()

    def _try_enroll(email: str, contact: Contact | None, data: dict) -> None:
        raw_date = get_regalado_field(data, birthday_field)
        if not raw_date or parse_birthday_mmdd(raw_date) != target_mmdd:
            return

        email_l = email.lower()
        dedupe = (email_l, birthday_field, target.year, days_before)
        if dedupe in seen:
            return
        seen.add(dedupe)

        child_name = get_regalado_field(data, name_field)
        relation = get_regalado_field(data, relation_field)
        contact_name = (contact.name if contact else None) or data.get("nombre") or email
        first = str(contact_name).split()[0]

        owner_key = contact.id if contact else email_l
        trigger_key = f"birthday:{owner_key}:{birthday_field}:{target.year}:{days_before}"
        extra_vars = {
            **{k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)},
            "nombre": contact_name,
            "first_name": first,
            "nombre_regalado": child_name,
            "relacion": relation,
            "dias_para_cumpleanos": days_before,
            "fecha_cumpleanos": str(target),
        }
        if isinstance(data.get("regalados"), list):
            extra_vars["regalados"] = data["regalados"]
        prepare_regalado_vars(extra_vars)
        _enroll(session, auto, email_l, trigger_key, first_delay, extra_vars)

    if data_source == "gift_popup":
        for email, data, contact in iter_gift_flow_on_mmdd(
            session, target.month, target.day
        ):
            _try_enroll(email, contact, data)
        return

    if data_source == "form":
        form_id = config.get("form_id")
        if not form_id:
            return
        for email, data, contact in iter_form_on_mmdd(
            session, int(form_id), target.month, target.day
        ):
            _try_enroll(email, contact, data)
        return

    for email, data, contact in iter_contacts_on_mmdd(
        session, target.month, target.day, birthday_field
    ):
        _try_enroll(email, contact, data)


def _check_product_of_month(auto: Automation, session: Session) -> None:
    """Enroll segment on the 1st Monday of each month for a 3-email product-of-month flow."""
    from app.services.product_of_month import (
        build_step_schedules_from_steps,
        get_or_create_monthly_product,
        is_enrollment_day,
        mark_month_enrolled,
        month_already_enrolled,
        month_key_for,
        today_in_tz,
    )

    config = auto.trigger_config or {}
    tz_name = str(config.get("timezone", "America/Santiago"))
    today = today_in_tz(tz_name)

    steps = _get_steps(auto)
    if not steps:
        return
    if not is_enrollment_day(today, steps):
        return

    mk = month_key_for(today)
    if month_already_enrolled(session, auto.id, mk):
        return

    segment_id = config.get("segment_id")
    if not segment_id:
        logger.warning("product_of_month automation %d: segment_id not configured", auto.id)
        return

    seg = session.get(Segment, int(segment_id))
    if not seg:
        logger.warning("product_of_month automation %d: segment %s not found", auto.id, segment_id)
        return

    pool_size = int(config.get("product_pool_size", 5))
    product = get_or_create_monthly_product(session, auto.id, mk, pool_size)
    if not product:
        logger.warning("product_of_month automation %d: no product available for %s", auto.id, mk)
        return

    send_hour = int(config.get("send_hour", 10))
    discount_percent = int(config.get("discount_percent", 20))
    step_schedules = build_step_schedules_from_steps(steps, today.year, today.month, tz_name, send_hour)

    extra_base = {
        "featured_product": product,
        "producto_del_mes": product.get("title", ""),
        "producto_del_mes_url": product.get("url", ""),
        "descuento_producto_mes": discount_percent,
        "month_key": mk,
        "step_schedules": step_schedules,
    }

    contacts = evaluate_segment(seg.conditions, session)
    exclude_ids = config.get("exclude_segment_ids") or []
    if exclude_ids:
        excluded: set[int] = set()
        for excl_id in exclude_ids:
            excl_seg = session.get(Segment, int(excl_id))
            if excl_seg:
                excluded.update(c.id for c in evaluate_segment(excl_seg.conditions, session))
        contacts = [c for c in contacts if c.id not in excluded]

    if not contacts:
        mark_month_enrolled(session, auto.id, mk)
        return

    enrolled = 0
    for contact in contacts:
        trigger_key = f"pom:{auto.id}:{mk}:{contact.id}"
        if _enroll(session, auto, contact.email, trigger_key, 0.0, extra_base):
            enrolled += 1

    if enrolled > 0:
        mark_month_enrolled(session, auto.id, mk)
        logger.info(
            "product_of_month: automation %d enrolled %d contacts for %s (product: %s)",
            auto.id, enrolled, mk, product.get("title"),
        )


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
    "product_of_month":         _check_product_of_month,
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
                from app.services.campaign_audience import get_campaign_recipient_ids

                recipient_ids = get_campaign_recipient_ids(
                    session, campaign.segment_id, campaign.exclude_segment_ids,
                )
                if not recipient_ids:
                    continue
                already_sent = set(session.exec(
                    select(CampaignSend.contact_id).where(
                        CampaignSend.campaign_id == campaign.id,
                        CampaignSend.status.in_((
                            "sent", "delivered", "opened", "clicked", "bounced", "complained",
                        )),
                    )
                ).all())
                to_send_ids = [cid for cid in recipient_ids if cid not in already_sent]
                if not to_send_ids:
                    campaign.status = "sent"
                    session.add(campaign)
                    session.commit()
                    continue
                campaign.status = "sending"
                session.add(campaign)
                session.commit()
                send_campaign_batch(campaign.id, None, len(recipient_ids), auto_resume=True)
            except Exception as exc:
                logger.exception("Scheduled campaign %d error: %s", campaign.id, exc)


def run_automation_triggers() -> None:
    """Phase 1: detect triggers and create enrollments (no sends)."""
    with Session(db_engine) as session:
        automations = session.exec(
            select(Automation).where(Automation.status == "active")
        ).all()
        auto_ids = [(a.id, a.trigger_type) for a in automations]

    for auto_id, trigger_type in auto_ids:
        handler = HANDLERS.get(trigger_type)
        if not handler:
            continue
        try:
            with Session(db_engine) as session:
                auto = session.get(Automation, auto_id)
                if auto:
                    handler(auto, session)
        except Exception as exc:
            logger.exception("Automation %d (%s) trigger error: %s", auto_id, trigger_type, exc)


def process_ready_enrollments() -> None:
    """Phase 2: send emails for enrollments whose next_send_at has passed."""
    try:
        with Session(db_engine) as session:
            _process_enrollments(session)
    except Exception as exc:
        logger.exception("Enrollment processing error: %s", exc)


def run_automations() -> None:
    """Full cycle (triggers + sends) — used by manual /run-now only."""
    run_automation_triggers()
    process_ready_enrollments()
