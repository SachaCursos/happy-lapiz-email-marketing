"""Fixtures compartidas. Usa SQLite en memoria — sirve para todo lo que
solo hace lecturas/escrituras simples de ORM (Shop, User), pero NO para
los endpoints que arman SQL crudo con funciones específicas de Postgres
(date_trunc, ILIKE, JSONB, to_regclass) — ver la nota en test_analytics
y test_email_log sobre qué queda fuera del alcance de esta suite."""
from datetime import datetime

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from app.models.shop import Shop
from app.models.user import User


@pytest.fixture()
def sqlite_engine():
    # StaticPool: una sola conexión compartida — sin esto cada checkout del
    # pool abre una base ":memory:" nueva y vacía (así es SQLite, no un bug
    # nuestro), y el TestClient (que corre el endpoint en otro hilo) ve
    # "no such table".
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine, tables=[Shop.__table__, User.__table__])
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(sqlite_engine):
    with Session(sqlite_engine) as session:
        yield session


@pytest.fixture()
def patched_engine(sqlite_engine, monkeypatch):
    """email_provider.py hace `from app.database import engine` adentro de
    cada función — parcheamos el atributo del módulo para que apunte a
    SQLite en vez de a Postgres real."""
    import app.database as database_module

    monkeypatch.setattr(database_module, "engine", sqlite_engine)
    return sqlite_engine


def make_shop(session: Session, **overrides) -> Shop:
    defaults = dict(
        shopify_domain=f"test-{datetime.utcnow().timestamp()}.myshopify.com",
        access_token_encrypted="enc-token",
        status="active",
    )
    defaults.update(overrides)
    shop = Shop(**defaults)
    session.add(shop)
    session.commit()
    session.refresh(shop)
    return shop


def make_user(session: Session, shop: Shop, **overrides) -> User:
    defaults = dict(
        email=f"user-{datetime.utcnow().timestamp()}@example.com",
        name="Test User",
        password_hash="x",
        role="admin",
        shop_id=shop.id,
    )
    defaults.update(overrides)
    user = User(**defaults)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
