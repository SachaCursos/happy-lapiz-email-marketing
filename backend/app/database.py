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
    """Add columns that were added after initial table creation."""
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
        # Coupon tables — created here so they exist even after a clean deploy
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
    with Session(engine) as session:
        for sql in migrations:
            try:
                session.execute(text(sql))
            except Exception:
                pass
        session.commit()


def get_session():
    with Session(engine) as session:
        yield session
