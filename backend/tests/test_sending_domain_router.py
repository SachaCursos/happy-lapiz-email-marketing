"""app/routers/sending_domain.py — endpoints end-to-end vía FastAPI TestClient,
con SQLite en vez de Postgres y el cliente SES mockeado (el flujo real contra
AWS ya se probó a mano esta sesión, en staging y producción)."""
import pytest
from fastapi.testclient import TestClient

from app.core.deps import get_current_shop, require_admin
from app.database import get_session
from app.main import app
from app.services import ses_domain

from conftest import make_shop, make_user


@pytest.fixture()
def client_for_shop(db_session, patched_engine, monkeypatch):
    """Devuelve (client, shop) con las dependencias de auth/DB reemplazadas
    por la tienda de prueba — sin pasar por login real."""
    shop = make_shop(db_session, name="Mi Tienda", email_provider="ses")
    admin = make_user(db_session, shop, role="admin")

    def _get_session_override():
        yield db_session

    app.dependency_overrides[get_session] = _get_session_override
    app.dependency_overrides[get_current_shop] = lambda: shop
    app.dependency_overrides[require_admin] = lambda: admin

    client = TestClient(app)
    yield client, shop

    app.dependency_overrides.clear()


def test_get_with_no_domain_configured(client_for_shop):
    client, _shop = client_for_shop
    resp = client.get("/api/settings/sending-domain")
    assert resp.status_code == 200
    assert resp.json() == {"domain": None, "verified": False, "dns_records": []}


def test_create_rejects_invalid_domain(client_for_shop):
    client, _shop = client_for_shop
    resp = client.post("/api/settings/sending-domain", json={"domain": "no es un dominio"})
    assert resp.status_code == 400


def test_create_saves_domain_and_returns_dns_records(client_for_shop, db_session, monkeypatch):
    client, shop = client_for_shop
    monkeypatch.setattr(
        ses_domain,
        "create_domain_identity",
        lambda domain: [{"type": "CNAME", "name": f"tok._domainkey.{domain}", "value": "tok.dkim.amazonses.com"}],
    )

    resp = client.post("/api/settings/sending-domain", json={"domain": "MiTienda.CL"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["domain"] == "mitienda.cl", "el dominio se normaliza a minúsculas"
    assert body["verified"] is False
    assert len(body["dns_records"]) == 1

    db_session.refresh(shop)
    assert shop.sending_domain == "mitienda.cl"
    assert shop.sending_domain_verified is False


def test_create_surfaces_ses_errors_as_502(client_for_shop, monkeypatch):
    client, _shop = client_for_shop

    def _boom(domain):
        raise RuntimeError("AccessDeniedException")

    monkeypatch.setattr(ses_domain, "create_domain_identity", _boom)

    resp = client.post("/api/settings/sending-domain", json={"domain": "mitienda.cl"})
    assert resp.status_code == 502


def test_verify_updates_verified_flag(client_for_shop, db_session, monkeypatch):
    client, shop = client_for_shop
    shop.sending_domain = "mitienda.cl"
    shop.sending_domain_verified = False
    db_session.add(shop)
    db_session.commit()

    monkeypatch.setattr(
        ses_domain,
        "get_domain_status",
        lambda domain: {"verified": True, "dkim_status": "SUCCESS", "dns_records": []},
    )

    resp = client.post("/api/settings/sending-domain/verify")

    assert resp.status_code == 200
    assert resp.json()["verified"] is True
    db_session.refresh(shop)
    assert shop.sending_domain_verified is True


def test_verify_without_domain_configured_is_400(client_for_shop):
    client, _shop = client_for_shop
    resp = client.post("/api/settings/sending-domain/verify")
    assert resp.status_code == 400


def test_delete_clears_shop_fields(client_for_shop, db_session, monkeypatch):
    client, shop = client_for_shop
    shop.sending_domain = "mitienda.cl"
    shop.sending_domain_verified = True
    db_session.add(shop)
    db_session.commit()

    monkeypatch.setattr(ses_domain, "delete_domain_identity", lambda domain: None)

    resp = client.delete("/api/settings/sending-domain")

    assert resp.status_code == 200
    assert resp.json() == {"domain": None, "verified": False, "dns_records": []}
    db_session.refresh(shop)
    assert shop.sending_domain is None
    assert shop.sending_domain_verified is False


def test_delete_with_no_domain_is_a_noop(client_for_shop):
    client, _shop = client_for_shop
    resp = client.delete("/api/settings/sending-domain")
    assert resp.status_code == 200
    assert resp.json()["domain"] is None
