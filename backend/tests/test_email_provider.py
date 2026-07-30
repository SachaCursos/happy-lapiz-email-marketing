"""app/services/email_provider.py — resolución de proveedor y remitente por
tienda. Cubre el comportamiento agregado esta sesión: nombre del remitente
por tienda (resolve_from_email) y dominio propio verificado."""
from email.header import decode_header
from email.utils import parseaddr


def _decoded_name(raw_name: str) -> str:
    parts = decode_header(raw_name)
    return "".join(
        chunk.decode(enc or "ascii") if isinstance(chunk, bytes) else chunk
        for chunk, enc in parts
    )

from app.core.config import settings
from app.services.email_provider import (
    apply_email_override,
    resolve_from_email,
    resolve_provider,
)

from conftest import make_shop


# ── apply_email_override ────────────────────────────────────────────────────

def test_apply_email_override_noop_when_unset(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_OVERRIDE_TO", "")
    to, subject = apply_email_override(["real@cliente.cl"], "Asunto")
    assert to == ["real@cliente.cl"]
    assert subject == "Asunto"


def test_apply_email_override_redirects_and_tags_subject(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_OVERRIDE_TO", "tester@ejemplo.com")
    to, subject = apply_email_override(["real@cliente.cl", "otro@cliente.cl"], "Asunto")
    assert to == ["tester@ejemplo.com"]
    assert subject == "[real@cliente.cl, otro@cliente.cl] Asunto"


# ── resolve_provider ─────────────────────────────────────────────────────────

def test_resolve_provider_no_shop_id_uses_global_default(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "resend")
    assert resolve_provider(None) == "resend"


def test_resolve_provider_shop_without_flag_falls_back_to_global(patched_engine, db_session, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "resend")
    shop = make_shop(db_session, email_provider=None)
    assert resolve_provider(shop.id) == "resend"


def test_resolve_provider_shop_flag_overrides_global(patched_engine, db_session, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "resend")
    shop = make_shop(db_session, email_provider="ses")
    assert resolve_provider(shop.id) == "ses"


def test_resolve_provider_missing_shop_falls_back_to_global(patched_engine, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "resend")
    assert resolve_provider(999999) == "resend"


# ── resolve_from_email ───────────────────────────────────────────────────────

def test_resolve_from_email_no_shop_id_returns_unchanged():
    original = "Happy Lápiz <hola@happylapiz.cl>"
    assert resolve_from_email(None, original) == original


def test_resolve_from_email_uses_shop_display_name_with_shared_address(patched_engine, db_session):
    shop = make_shop(db_session, name="test_store777")
    result = resolve_from_email(shop.id, "Happy Lápiz <hola@happylapiz.cl>")
    name, addr = parseaddr(result)
    assert name == "test_store777"
    assert addr == "hola@happylapiz.cl"


def test_resolve_from_email_falls_back_to_shopify_subdomain_when_name_unset(patched_engine, db_session):
    shop = make_shop(db_session, name=None, shopify_domain="acme-store.myshopify.com")
    result = resolve_from_email(shop.id, "Happy Lápiz <hola@happylapiz.cl>")
    name, addr = parseaddr(result)
    assert name == "acme-store"
    assert addr == "hola@happylapiz.cl"


def test_resolve_from_email_preserves_accented_display_name(patched_engine, db_session):
    """Regresión: un nombre con tilde no debe romper la dirección (bug real
    encontrado esta sesión — RFC-2047 codificaba From completo, no solo el
    nombre, y SES lo rechazaba con 'Missing final @domain')."""
    shop = make_shop(db_session, name="Happy Lápiz")
    result = resolve_from_email(shop.id, "Happy Lápiz <hola@happylapiz.cl>")
    name, addr = parseaddr(result)
    # El nombre queda RFC-2047 encoded (normal para no-ASCII) — lo que
    # importa es que la dirección en sí no se corrompa, que era el bug real.
    assert _decoded_name(name) == "Happy Lápiz"
    assert addr == "hola@happylapiz.cl"


def test_resolve_from_email_ignores_unverified_custom_domain(patched_engine, db_session):
    shop = make_shop(
        db_session,
        name="Mi Tienda",
        sending_domain="mitienda.cl",
        sending_domain_verified=False,
    )
    result = resolve_from_email(shop.id, "Happy Lápiz <hola@happylapiz.cl>")
    name, addr = parseaddr(result)
    assert name == "Mi Tienda"
    assert addr == "hola@happylapiz.cl", "un dominio pendiente de verificar no debe usarse todavía"


def test_resolve_from_email_uses_verified_custom_domain(patched_engine, db_session):
    shop = make_shop(
        db_session,
        name="Mi Tienda",
        sending_domain="mitienda.cl",
        sending_domain_verified=True,
    )
    result = resolve_from_email(shop.id, "Happy Lápiz <hola@happylapiz.cl>")
    name, addr = parseaddr(result)
    assert name == "Mi Tienda"
    assert addr == "hola@mitienda.cl"


def test_resolve_from_email_missing_shop_returns_unchanged(patched_engine):
    original = "Happy Lápiz <hola@happylapiz.cl>"
    assert resolve_from_email(999999, original) == original
