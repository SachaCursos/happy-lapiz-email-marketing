"""Crea/actualiza plantilla y campaña borrador: Vacaciones — Juguetes para tus peques (bloques)."""
import json
import os
import sys
from datetime import datetime

import psycopg2

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.favorite_blocks_seed import VACACIONES_PREVIEW, VACACIONES_SUBJECT, vacaciones_blocks
from app.services.template_block_compiler import blocks_to_html

DB = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:nfKjyKqezPIGMgmneHgxdscnCFXypQQq@switchyard.proxy.rlwy.net:22708/railway",
)

TPL_NAME = "Vacaciones — Juguetes para tus peques"
CAM_NAME = "Vacaciones — Juguetes para tus peques"
SEG_NAME = "Todos los suscriptores"

SEG_CONDITIONS = {
    "operator": "AND",
    "rules": [{"field": "opted_in", "op": "eq", "value": True}],
}


def main() -> None:
    now = datetime.utcnow()
    blocks = vacaciones_blocks()
    tpl_html = blocks_to_html(blocks)
    json_blocks = json.dumps(blocks, ensure_ascii=False)

    conn = psycopg2.connect(DB)
    cur = conn.cursor()

    cur.execute("SELECT id FROM users ORDER BY id LIMIT 1")
    row = cur.fetchone()
    if not row:
        print("ERROR: no hay usuarios en la BD")
        sys.exit(1)
    admin_id = row[0]

    cur.execute("SELECT id FROM segments WHERE name = %s", (SEG_NAME,))
    seg_row = cur.fetchone()
    if seg_row:
        seg_id = seg_row[0]
        print(f"  segmento ya existe: {SEG_NAME} (id={seg_id})")
    else:
        cur.execute(
            "INSERT INTO segments (name, description, conditions, created_by, created_at, updated_at) "
            "VALUES (%s, %s, %s::jsonb, %s, %s, %s) RETURNING id",
            (
                SEG_NAME,
                "Todos los contactos con opt-in activo",
                json.dumps(SEG_CONDITIONS),
                admin_id,
                now,
                now,
            ),
        )
        seg_id = cur.fetchone()[0]
        print(f"  segmento creado: {SEG_NAME} (id={seg_id})")
    conn.commit()

    cur.execute("SELECT id FROM templates WHERE name = %s", (TPL_NAME,))
    tpl_row = cur.fetchone()
    if tpl_row:
        tpl_id = tpl_row[0]
        cur.execute(
            "UPDATE templates SET subject_default=%s, preview_text=%s, html_content=%s, json_blocks=%s::jsonb, updated_at=%s WHERE id=%s",
            (VACACIONES_SUBJECT, VACACIONES_PREVIEW, tpl_html, json_blocks, now, tpl_id),
        )
        print(f"  plantilla actualizada (bloques): {TPL_NAME} (id={tpl_id})")
    else:
        cur.execute(
            "INSERT INTO templates (name, subject_default, preview_text, html_content, json_blocks, created_by, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s) RETURNING id",
            (TPL_NAME, VACACIONES_SUBJECT, VACACIONES_PREVIEW, tpl_html, json_blocks, admin_id, now, now),
        )
        tpl_id = cur.fetchone()[0]
        print(f"  plantilla creada (bloques): {TPL_NAME} (id={tpl_id})")
    conn.commit()

    cur.execute("SELECT id FROM campaigns WHERE name = %s", (CAM_NAME,))
    if cur.fetchone():
        cur.execute(
            "UPDATE campaigns SET subject=%s, preview_text=%s, template_id=%s, segment_id=%s WHERE name=%s",
            (VACACIONES_SUBJECT, VACACIONES_PREVIEW, tpl_id, seg_id, CAM_NAME),
        )
        print(f"  campaña actualizada: {CAM_NAME}")
    else:
        cur.execute(
            "INSERT INTO campaigns (name, subject, preview_text, template_id, segment_id, status, created_by, created_at) "
            "VALUES (%s, %s, %s, %s, %s, 'draft', %s, %s)",
            (CAM_NAME, VACACIONES_SUBJECT, VACACIONES_PREVIEW, tpl_id, seg_id, admin_id, now),
        )
        print(f"  campaña creada: {CAM_NAME}")
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM contacts WHERE opted_in = true")
    total = cur.fetchone()[0]
    conn.close()

    print(f"\n  Destinatarios potenciales (opted_in): {total}")
    print(f"  Bloques en plantilla: {len(blocks)}")
    print("\nListo. Edita la plantilla en el editor de bloques — cada CTA es un bloque con URL visible.")


if __name__ == "__main__":
    main()
