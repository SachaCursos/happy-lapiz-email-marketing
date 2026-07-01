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
        "ALTER TABLE form_submissions ADD COLUMN IF NOT EXISTS relacion_regalado2 VARCHAR",
        "ALTER TABLE form_submissions ADD COLUMN IF NOT EXISTS nombre_regalado2 VARCHAR",
        "ALTER TABLE form_submissions ADD COLUMN IF NOT EXISTS fecha_nacimiento_regalado2 VARCHAR",
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
        """CREATE TABLE IF NOT EXISTS evergreen_campaigns (
            id SERIAL PRIMARY KEY,
            name VARCHAR NOT NULL,
            subject VARCHAR NOT NULL,
            preview_text VARCHAR,
            template_id INTEGER NOT NULL REFERENCES templates(id),
            segment_id INTEGER REFERENCES segments(id),
            exclude_segment_ids JSONB,
            sort_order INTEGER NOT NULL DEFAULT 0,
            status VARCHAR NOT NULL DEFAULT 'active',
            allow_resend BOOLEAN NOT NULL DEFAULT FALSE,
            resend_after_days INTEGER,
            min_days_inactive INTEGER NOT NULL DEFAULT 15,
            require_open_in_last_n INTEGER NOT NULL DEFAULT 5,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS evergreen_sends (
            id SERIAL PRIMARY KEY,
            evergreen_id INTEGER NOT NULL REFERENCES evergreen_campaigns(id),
            contact_id INTEGER NOT NULL REFERENCES contacts(id),
            resend_id VARCHAR,
            status VARCHAR NOT NULL DEFAULT 'queued',
            sent_at TIMESTAMP,
            delivered_at TIMESTAMP,
            opened_at TIMESTAMP,
            clicked_at TIMESTAMP,
            bounced_at TIMESTAMP
        )""",
        "CREATE INDEX IF NOT EXISTS idx_evergreen_sends_evergreen ON evergreen_sends(evergreen_id)",
        "CREATE INDEX IF NOT EXISTS idx_evergreen_sends_contact ON evergreen_sends(contact_id)",
        "CREATE INDEX IF NOT EXISTS idx_evergreen_sends_resend ON evergreen_sends(resend_id)",
        "ALTER TABLE evergreen_campaigns ADD COLUMN IF NOT EXISTS steps JSONB",
        "ALTER TABLE evergreen_sends ADD COLUMN IF NOT EXISTS step_number INTEGER NOT NULL DEFAULT 1",
        "ALTER TABLE evergreen_sends ADD COLUMN IF NOT EXISTS enrollment_id INTEGER",
        """CREATE TABLE IF NOT EXISTS evergreen_enrollments (
            id SERIAL PRIMARY KEY,
            evergreen_id INTEGER NOT NULL REFERENCES evergreen_campaigns(id),
            contact_id INTEGER NOT NULL REFERENCES contacts(id),
            started_at TIMESTAMP NOT NULL DEFAULT NOW(),
            next_step INTEGER NOT NULL DEFAULT 2,
            next_send_at TIMESTAMP NOT NULL,
            status VARCHAR NOT NULL DEFAULT 'active'
        )""",
        "CREATE INDEX IF NOT EXISTS idx_evergreen_enrollments_due ON evergreen_enrollments(status, next_send_at)",
        "ALTER TABLE shopify_products ADD COLUMN IF NOT EXISTS inventory_total INTEGER NOT NULL DEFAULT 0",
        """DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'shopify_products' AND column_name = 'id'
            ) AND pg_get_serial_sequence('shopify_products', 'id') IS NULL THEN
                CREATE SEQUENCE IF NOT EXISTS shopify_products_id_seq;
                ALTER TABLE shopify_products
                    ALTER COLUMN id SET DEFAULT nextval('shopify_products_id_seq');
                ALTER SEQUENCE shopify_products_id_seq OWNED BY shopify_products.id;
            END IF;
        END $$""",
        """CREATE TABLE IF NOT EXISTS automation_calendar_state (
            automation_id INTEGER NOT NULL,
            month_key VARCHAR(7) NOT NULL,
            rotation_index INTEGER NOT NULL DEFAULT 0,
            product_shopify_id BIGINT,
            product_json JSONB,
            enrolled_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            PRIMARY KEY (automation_id, month_key)
        )""",
        """CREATE TABLE IF NOT EXISTS dynamic_html_blocks (
            block_key VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL,
            description TEXT,
            html_template TEXT NOT NULL,
            design_config JSONB,
            sample_products JSONB,
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )""",
        "ALTER TABLE dynamic_html_blocks ADD COLUMN IF NOT EXISTS design_config JSONB",
        """DELETE FROM campaign_sends q
           WHERE q.status = 'queued'
             AND EXISTS (
               SELECT 1 FROM campaign_sends ok
               WHERE ok.campaign_id = q.campaign_id
                 AND ok.contact_id = q.contact_id
                 AND ok.status IN (
                   'sent','delivered','opened','clicked','bounced','complained'
                 )
                 AND ok.id <> q.id
             )""",
        """DELETE FROM campaign_sends cs
           WHERE cs.id IN (
             SELECT id FROM (
               SELECT id,
                 ROW_NUMBER() OVER (
                   PARTITION BY campaign_id, contact_id
                   ORDER BY
                     CASE status
                       WHEN 'delivered' THEN 1
                       WHEN 'opened' THEN 2
                       WHEN 'clicked' THEN 3
                       WHEN 'sent' THEN 4
                       WHEN 'bounced' THEN 5
                       WHEN 'complained' THEN 6
                       WHEN 'failed' THEN 7
                       ELSE 8
                     END,
                     sent_at DESC NULLS LAST,
                     id DESC
                 ) AS rn
               FROM campaign_sends
             ) ranked
             WHERE rn > 1
           )""",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_campaign_sends_campaign_contact ON campaign_sends (campaign_id, contact_id)",
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
