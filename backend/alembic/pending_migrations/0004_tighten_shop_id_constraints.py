"""tighten shop_id to NOT NULL + FK, and make contacts.email unique per shop

Revision ID: 0004_tighten_shop_id_constraints
Revises: 0003_backfill_bootstrap_shop
Create Date: 2026-07-01

DO NOT run this until 0001-0003 have been applied AND the app code that
populates shop_id on every new row (Deploy 2: get_current_shop-scoped
routers, the OAuth callback, webhook tenant resolution) has been live in
production for a while with no NULL shop_id rows showing up. Running this
before that will hard-fail (by design — the guard raises loudly rather than
silently corrupting data) or, if forced through, would start rejecting
writes from any code path that hasn't been converted yet.

This file intentionally lives in alembic/pending_migrations/, NOT in
alembic/versions/ — the Dockerfile runs `alembic upgrade head` on every
deploy, which would apply this immediately together with 0001-0003 if it
sat in versions/. When you're ready for the Deploy 3 tightening step, move
this file into alembic/versions/ and deploy again.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_tighten_shop_id_constraints"
down_revision: Union[str, None] = "0003_backfill_bootstrap_shop"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ORM_TABLES = [
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
]

RAW_TABLES = [
    "shopify_products",
    "shopify_orders",
    "shopify_events",
    "shopify_checkouts",
    "carritos_abandonados",
    "coupon_campaigns",
    "coupon_sends",
]


def _assert_no_null_shop_id(bind, table: str) -> None:
    count = bind.execute(sa.text(f"SELECT COUNT(*) FROM {table} WHERE shop_id IS NULL")).scalar()
    if count:
        raise RuntimeError(
            f"{table} tiene {count} fila(s) con shop_id NULL — corré/revisá el backfill "
            f"(0003_backfill_bootstrap_shop) antes de aplicar esta migración."
        )


def upgrade() -> None:
    bind = op.get_bind()

    for table in ORM_TABLES + RAW_TABLES:
        exists = bind.execute(sa.text(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = :t"
        ), {"t": table}).scalar()
        if not exists:
            continue
        _assert_no_null_shop_id(bind, table)
        op.execute(f"ALTER TABLE {table} ALTER COLUMN shop_id SET NOT NULL")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT fk_{table}_shop_id "
            f"FOREIGN KEY (shop_id) REFERENCES shops(id)"
        )

    # contacts.email: global-unique -> unique per shop
    op.execute("ALTER TABLE contacts DROP CONSTRAINT IF EXISTS contacts_email_key")
    op.execute(
        "ALTER TABLE contacts ADD CONSTRAINT contacts_shop_id_email_key UNIQUE (shop_id, email)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE contacts DROP CONSTRAINT IF EXISTS contacts_shop_id_email_key")
    op.execute("ALTER TABLE contacts ADD CONSTRAINT contacts_email_key UNIQUE (email)")

    for table in ORM_TABLES + RAW_TABLES:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS fk_{table}_shop_id")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN shop_id DROP NOT NULL")
