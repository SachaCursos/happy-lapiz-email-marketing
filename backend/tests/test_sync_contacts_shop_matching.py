"""app/services/sync_shopify_orders.py::sync_contacts_from_shopify_orders —
el INSERT y el UPDATE matcheaban contactos existentes solo por email, sin
shop_id (`WHERE lower(c.email) = os.email`). Con `contacts.email` pasando a
ser único por tienda (ver database.py), eso: (a) generaba los contactos con
shop_id NULL que tuvimos que backfillear en producción, y (b) una vez el
constraint por-tienda esté activo, haría que el INSERT se salte la creación
de un contacto legítimo de la tienda B solo porque una tienda A ya tiene un
contacto con ese email.

Esta suite no puede correr las queries reales contra SQLite (usan
DISTINCT ON, NOW(), IS DISTINCT FROM — todo específico de Postgres, mismo
límite documentado en conftest.py), así que es un regression-guard sobre el
texto de las queries: confirma que ambas exigen (email, shop_id) y no
reintroducen el matcheo solo-por-email."""
import inspect
import re

from app.services import sync_shopify_orders


def _source() -> str:
    return inspect.getsource(sync_shopify_orders.sync_contacts_from_shopify_orders)


def test_insert_matches_existing_contact_by_email_and_shop():
    source = _source()
    insert_block = source.split("insert_sql = text(")[1].split("update_sql = text(")[0]
    assert "c.shop_id = os.shop_id" in insert_block, (
        "el INSERT dejó de exigir shop_id al chequear si el contacto ya existe — "
        "volvería a crear (o saltear) contactos ignorando la tienda"
    )


def test_update_matches_existing_contact_by_email_and_shop():
    source = _source()
    update_block = source.split("update_sql = text(")[1]
    assert "c.shop_id = os.shop_id" in update_block, (
        "el UPDATE dejó de exigir shop_id al matchear contactos — "
        "actualizaría el contacto de una tienda con datos de otra si comparten email"
    )


def test_no_leftover_email_only_matching():
    """El bug real: `WHERE lower(c.email) = os.email` sin ningún AND de shop_id
    en la misma cláusula. Si alguien reintroduce esa forma exacta (por ejemplo
    copiando el patrón viejo a una query nueva), esto debe fallar."""
    source = _source()
    email_only_where = re.search(
        r"WHERE\s+lower\(c\.email\)\s*=\s*os\.email\s*\n\s*\)",
        source,
    )
    assert email_only_where is None, (
        "encontrado un WHERE que matchea contacts solo por email, sin shop_id, "
        "en sync_contacts_from_shopify_orders"
    )
