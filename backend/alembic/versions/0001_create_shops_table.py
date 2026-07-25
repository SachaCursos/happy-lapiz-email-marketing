"""create shops table

Revision ID: 0001_create_shops_table
Revises:
Create Date: 2026-07-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_create_shops_table"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS shops (
            id SERIAL PRIMARY KEY,
            shopify_domain VARCHAR NOT NULL UNIQUE,
            shopify_shop_id VARCHAR,
            access_token_encrypted VARCHAR NOT NULL,
            scopes VARCHAR,
            status VARCHAR NOT NULL DEFAULT 'active',
            installed_at TIMESTAMP NOT NULL DEFAULT now(),
            uninstalled_at TIMESTAMP,
            shop_owner_email VARCHAR,
            plan_name VARCHAR,
            currency VARCHAR,
            initial_sync_status VARCHAR NOT NULL DEFAULT 'pending',
            initial_sync_started_at TIMESTAMP,
            initial_sync_completed_at TIMESTAMP,
            initial_sync_error VARCHAR,
            initial_sync_stats JSON,
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            updated_at TIMESTAMP NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_shops_shopify_domain ON shops (shopify_domain)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS shops")
