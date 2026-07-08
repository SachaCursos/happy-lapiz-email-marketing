import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.config import settings
from app.database import engine
from sqlmodel import SQLModel

# Importar todos los modelos para que su metadata quede registrada
import app.models.shop            # noqa
import app.models.user            # noqa
import app.models.contact         # noqa
import app.models.segment         # noqa
import app.models.template        # noqa
import app.models.campaign        # noqa
import app.models.automation      # noqa
import app.models.form            # noqa
import app.models.gift_recipient  # noqa

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine
    # On a brand-new database (e.g. a fresh staging Postgres), the shop_id
    # migrations below assume the base ORM tables already exist — which is
    # normally true because the app creates them on startup, but Alembic
    # runs before the app does. create_all is a no-op for tables that
    # already exist (production), and fills in the rest here (fresh DBs).
    SQLModel.metadata.create_all(connectable)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
