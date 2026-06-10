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
        "ALTER TABLE signupform ADD COLUMN IF NOT EXISTS design_config JSONB",
        "ALTER TABLE signupform ADD COLUMN IF NOT EXISTS steps_config JSONB",
        "ALTER TABLE signupform ADD COLUMN IF NOT EXISTS coupon_campaign_id INTEGER",
        "ALTER TABLE signupform ADD COLUMN IF NOT EXISTS coupon_automation_id INTEGER",
        "ALTER TABLE formsubmission ADD COLUMN IF NOT EXISTS coupon_code VARCHAR",
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
