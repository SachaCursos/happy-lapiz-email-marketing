"""add nullable shop_id column to every tenant-scoped table

Revision ID: 0002_add_shop_id_columns
Revises: 0001_create_shops_table
Create Date: 2026-07-01

Additive-only: every column is nullable, so old app code (which knows
nothing about shop_id) keeps working unmodified against this schema.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_add_shop_id_columns"
down_revision: Union[str, None] = "0001_create_shops_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# SQLModel-backed tables
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

# Tables that only exist via raw SQL in app/database.py::_run_migrations()
RAW_TABLES = [
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
    for table in ORM_TABLES + RAW_TABLES:
        op.execute(
            f"ALTER TABLE IF EXISTS {table} ADD COLUMN IF NOT EXISTS shop_id INTEGER"
        )
        # CREATE INDEX has no "IF TABLE EXISTS" guard, unlike ALTER TABLE above —
        # skip tables that don't exist yet (e.g. shopify_orders/shopify_events/
        # shopify_checkouts/carritos_abandonados, which the separate ETL pipeline
        # creates, not this app) instead of crashing the whole migration run.
        # database.py::_run_migrations() self-heals the index once the table
        # shows up, on this app's next startup.
        exists = bind.execute(
            sa.text("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = :t"),
            {"t": table},
        ).scalar()
        if exists:
            op.execute(
                f"CREATE INDEX IF NOT EXISTS ix_{table}_shop_id ON {table} (shop_id)"
            )


def downgrade() -> None:
    for table in ORM_TABLES + RAW_TABLES:
        op.execute(f"ALTER TABLE IF EXISTS {table} DROP COLUMN IF EXISTS shop_id")
