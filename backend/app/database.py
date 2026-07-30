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
        "ALTER TABLE campaign_sends ADD COLUMN IF NOT EXISTS variant_sent VARCHAR",
        "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS variants JSONB",
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
            shop_id INTEGER,
            shopify_id BIGINT NOT NULL,
            title VARCHAR NOT NULL,
            handle VARCHAR,
            product_type VARCHAR,
            tags TEXT,
            vendor VARCHAR,
            image_url TEXT,
            imagen_url TEXT,
            price NUMERIC(10,2),
            precio_min NUMERIC(10,2),
            raw JSONB,
            status VARCHAR NOT NULL DEFAULT 'active',
            synced_at TIMESTAMP NOT NULL DEFAULT NOW(),
            edad_recomendada VARCHAR,
            inventory_total INTEGER NOT NULL DEFAULT 0
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
        """CREATE TABLE IF NOT EXISTS form_views (
            id SERIAL PRIMARY KEY,
            form_id INTEGER NOT NULL REFERENCES signup_forms(id),
            email VARCHAR,
            source VARCHAR NOT NULL DEFAULT 'page',
            viewed_at TIMESTAMP NOT NULL DEFAULT NOW()
        )""",
        "CREATE INDEX IF NOT EXISTS idx_form_views_form_id ON form_views(form_id)",
        "CREATE INDEX IF NOT EXISTS idx_form_views_form_email ON form_views(form_id, email)",
        "DELETE FROM form_views WHERE source = 'backfill'",
        "DELETE FROM form_views WHERE source = 'submit'",
        "ALTER TABLE signup_forms ADD COLUMN IF NOT EXISTS stats_since TIMESTAMP",
        "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS segment_ids JSONB",
        "ALTER TABLE campaigns ALTER COLUMN segment_id DROP NOT NULL",
        """CREATE TABLE IF NOT EXISTS _internal_flags (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT ''
        )""",
        """DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM _internal_flags WHERE key = 'form_stats_v2_reset') THEN
            DELETE FROM form_views;
            UPDATE signup_forms SET stats_since = NOW();
            INSERT INTO _internal_flags (key, value) VALUES ('form_stats_v2_reset', 'done');
          END IF;
        END $$""",
        """CREATE TABLE IF NOT EXISTS dynamic_criteria (
            criteria_key VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL,
            description TEXT,
            variables JSONB NOT NULL DEFAULT '[]',
            config JSONB NOT NULL DEFAULT '{}',
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )""",
        # contacts.family_role — madre|padre|abuela|abuelo|tia|tio|…
        "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS family_role VARCHAR",
        "CREATE INDEX IF NOT EXISTS idx_contacts_family_role ON contacts(family_role)",
        # shop_id for every raw-SQL table above, plus shopify_orders/shopify_events/
        # shopify_checkouts/carritos_abandonados — those four aren't created anywhere
        # in this repo (they're populated by the separate ETL pipeline), so this list
        # can't assume they exist yet. ALTER TABLE IF EXISTS is a safe no-op until
        # they show up; this block then self-heals them on the next app restart
        # instead of depending on deploy ordering between the ETL and this app.
        "ALTER TABLE IF EXISTS shopify_products ADD COLUMN IF NOT EXISTS shop_id INTEGER",
        "CREATE INDEX IF NOT EXISTS ix_shopify_products_shop_id ON shopify_products (shop_id)",
        "ALTER TABLE IF EXISTS coupon_campaigns ADD COLUMN IF NOT EXISTS shop_id INTEGER",
        "CREATE INDEX IF NOT EXISTS ix_coupon_campaigns_shop_id ON coupon_campaigns (shop_id)",
        "ALTER TABLE IF EXISTS coupon_sends ADD COLUMN IF NOT EXISTS shop_id INTEGER",
        "CREATE INDEX IF NOT EXISTS ix_coupon_sends_shop_id ON coupon_sends (shop_id)",
        "ALTER TABLE IF EXISTS shopify_orders ADD COLUMN IF NOT EXISTS shop_id INTEGER",
        "CREATE INDEX IF NOT EXISTS ix_shopify_orders_shop_id ON shopify_orders (shop_id)",
        "ALTER TABLE IF EXISTS shopify_events ADD COLUMN IF NOT EXISTS shop_id INTEGER",
        "CREATE INDEX IF NOT EXISTS ix_shopify_events_shop_id ON shopify_events (shop_id)",
        "ALTER TABLE IF EXISTS shopify_checkouts ADD COLUMN IF NOT EXISTS shop_id INTEGER",
        "CREATE INDEX IF NOT EXISTS ix_shopify_checkouts_shop_id ON shopify_checkouts (shop_id)",
        "ALTER TABLE IF EXISTS carritos_abandonados ADD COLUMN IF NOT EXISTS shop_id INTEGER",
        "CREATE INDEX IF NOT EXISTS ix_carritos_abandonados_shop_id ON carritos_abandonados (shop_id)",
        "ALTER TABLE IF EXISTS shops ADD COLUMN IF NOT EXISTS name VARCHAR",
        # plantillas_de_la_marca predates multi-tenancy: on environments where it
        # already existed (e.g. production, with Happy Lápiz's real colors/logos)
        # it has no shop_id column yet — SQLModel.metadata.create_all above only
        # creates the table where it's missing (e.g. staging), it doesn't alter an
        # existing one. ALTER TABLE IF EXISTS covers both cases.
        "ALTER TABLE IF EXISTS plantillas_de_la_marca ADD COLUMN IF NOT EXISTS shop_id INTEGER",
        "CREATE INDEX IF NOT EXISTS ix_plantillas_de_la_marca_shop_id ON plantillas_de_la_marca (shop_id)",
        # Backfill: any pre-multi-tenant rows (shop_id IS NULL) are Happy Lápiz's
        # own brand assets — assign them to that shop by domain instead of a
        # hardcoded id, so this works the same on any environment.
        """UPDATE plantillas_de_la_marca SET shop_id = (
               SELECT id FROM shops WHERE shopify_domain = 'happy-lapiz.myshopify.com' LIMIT 1
           ) WHERE shop_id IS NULL""",
        # AWS SES migration: opt-in provider per shop (NULL = usa el default global
        # settings.EMAIL_PROVIDER) + qué proveedor mandó cada envío ya realizado.
        "ALTER TABLE shops ADD COLUMN IF NOT EXISTS email_provider VARCHAR",
        "ALTER TABLE campaign_sends ADD COLUMN IF NOT EXISTS send_provider VARCHAR",
        "ALTER TABLE automation_runs ADD COLUMN IF NOT EXISTS send_provider VARCHAR",
        "ALTER TABLE evergreen_sends ADD COLUMN IF NOT EXISTS send_provider VARCHAR",
        # contacts.gender/birthday/notes predate this staging DB's table creation —
        # found crashing every real campaign send (get_campaign_recipients selects
        # every Contact column) while validating the SES migration above.
        "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS gender VARCHAR",
        "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS birthday DATE",
        "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS notes VARCHAR",
        # Visor de correos enviados: snapshot del asunto/HTML realmente mandado en
        # cada envío, para poder verlo después sin depender de que la plantilla no
        # haya cambiado. NULL en filas históricas anteriores a esto.
        "ALTER TABLE campaign_sends ADD COLUMN IF NOT EXISTS subject VARCHAR",
        "ALTER TABLE campaign_sends ADD COLUMN IF NOT EXISTS html_snapshot TEXT",
        "ALTER TABLE automation_runs ADD COLUMN IF NOT EXISTS subject VARCHAR",
        "ALTER TABLE automation_runs ADD COLUMN IF NOT EXISTS html_snapshot TEXT",
        "ALTER TABLE evergreen_sends ADD COLUMN IF NOT EXISTS subject VARCHAR",
        "ALTER TABLE evergreen_sends ADD COLUMN IF NOT EXISTS html_snapshot TEXT",
        # campaign_sends.shop_id / automation_runs.shop_id existían como columna pero
        # nunca se completaban al crear la fila (_ensure_send_records / process_step
        # solo pasaban campaign_id/automation_id) — quedaban NULL en TODOS los envíos
        # históricos. Encontrado construyendo el visor de correos enviados, que
        # necesita poder filtrar por tienda directamente sobre estas tablas.
        """UPDATE campaign_sends cs SET shop_id = c.shop_id
           FROM campaigns c WHERE cs.campaign_id = c.id AND cs.shop_id IS NULL""",
        """UPDATE automation_runs ar SET shop_id = a.shop_id
           FROM automations a WHERE ar.automation_id = a.id AND ar.shop_id IS NULL""",
        # email_provider.resolve_from_email() usa Shop.display_name() (que cae a
        # shopify_domain si name es NULL) como nombre del remitente — sin esto,
        # Happy Lápiz mandaría como "happy-lapiz" en vez de "Happy Lápiz".
        """UPDATE shops SET name = 'Happy Lápiz'
           WHERE shopify_domain = 'happy-lapiz.myshopify.com' AND name IS NULL""",
        # Dominios de envío propios por tienda (SES) — ver ses_domain.py.
        "ALTER TABLE shops ADD COLUMN IF NOT EXISTS sending_domain VARCHAR",
        "ALTER TABLE shops ADD COLUMN IF NOT EXISTS sending_domain_verified BOOLEAN NOT NULL DEFAULT false",
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
