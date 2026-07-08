"""Product recommendation engine for automation emails.

Supports:
- Bestsellers from shopify_orders / shopify_order_line_items (configurable lookback, default 180 days)
- Age-based filtering via edad_recomendada
- Rule-based cross-sell (if bought product A → recommend B, C, D in order)
- Purchase-history exclusion
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy import text
from sqlmodel import Session

logger = logging.getLogger(__name__)

DEFAULT_LOOKBACK_DAYS = 180
DEFAULT_MAX_PRODUCTS = 4


def normalize_recommendation_config(raw: dict | None) -> dict:
    """Merge legacy cross_sell_config with product_recommendation_config."""
    cfg = dict(raw or {})
    legacy = cfg.pop("cross_sell_config", None) or {}
    prc = cfg.get("product_recommendation_config") or {}

    merged: dict[str, Any] = {
        "enabled": True,
        "max_products": DEFAULT_MAX_PRODUCTS,
        "strategy": "bestseller",
        "lookback_days": DEFAULT_LOOKBACK_DAYS,
        "require_age_match": True,
        "require_edad_catalog": True,
        "exclude_purchased": True,
        "rules": [],
    }

    if legacy:
        merged["enabled"] = True
        if "max_products" in legacy:
            merged["max_products"] = int(legacy["max_products"])
        if legacy.get("strategy"):
            merged["strategy"] = legacy["strategy"]
        if legacy.get("lookback_days") is not None:
            merged["lookback_days"] = int(legacy["lookback_days"])
        if legacy.get("require_age_match") is not None:
            merged["require_age_match"] = bool(legacy["require_age_match"])
        if legacy.get("rules"):
            merged["rules"] = legacy["rules"]

    if (prc):
        merged.update({k: v for k, v in prc.items() if v is not None})
    if "enabled" in (prc or {}):
        merged["enabled"] = bool(prc["enabled"])
    elif legacy and legacy.get("enabled") is False:
        merged["enabled"] = False

    merged["max_products"] = max(1, min(8, int(merged.get("max_products") or DEFAULT_MAX_PRODUCTS)))
    merged["lookback_days"] = max(1, min(365, int(merged.get("lookback_days") or DEFAULT_LOOKBACK_DAYS)))
    if not isinstance(merged.get("rules"), list):
        merged["rules"] = []
    return merged


def get_recommendation_config(trigger_config: dict | None) -> dict:
    return normalize_recommendation_config(trigger_config or {})


def _product_pk_sql() -> str:
    """SQL expression for the canonical Shopify product id on shopify_products rows."""
    return "COALESCE(sp.shopify_id, NULLIF(sp.id::text, '')::bigint)"


def _age_matches(edad_rec: str, age: int) -> bool:
    s = re.sub(r"[^\d+\-]", "", (edad_rec or "").strip())
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


def _format_price(price_val: float | None) -> str:
    if not price_val:
        return ""
    return f"${float(price_val):,.0f}".replace(",", ".")


def _row_to_product(r: tuple) -> dict:
    shopify_id, title, handle, img, price, sales = r
    price_val = float(price) if price else 0
    return {
        "shopify_id": shopify_id,
        "title": title or "",
        "handle": handle or "",
        "image_url": img,
        "price": _format_price(price_val),
        "url": f"https://www.happylapiz.cl/products/{handle or ''}",
        "sales": int(sales or 0),
    }


def _get_purchased_product_ids(session: Session, customer_email: str) -> set[int]:
    """All product IDs ever purchased by this customer (from normalized orders)."""
    try:
        rows = session.execute(text("""
            SELECT DISTINCT li.product_id
            FROM shopify_order_line_items li
            JOIN shopify_orders o ON o.id = li.order_id
            WHERE LOWER(o.email) = LOWER(:email)
              AND li.product_id IS NOT NULL
              AND li.product_id <> ''
              AND (o.cancelled_at IS NULL)
              AND COALESCE(o.financial_status, '') NOT IN ('voided', 'refunded')
        """), {"email": customer_email}).fetchall()
        return {int(r[0]) for r in rows if r[0] and str(r[0]).isdigit()}
    except Exception as exc:
        logger.warning("purchased_product_ids: shopify_orders query failed: %s", exc)
        return _get_purchased_product_ids_from_events(session, customer_email)


def _get_purchased_product_ids_from_events(session: Session, customer_email: str) -> set[int]:
    ever_bought: set[int] = set()
    rows = session.execute(text("""
        SELECT payload FROM shopify_events
        WHERE LOWER(email) = LOWER(:email)
          AND topic = 'orders/create'
          AND payload IS NOT NULL
    """), {"email": customer_email}).fetchall()
    for row in rows:
        try:
            payload = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            for item in payload.get("line_items", []):
                pid = item.get("product_id")
                if pid:
                    ever_bought.add(int(pid))
        except Exception:
            pass
    return ever_bought


def _fetch_products_by_ids(
    session: Session,
    product_ids: list[int],
    exclude_ids: set[int] | None = None,
) -> list[dict]:
    if not product_ids:
        return []
    exclude_ids = exclude_ids or set()
    ids = [pid for pid in product_ids if pid not in exclude_ids]
    if not ids:
        return []

    pk = _product_pk_sql()
    try:
        rows = session.execute(text(f"""
            SELECT
                {pk} AS shopify_id,
                sp.title,
                sp.handle,
                COALESCE(sp.imagen_url, sp.image_url) AS img,
                COALESCE(sp.price, sp.precio_min, (sp.raw->'variants'->0->>'price')::numeric) AS price,
                0 AS sales
            FROM shopify_products sp
            WHERE sp.status = 'active'
              AND {pk} = ANY(:ids)
        """), {"ids": ids}).fetchall()
    except Exception as exc:
        logger.warning("fetch_products_by_ids failed: %s", exc)
        return []

    by_id = {_row_to_product(r)["shopify_id"]: _row_to_product(r) for r in rows}
    result = []
    for pid in ids:
        p = by_id.get(pid)
        if p:
            result.append(p)
    return result


def _fetch_bestsellers(
    session: Session,
    *,
    lookback_days: int,
    edad_regalon: int | None,
    require_age_match: bool,
    require_edad_catalog: bool,
    exclude_ids: set[int],
    max_products: int,
) -> list[dict]:
    pk = _product_pk_sql()
    excl_clause = f"AND {pk} != ALL(:excl)" if exclude_ids else ""
    edad_clause = ""
    if require_edad_catalog:
        edad_clause = "AND sp.edad_recomendada IS NOT NULL AND sp.edad_recomendada <> ''"

    params: dict[str, Any] = {"days": lookback_days}
    if exclude_ids:
        params["excl"] = list(exclude_ids)

    try:
        all_rows = session.execute(text(f"""
            WITH order_counts AS (
                SELECT li.product_id::bigint AS product_id, SUM(li.quantity)::bigint AS n
                FROM shopify_order_line_items li
                JOIN shopify_orders o ON o.id = li.order_id
                WHERE o.created_at >= NOW() - make_interval(days => :days)
                  AND (o.cancelled_at IS NULL)
                  AND COALESCE(o.financial_status, '') NOT IN ('voided', 'refunded')
                  AND li.product_id IS NOT NULL AND li.product_id <> ''
                GROUP BY 1
            )
            SELECT
                {pk} AS shopify_id,
                sp.title,
                sp.handle,
                COALESCE(sp.imagen_url, sp.image_url) AS img,
                COALESCE(sp.price, sp.precio_min, (sp.raw->'variants'->0->>'price')::numeric) AS price,
                sp.edad_recomendada,
                COALESCE(oc.n, 0) AS sales
            FROM shopify_products sp
            LEFT JOIN order_counts oc ON oc.product_id = {pk}
            WHERE sp.status = 'active'
              {edad_clause}
              {excl_clause}
            ORDER BY sales DESC, sp.title ASC
        """), params).fetchall()
    except Exception as exc:
        logger.warning("bestsellers: shopify_orders query failed, falling back to events: %s", exc)
        return _fetch_bestsellers_from_events(
            session,
            edad_regalon=edad_regalon,
            require_age_match=require_age_match,
            require_edad_catalog=require_edad_catalog,
            exclude_ids=exclude_ids,
            max_products=max_products,
        )

    result = []
    for r in all_rows:
        if require_age_match and edad_regalon is not None and not _age_matches(r[5] or "", edad_regalon):
            continue
        result.append(_row_to_product(r[:5] + (r[6],)))
        if len(result) >= max_products:
            break
    return result


def _fetch_bestsellers_from_events(
    session: Session,
    *,
    edad_regalon: int | None,
    require_age_match: bool,
    require_edad_catalog: bool,
    exclude_ids: set[int],
    max_products: int,
) -> list[dict]:
    pk = _product_pk_sql()
    excl_clause = f"AND {pk} != ALL(:excl)" if exclude_ids else ""
    edad_clause = ""
    if require_edad_catalog:
        edad_clause = "AND sp.edad_recomendada IS NOT NULL AND sp.edad_recomendada <> ''"
    params: dict[str, Any] = {}
    if exclude_ids:
        params["excl"] = list(exclude_ids)

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
                {pk} AS shopify_id,
                sp.title,
                sp.handle,
                COALESCE(sp.imagen_url, sp.image_url) AS img,
                COALESCE(sp.price, sp.precio_min, (sp.raw->'variants'->0->>'price')::numeric) AS price,
                sp.edad_recomendada,
                COALESCE(oc.n, 0) AS sales
            FROM shopify_products sp
            LEFT JOIN order_counts oc ON oc.product_id = {pk}
            WHERE sp.status = 'active'
              {edad_clause}
              {excl_clause}
            ORDER BY sales DESC, sp.title ASC
        """), params).fetchall()
    except Exception as exc:
        logger.warning("bestsellers events fallback failed: %s", exc)
        return []

    result = []
    for r in all_rows:
        if require_age_match and edad_regalon is not None and not _age_matches(r[5] or "", edad_regalon):
            continue
        result.append(_row_to_product(r[:5] + (r[6],)))
        if len(result) >= max_products:
            break
    return result


