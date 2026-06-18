"""
kok
Adds new columns to existing tables in Railway DB.
Safe to run multiple times (uses IF NOT EXISTS logic).
"""
import sys, psycopg2
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = "postgresql://postgres:mcxQvhpGaatBzcZNCbVqnGWGBjQpCNYJ@turntable.proxy.rlwy.net:48129/railway"
conn = psycopg2.connect(DB)
cur = conn.cursor()

migrations = [
    # campaigns.template_id — make nullable so templates can be deleted independently
    "ALTER TABLE campaigns ALTER COLUMN template_id DROP NOT NULL",
    # contacts — new profile columns
    "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS birthday DATE",
    "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS notes TEXT",
    "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS custom_fields JSONB",
    "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS location VARCHAR",
    # signup_forms — custom fields + html override + coupon
    "ALTER TABLE signup_forms ADD COLUMN IF NOT EXISTS custom_form_fields JSONB",
    "ALTER TABLE signup_forms ADD COLUMN IF NOT EXISTS html_override TEXT",
    "ALTER TABLE signup_forms ADD COLUMN IF NOT EXISTS coupon_code VARCHAR",
    # form_submissions — extra data from custom fields
    "ALTER TABLE form_submissions ADD COLUMN IF NOT EXISTS extra_data JSONB",
    # automations + automation_runs (new tables — create if not exist)
    """CREATE TABLE IF NOT EXISTS automations (
        id SERIAL PRIMARY KEY,
        name VARCHAR NOT NULL,
        trigger_type VARCHAR NOT NULL,
        trigger_config JSONB,
        template_id INTEGER REFERENCES templates(id),
        subject VARCHAR NOT NULL,
        status VARCHAR DEFAULT 'active',
        created_by INTEGER REFERENCES users(id),
        created_at TIMESTAMP,
        updated_at TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS automation_runs (
        id SERIAL PRIMARY KEY,
        automation_id INTEGER REFERENCES automations(id),
        contact_id INTEGER REFERENCES contacts(id),
        contact_email VARCHAR NOT NULL,
        trigger_key VARCHAR NOT NULL,
        status VARCHAR DEFAULT 'sent',
        triggered_at TIMESTAMP,
        executed_at TIMESTAMP,
        resend_id VARCHAR,
        error VARCHAR
    )""",
    # signup_forms (ensure new table exists)
    """CREATE TABLE IF NOT EXISTS signup_forms (
        id SERIAL PRIMARY KEY,
        name VARCHAR NOT NULL,
        title VARCHAR NOT NULL,
        description TEXT,
        button_text VARCHAR DEFAULT 'Suscribirme',
        success_message VARCHAR DEFAULT '¡Gracias! Pronto recibirás noticias nuestras.',
        collect_name BOOLEAN DEFAULT TRUE,
        collect_phone BOOLEAN DEFAULT FALSE,
        popup_trigger VARCHAR DEFAULT 'delay',
        popup_delay_seconds INTEGER DEFAULT 5,
        popup_scroll_pct INTEGER DEFAULT 50,
        custom_form_fields JSONB,
        html_override TEXT,
        status VARCHAR DEFAULT 'active',
        created_by INTEGER REFERENCES users(id),
        created_at TIMESTAMP,
        updated_at TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS form_submissions (
        id SERIAL PRIMARY KEY,
        form_id INTEGER REFERENCES signup_forms(id),
        email VARCHAR NOT NULL,
        name VARCHAR,
        phone VARCHAR,
        source_url VARCHAR,
        extra_data JSONB,
        created_at TIMESTAMP
    )""",
]

for sql in migrations:
    try:
        cur.execute(sql)
        label = sql.strip().split("\n")[0][:80]
        print(f"  OK: {label}")
    except Exception as e:
        print(f"  ERR: {e}")
        conn.rollback()
        continue

conn.commit()
conn.close()
print("\nMigracion completada.")
