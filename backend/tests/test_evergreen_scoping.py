"""app/services/evergreen_engine.py — el motor diario de evergreen tenía que
matchear contactos SOLO de la tienda dueña de cada campaña. Antes del fix, el
loop de run_evergreen_campaigns hace `break` tras la primera campaña que pasa
los filtros de segmento/apertura/enrollment (sin importar la tienda) — así
que una tienda con una campaña evergreen "gana" y le manda contenido a
contactos de OTRAS tiendas. Este archivo reproduce exactamente ese escenario
en SQLite."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from app.models.shop import Shop
from app.models.contact import Contact
from app.models.evergreen import EvergreenCampaign, EvergreenEnrollment, EvergreenSend
from app.models.campaign import CampaignSend
from app.models.automation import AutomationRun
from app.services import evergreen_engine

from conftest import make_shop


@pytest.fixture()
def evergreen_sqlite_engine():
    # StaticPool: misma razón que sqlite_engine en conftest.py — una sola
    # conexión compartida para que la tabla no desaparezca entre checkouts.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(
        engine,
        tables=[
            Shop.__table__,
            Contact.__table__,
            EvergreenCampaign.__table__,
            EvergreenEnrollment.__table__,
            EvergreenSend.__table__,
            CampaignSend.__table__,
            AutomationRun.__table__,
        ],
    )
    yield engine
    engine.dispose()


@pytest.fixture()
def evergreen_db_session(evergreen_sqlite_engine):
    with Session(evergreen_sqlite_engine) as session:
        yield session


@pytest.fixture()
def patched_evergreen_engine(evergreen_sqlite_engine, monkeypatch):
    """run_evergreen_campaigns abre sus propias Session(engine) usando el
    `engine` importado a nivel de módulo en evergreen_engine.py — hay que
    parchear ese atributo, no app.database.engine."""
    monkeypatch.setattr(evergreen_engine, "engine", evergreen_sqlite_engine)
    return evergreen_sqlite_engine


def make_contact(session: Session, shop: Shop, **overrides) -> Contact:
    defaults = dict(
        shop_id=shop.id,
        email=f"contact-{datetime.utcnow().timestamp()}@example.com",
        opted_in=True,
    )
    defaults.update(overrides)
    contact = Contact(**defaults)
    session.add(contact)
    session.commit()
    session.refresh(contact)
    return contact


def make_evergreen(session: Session, shop: Shop, **overrides) -> EvergreenCampaign:
    defaults = dict(
        shop_id=shop.id,
        name=f"Evergreen {shop.id}",
        subject="Asunto",
        template_id=1,
        status="active",
        min_days_inactive=0,
    )
    defaults.update(overrides)
    eg = EvergreenCampaign(**defaults)
    session.add(eg)
    session.commit()
    session.refresh(eg)
    return eg


def test_evergreen_does_not_leak_across_shops(
    patched_evergreen_engine, evergreen_db_session, monkeypatch
):
    """El caso real que produjo el bug: una campaña de la tienda B tiene un id
    más chico (se evalúa primero) que la campaña de la tienda A. Un contacto
    de la tienda A no debe recibir el contenido de la campaña de la tienda B."""
    shop_a = make_shop(evergreen_db_session, name="Tienda A")
    shop_b = make_shop(evergreen_db_session, name="Tienda B")

    eg_b = make_evergreen(evergreen_db_session, shop_b)  # id más chico, se evalúa primero
    eg_a = make_evergreen(evergreen_db_session, shop_a)

    contact_a = make_contact(evergreen_db_session, shop_a)

    sent_to = []

    def _fake_send_step(session, eg, contact, step_cfg, *, step_number, enrollment_id=None):
        sent_to.append((eg.id, contact.id))
        return EvergreenSend(
            evergreen_id=eg.id, contact_id=contact.id, step_number=step_number,
            status="sent", sent_at=datetime.utcnow(),
        )

    monkeypatch.setattr(evergreen_engine, "_send_evergreen_step", _fake_send_step)

    stats = evergreen_engine.run_evergreen_campaigns(force=True)

    assert stats["sent"] == 1
    assert sent_to == [(eg_a.id, contact_a.id)], (
        "el contacto de la tienda A recibió (o se saltó) la campaña de la tienda B"
    )


def test_evergreen_matches_each_contact_to_its_own_shop(
    patched_evergreen_engine, evergreen_db_session, monkeypatch
):
    shop_a = make_shop(evergreen_db_session, name="Tienda A")
    shop_b = make_shop(evergreen_db_session, name="Tienda B")

    eg_a = make_evergreen(evergreen_db_session, shop_a)
    eg_b = make_evergreen(evergreen_db_session, shop_b)

    contact_a = make_contact(evergreen_db_session, shop_a)
    contact_b = make_contact(evergreen_db_session, shop_b)

    sent_to = []

    def _fake_send_step(session, eg, contact, step_cfg, *, step_number, enrollment_id=None):
        sent_to.append((eg.id, contact.id))
        return EvergreenSend(
            evergreen_id=eg.id, contact_id=contact.id, step_number=step_number,
            status="sent", sent_at=datetime.utcnow(),
        )

    monkeypatch.setattr(evergreen_engine, "_send_evergreen_step", _fake_send_step)

    stats = evergreen_engine.run_evergreen_campaigns(force=True)

    assert stats["sent"] == 2
    assert set(sent_to) == {(eg_a.id, contact_a.id), (eg_b.id, contact_b.id)}


def test_evergreen_skips_opted_out_contact(patched_evergreen_engine, evergreen_db_session, monkeypatch):
    shop_a = make_shop(evergreen_db_session, name="Tienda A")
    make_evergreen(evergreen_db_session, shop_a)
    make_contact(evergreen_db_session, shop_a, opted_in=False)

    sent_to = []
    monkeypatch.setattr(
        evergreen_engine,
        "_send_evergreen_step",
        lambda *a, **k: sent_to.append(1) or None,
    )

    stats = evergreen_engine.run_evergreen_campaigns(force=True)
    assert stats["sent"] == 0
    assert sent_to == []
