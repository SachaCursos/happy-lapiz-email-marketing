"""bootstrap the Happy Lapiz Shop row and backfill shop_id on existing rows

Revision ID: 0003_backfill_bootstrap_shop
Revises: 0002_add_shop_id_columns
Create Date: 2026-07-01

Idempotent / rerunnable: every UPDATE is guarded with WHERE shop_id IS NULL,
and the bootstrap Shop row is only inserted if its domain doesn't exist yet.
Requires SHOPIFY_ACCESS_TOKEN, SHOPIFY_DOMAIN and SHOPIFY_TOKEN_ENCRYPTION_KEY
to already be set in the environment this migration runs in.
"""
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.core.config import settings
from app.core.crypto import encrypt_token

revision: str = "0003_backfill_bootstrap_shop"
down_revision: Union[str, None] = "0002_add_shop_id_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BACKFILL_TABLES = [
    "users",
    "contacts",
    "campaigns",
    "campaign_sends",
    "automations",
    "automation_enrollments",
    "automation_runs",
    "segments",
    "templates",
    "signup_forms",
    "form_submissions",
    "gift_recipients",
    "shopify_products",
    "shopify_orders",
    "shopify_events",
    "shopify_checkouts",
    "carritos_abandonados",
    "coupon_campaigns",
    "coupon_sends",
]


def upgrade() -> None:
    bind = op.get_bind()

    domain = settings.SHOPIFY_DOMAIN
    existing = bind.execute(
        sa.text("SELECT id FROM shops WHERE shopify_domain = :domain"),
        {"domain": domain},
    ).fetchone()

    if existing:
        shop_id = existing[0]
    else:
        token_encrypted = encrypt_token(settings.SHOPIFY_ACCESS_TOKEN or "")
        result = bind.execute(
            sa.text(
                """
                INSERT INTO shops (shopify_domain, access_token_encrypted, status, installed_at, created_at, updated_at)
                VALUES (:domain, :token, 'active', :now, :now, :now)
                RETURNING id
                """
            ),
            {
                "domain": domain,
                "token": token_encrypted,
                "now": datetime.now(timezone.utc),
            },
        )
        shop_id = result.fetchone()[0]

    for table in BACKFILL_TABLES:
        bind.execute(
            sa.text(
                f"UPDATE {table} SET shop_id = :shop_id WHERE shop_id IS NULL"
            ),
            {"shop_id": shop_id},
        )


def downgrade() -> None:
    # Backfill is not reversible in a meaningful way; leave shop_id values in
    # place (the column itself is dropped by the 0002 downgrade if needed).
    pass
