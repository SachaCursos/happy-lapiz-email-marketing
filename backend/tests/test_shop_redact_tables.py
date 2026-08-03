"""app/routers/shopify_webhooks.py::_redact_shop_data — shop/redact (fired
~48h after app/uninstalled) deleted every tenant table except shopify_orders,
even though it carries real PII (email, phone, name, shipping address).
Regression guard so it doesn't quietly drop out of the list again — this
function builds its DELETE list from a plain Python list of table names, not
something coverable by a real DB integration test in this suite (raw
psycopg2 cursor, no SQLModel session)."""
import inspect

from app.routers import shopify_webhooks


def test_shopify_orders_is_included_in_shop_redact():
    source = inspect.getsource(shopify_webhooks._redact_shop_data)
    tables_block = source.split("tables_in_fk_order = [")[1].split("]")[0]
    assert "shopify_orders" in tables_block, (
        "shopify_orders dejó de estar en la lista de tablas que borra shop/redact — "
        "es la única tabla de Shopify con PII real (email/telefono/nombre/direccion) "
        "que este webhook debe limpiar"
    )
