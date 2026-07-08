"""Global dynamic criteria for product recommendation variables."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlmodel import Session

from app.services.product_recommendations import DEFAULT_LOOKBACK_DAYS, DEFAULT_MAX_PRODUCTS

CRITERIA_CATALOG: dict[str, dict[str, Any]] = {
    "recommended_products": {
        "name": "Criterios recommended_products",
        "description": (
            "Define cómo se eligen los productos para "
            "{{ recommended_products }}, {{ productos_recomendados_edad }} y sus grillas HTML."
        ),
        "variables": [
            "recommended_products",
            "recommended_products_html",
            "productos_recomendados_edad",
            "productos_recomendados_edad_html",
        ],
        "default_config": {
            "enabled": True,
            "max_products": DEFAULT_MAX_PRODUCTS,
            "strategy": "bestseller",
            "lookback_days": DEFAULT_LOOKBACK_DAYS,
            "require_age_match": True,
            "require_edad_catalog": True,
            "exclude_purchased": True,
            "rules": [],
        },
    },
    "cross_sell": {
        "name": "Criterios cross sell",
        "description": (
            "Reglas cuando el cliente compró un producto específico. "
            "Se usa en automatizaciones de pedido con {{ recommended_products }} / cross-sell."
        ),
        "variables": [
            "recommended_products",
            "recommended_products_html",
        ],
        "default_config": {
            "enabled": True,
            "max_products": DEFAULT_MAX_PRODUCTS,
            "strategy": "rules_then_bestseller",
            "lookback_days": DEFAULT_LOOKBACK_DAYS,
            "require_age_match": False,
            "require_edad_catalog": True,
            "exclude_purchased": True,
            "rules": [],
        },
    },
}


def ensure_dynamic_criteria(session: Session) -> None:
    now = datetime.utcnow()
    for key, meta in CRITERIA_CATALOG.items():
        exists = session.execute(
            text("SELECT 1 FROM dynamic_criteria WHERE criteria_key = :k"),
            {"k": key},
        ).fetchone()
        if exists:
            continue
        session.execute(
            text("""
                INSERT INTO dynamic_criteria (criteria_key, name, description, variables, config, updated_at)
                VALUES (:k, :name, :description, CAST(:variables AS jsonb), CAST(:config AS jsonb), :now)
            """),
            {
                "k": key,
                "name": meta["name"],
                "description": meta["description"],
                "variables": __import__("json").dumps(meta["variables"]),
                "config": __import__("json").dumps(meta["default_config"]),
                "now": now,
            },
        )
    session.commit()


def load_criteria_config(session: Session, criteria_key: str) -> dict:
    ensure_dynamic_criteria(session)
    row = session.execute(
        text("SELECT config FROM dynamic_criteria WHERE criteria_key = :k"),
        {"k": criteria_key},
    ).fetchone()
    if row and row[0]:
        cfg = row[0] if isinstance(row[0], dict) else __import__("json").loads(row[0])
        return dict(cfg)
    return dict(CRITERIA_CATALOG.get(criteria_key, {}).get("default_config", {}))


def list_criteria(session: Session) -> list[dict]:
    ensure_dynamic_criteria(session)
    rows = session.execute(
        text("""
            SELECT criteria_key, name, description, variables, config, updated_at
            FROM dynamic_criteria
            ORDER BY criteria_key
        """)
    ).fetchall()
    result = []
    for r in rows:
        variables = r[3]
        if isinstance(variables, str):
            variables = __import__("json").loads(variables)
        config = r[4]
        if isinstance(config, str):
            config = __import__("json").loads(config)
        result.append({
            "criteria_key": r[0],
            "name": r[1],
            "description": r[2],
            "variables": variables or [],
            "config": config or {},
            "updated_at": r[5],
        })
    return result
