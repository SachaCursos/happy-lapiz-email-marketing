from sqlmodel import create_engine, Session, SQLModel
from sqlalchemy import text
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=300,
)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
    _run_migrations()


def _run_migrations():
    """Add columns/tables that were added after initial table creation.
    Each statement runs in its own transaction so one failure never blocks the rest.
    """
    # Step 1: fix shopify_products if it exists without the shopify_id column
    # (Python-side check avoids DO $$ syntax issues and transaction abort cascade)
    with Session(engine) as session:
        try:
            has_col = session.execute(text(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_name = 'shopify_products' AND column_name = 'shopify_id'"
            )).scalar()
            if has_col == 0:
                session.execute(text("DROP TABLE IF EXISTS shopify_products"))
            session.commit()
        except Exception:
            session.rollback()

    migrations = [
        "ALTER TABLE templates ALTER COLUMN subject_default SET DEFAULT ''",
        "ALTER TABLE signup_forms ADD COLUMN IF NOT EXISTS design_config JSONB",
        "ALTER TABLE signup_forms ADD COLUMN IF NOT EXISTS steps_config JSONB",
        "ALTER TABLE signup_forms ADD COLUMN IF NOT EXISTS coupon_campaign_id INTEGER",
        "ALTER TABLE signup_forms ADD COLUMN IF NOT EXISTS coupon_automation_id INTEGER",
        "ALTER TABLE form_submissions ADD COLUMN IF NOT EXISTS coupon_code VARCHAR",
        "ALTER TABLE automation_runs ADD COLUMN IF NOT EXISTS variant_sent VARCHAR",
        "ALTER TABLE automations ADD COLUMN IF NOT EXISTS coupon_campaign_id INTEGER",
        "ALTER TABLE coupon_campaigns ADD COLUMN IF NOT EXISTS coupon_mode VARCHAR NOT NULL DEFAULT 'dynamic'",
        "ALTER TABLE coupon_campaigns ADD COLUMN IF NOT EXISTS static_code VARCHAR",
        # Keep only the earliest run per (automation, trigger_key, step) before adding
        # the unique index below, in case the pre-fix race already produced duplicates.
        """DELETE FROM automation_runs a USING automation_runs b
           WHERE a.id > b.id
             AND a.automation_id = b.automation_id
             AND a.trigger_key = b.trigger_key
             AND a.step_number = b.step_number""",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_automation_runs_dedup ON automation_runs (automation_id, trigger_key, step_number)",
        """CREATE TABLE IF NOT EXISTS shopify_products (
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
            synced_at TIMESTAMP NOT NULL DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS coupon_campaigns (
            id SERIAL PRIMARY KEY,
            name VARCHAR NOT NULL,
            shopify_discount_id VARCHAR,
            discount_type VARCHAR NOT NULL DEFAULT 'percentage',
            discount_value NUMERIC NOT NULL DEFAULT 10,
            min_purchase NUMERIC NOT NULL DEFAULT 0,
            prefix VARCHAR NOT NULL DEFAULT 'HL',
            expires_at VARCHAR,
            applies_to VARCHAR NOT NULL DEFAULT 'all',
            status VARCHAR NOT NULL DEFAULT 'active',
            coupon_mode VARCHAR NOT NULL DEFAULT 'dynamic',
            static_code VARCHAR,
            created_by INTEGER,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS coupon_sends (
            id SERIAL PRIMARY KEY,
            coupon_campaign_id INTEGER NOT NULL REFERENCES coupon_campaigns(id),
            contact_id INTEGER,
            contact_email VARCHAR NOT NULL,
            code VARCHAR NOT NULL UNIQUE,
            shopify_code_id VARCHAR,
            campaign_id INTEGER,
            used BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )""",
    ]
    # Each migration gets its own transaction — a failure in one never aborts the rest
    for sql in migrations:
        with Session(engine) as session:
            try:
                session.execute(text(sql))
                session.commit()
            except Exception:
                session.rollback()


def get_session():
    with Session(engine) as session:
        yield session