def _resolve_rule_products(
    session: Session,
    rules: list[dict],
    trigger_product_ids: list[int],
    exclude_ids: set[int],
    max_products: int,
) -> list[dict]:
    if not rules or not trigger_product_ids:
        return []

    trigger_set = set(trigger_product_ids)
    for rule in rules:
        if_products = [int(x) for x in (rule.get("if_product_ids") or []) if str(x).isdigit()]
        if not if_products:
            continue
        if not trigger_set.intersection(if_products):
            continue

        recommend_ids = [int(x) for x in (rule.get("recommend_product_ids") or []) if str(x).isdigit()]
        if not recommend_ids:
            continue

        picked = _fetch_products_by_ids(session, recommend_ids, exclude_ids)
        if picked:
            return picked[:max_products]
    return []


def resolve_recommended_products(
    session: Session,
    customer_email: str,
    config: dict,
    *,
    edad_regalon: int | None = None,
    trigger_product_ids: list[int] | None = None,
) -> list[dict]:
    """Main entry: resolve product recommendations according to automation config."""
    cfg = normalize_recommendation_config(config)
    if not cfg.get("enabled", True):
        return []

    max_products = int(cfg["max_products"])
    strategy = cfg.get("strategy") or "bestseller"
    lookback_days = int(cfg["lookback_days"])
    require_age_match = bool(cfg.get("require_age_match", True))
    require_edad_catalog = bool(cfg.get("require_edad_catalog", True))
    exclude_purchased = bool(cfg.get("exclude_purchased", True))
    rules = cfg.get("rules") or []

    exclude_ids: set[int] = set()
    if exclude_purchased:
        exclude_ids = _get_purchased_product_ids(session, customer_email)

    trigger_ids = list(trigger_product_ids or [])

    rule_products: list[dict] = []
    if strategy in ("rules", "rules_then_bestseller") and rules:
        rule_products = _resolve_rule_products(session, rules, trigger_ids, exclude_ids, max_products)

    if strategy == "rules":
        return rule_products[:max_products]

    if rule_products and strategy == "rules_then_bestseller":
        if len(rule_products) >= max_products:
            return rule_products[:max_products]
        seen = {p["shopify_id"] for p in rule_products if p.get("shopify_id")}
        exclude_for_fill = exclude_ids | seen
        fillers = _fetch_bestsellers(
            session,
            lookback_days=lookback_days,
            edad_regalon=edad_regalon,
            require_age_match=require_age_match,
            require_edad_catalog=require_edad_catalog,
            exclude_ids=exclude_for_fill,
            max_products=max_products - len(rule_products),
        )
        return rule_products + fillers

    return _fetch_bestsellers(
        session,
        lookback_days=lookback_days,
        edad_regalon=edad_regalon,
        require_age_match=require_age_match,
        require_edad_catalog=require_edad_catalog,
        exclude_ids=exclude_ids,
        max_products=max_products,
    )
