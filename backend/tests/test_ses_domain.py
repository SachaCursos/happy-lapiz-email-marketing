"""app/services/ses_domain.py — construcción de los registros DNS y parseo
de las respuestas de SES. El cliente boto3 real se mockea acá (nunca toca
AWS) — el flujo real contra SES ya se probó a mano en staging/producción
esta sesión (create/get/delete reales, con el dominio de prueba
envios-test-claude-session.cl)."""
from unittest.mock import MagicMock

from app.services import ses_domain


def test_dkim_records_builds_three_cname_entries():
    records = ses_domain._dkim_records("midominio.cl", ["tok1", "tok2", "tok3"])
    assert len(records) == 3
    assert records[0] == {
        "type": "CNAME",
        "name": "tok1._domainkey.midominio.cl",
        "value": "tok1.dkim.amazonses.com",
    }
    assert all(r["type"] == "CNAME" for r in records)
    assert [r["name"] for r in records] == [
        "tok1._domainkey.midominio.cl",
        "tok2._domainkey.midominio.cl",
        "tok3._domainkey.midominio.cl",
    ]


def test_dkim_records_empty_tokens_returns_empty_list():
    assert ses_domain._dkim_records("midominio.cl", []) == []


def test_create_domain_identity_returns_dns_records(monkeypatch):
    fake_client = MagicMock()
    fake_client.create_email_identity.return_value = {
        "DkimAttributes": {"Tokens": ["aaa", "bbb", "ccc"]}
    }
    monkeypatch.setattr(ses_domain, "_client", lambda: fake_client)

    records = ses_domain.create_domain_identity("midominio.cl")

    fake_client.create_email_identity.assert_called_once_with(EmailIdentity="midominio.cl")
    assert len(records) == 3
    assert records[0]["name"] == "aaa._domainkey.midominio.cl"


def test_get_domain_status_pending(monkeypatch):
    fake_client = MagicMock()
    fake_client.get_email_identity.return_value = {
        "DkimAttributes": {"Status": "PENDING", "Tokens": ["aaa", "bbb", "ccc"]}
    }
    monkeypatch.setattr(ses_domain, "_client", lambda: fake_client)

    status = ses_domain.get_domain_status("midominio.cl")

    assert status["verified"] is False
    assert status["dkim_status"] == "PENDING"
    assert len(status["dns_records"]) == 3


def test_get_domain_status_verified(monkeypatch):
    fake_client = MagicMock()
    fake_client.get_email_identity.return_value = {
        "DkimAttributes": {"Status": "SUCCESS", "Tokens": ["aaa", "bbb", "ccc"]}
    }
    monkeypatch.setattr(ses_domain, "_client", lambda: fake_client)

    status = ses_domain.get_domain_status("midominio.cl")

    assert status["verified"] is True
    assert status["dkim_status"] == "SUCCESS"


def test_get_domain_status_defaults_to_not_started_when_missing(monkeypatch):
    fake_client = MagicMock()
    fake_client.get_email_identity.return_value = {}
    monkeypatch.setattr(ses_domain, "_client", lambda: fake_client)

    status = ses_domain.get_domain_status("midominio.cl")

    assert status["verified"] is False
    assert status["dkim_status"] == "NOT_STARTED"
    assert status["dns_records"] == []


def test_delete_domain_identity_calls_ses(monkeypatch):
    fake_client = MagicMock()
    monkeypatch.setattr(ses_domain, "_client", lambda: fake_client)

    ses_domain.delete_domain_identity("midominio.cl")

    fake_client.delete_email_identity.assert_called_once_with(EmailIdentity="midominio.cl")
