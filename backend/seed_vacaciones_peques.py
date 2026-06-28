"""Crea plantilla y campaña borrador: Vacaciones — Juguetes para tus peques (Happy Lápiz)."""
import json
import os
import sys
from datetime import datetime

import psycopg2

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:nfKjyKqezPIGMgmneHgxdscnCFXypQQq@switchyard.proxy.rlwy.net:22708/railway",
)
HL_LOGO = "https://cdn.shopify.com/s/files/1/0556/5343/3495/files/LOGO_HappyLapiz.png?v=1621889822"

TPL_NAME = "Vacaciones — Juguetes para tus peques"
CAM_NAME = "Vacaciones — Juguetes para tus peques"
SEG_NAME = "Todos los suscriptores"
SUBJECT = "{{nombre or 'Hola'}}, ideas para las vacaciones de tus peques ☀️"
PREVIEW = "Juegos, creatividad y aprendizaje para que disfruten al máximo sus vacaciones."

TPL_HTML = f"""<div style="font-family:'Helvetica Neue',Arial,sans-serif;max-width:600px;margin:0 auto;background:#ffffff;">
  <div style="padding:28px 32px 0;text-align:center;">
    <a href="https://www.happylapiz.cl"><img src="{HL_LOGO}" alt="Happy L&#225;piz" width="160" style="height:auto;display:inline-block;" /></a>
  </div>
  <div style="background:linear-gradient(135deg,#f97316 0%,#fb923c 40%,#682ae7 100%);margin:20px 0 0;padding:40px 32px;text-align:center;">
    <p style="color:rgba(255,255,255,0.9);font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:1.5px;margin:0 0 12px;">Vacaciones con alegr&#237;a</p>
    <h1 style="color:#fff;font-size:26px;font-weight:800;margin:0 0 12px;line-height:1.25;">
      &#161;Hola {{{{ first_name or nombre or 'familia' }}}}!<br/>Que tus peques disfruten al m&#225;ximo
    </h1>
    <p style="color:#fff;font-size:15px;margin:0;line-height:1.6;opacity:0.95;">
      Llegaron las vacaciones: el momento perfecto para jugar, crear y aprender juntos en casa.
    </p>
  </div>
  <div style="padding:32px 32px 8px;">
    <p style="font-size:15px;color:#374151;line-height:1.75;margin:0 0 20px;">
      En <strong>Happy L&#225;piz</strong> reunimos juguetes educativos que mantienen a los ni&#241;os entretenidos
      <em>y</em> estimulan su creatividad. Sin pantallas de m&#225;s: manos a la obra, imaginaci&#243;n encendida.
    </p>
    <div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:14px;padding:24px;margin-bottom:24px;">
      <p style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;color:#ea580c;margin:0 0 14px;">Ideas para estas vacaciones</p>
      <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;">
        <tr>
          <td style="padding:8px 0;vertical-align:top;width:36px;font-size:22px;">🎨</td>
          <td style="padding:8px 0;vertical-align:top;">
            <p style="font-weight:700;color:#111;font-size:14px;margin:0 0 2px;">Arte y manualidades</p>
            <p style="color:#6b7280;font-size:13px;margin:0;line-height:1.5;">Pinturas, marcadores y kits creativos para tardes llenas de color.</p>
          </td>
        </tr>
        <tr>
          <td style="padding:8px 0;vertical-align:top;font-size:22px;">🧩</td>
          <td style="padding:8px 0;vertical-align:top;">
            <p style="font-weight:700;color:#111;font-size:14px;margin:0 0 2px;">Juegos de mesa y puzzles</p>
            <p style="color:#6b7280;font-size:13px;margin:0;line-height:1.5;">Diversi&#243;n en familia que desarrolla l&#243;gica y paciencia.</p>
          </td>
        </tr>
        <tr>
          <td style="padding:8px 0;vertical-align:top;font-size:22px;">🔬</td>
          <td style="padding:8px 0;vertical-align:top;">
            <p style="font-weight:700;color:#111;font-size:14px;margin:0 0 2px;">Ciencia y exploraci&#243;n</p>
            <p style="color:#6b7280;font-size:13px;margin:0;line-height:1.5;">Experimentos y kits que convierten el hogar en un laboratorio.</p>
          </td>
        </tr>
      </table>
    </div>
    <div style="text-align:center;margin:28px 0 12px;">
      <a href="https://www.happylapiz.cl/collections/all" style="background:#682ae7;color:#fff;font-weight:700;padding:15px 42px;border-radius:30px;text-decoration:none;font-size:15px;display:inline-block;">Ver juguetes para vacaciones &#8594;</a>
    </div>
    <p style="font-size:13px;color:#9ca3af;text-align:center;margin:0 0 24px;line-height:1.5;">
      Env&#237;o a todo Chile &middot; Productos pensados para cada edad
    </p>
    <div style="background:#f5f3ff;border-radius:12px;padding:20px 24px;text-align:center;">
      <p style="font-size:14px;color:#5b21b6;margin:0;line-height:1.6;">
        <strong>&#128161; Tip:</strong> Si ya conoces la edad de tu peque, filtra por categor&#237;a en la tienda y encuentra el regalo ideal en minutos.
      </p>
    </div>
  </div>
  <div style="border-top:1px solid #f3f4f6;padding:20px 32px;text-align:center;">
    <img src="{HL_LOGO}" alt="Happy L&#225;piz" width="100" style="height:auto;display:inline-block;opacity:0.5;margin-bottom:10px;" />
    <p style="font-size:12px;color:#d1d5db;margin:4px 0;">Juguetes educativos &middot; Chile</p>
    <p style="font-size:12px;color:#d1d5db;margin:6px 0;"><a href="##unsub##" style="color:#d1d5db;">Cancelar suscripci&#243;n</a></p>
  </div>
</div>"""

SEG_CONDITIONS = {
    "operator": "AND",
    "rules": [{"field": "opted_in", "op": "eq", "value": True}],
}


def main() -> None:
    now = datetime.utcnow()
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
            "UPDATE templates SET subject_default=%s, preview_text=%s, html_content=%s, updated_at=%s WHERE id=%s",
            (SUBJECT, PREVIEW, TPL_HTML, now, tpl_id),
        )
        print(f"  plantilla actualizada: {TPL_NAME} (id={tpl_id})")
    else:
        cur.execute(
            "INSERT INTO templates (name, subject_default, preview_text, html_content, created_by, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (TPL_NAME, SUBJECT, PREVIEW, TPL_HTML, admin_id, now, now),
        )
        tpl_id = cur.fetchone()[0]
        print(f"  plantilla creada: {TPL_NAME} (id={tpl_id})")
    conn.commit()

    cur.execute("SELECT id FROM campaigns WHERE name = %s", (CAM_NAME,))
    if cur.fetchone():
        cur.execute(
            "UPDATE campaigns SET subject=%s, preview_text=%s, template_id=%s, segment_id=%s WHERE name=%s",
            (SUBJECT, PREVIEW, tpl_id, seg_id, CAM_NAME),
        )
        print(f"  campaña actualizada: {CAM_NAME}")
    else:
        cur.execute(
            "INSERT INTO campaigns (name, subject, preview_text, template_id, segment_id, status, created_by, created_at) "
            "VALUES (%s, %s, %s, %s, %s, 'draft', %s, %s)",
            (CAM_NAME, SUBJECT, PREVIEW, tpl_id, seg_id, admin_id, now),
        )
        print(f"  campaña creada: {CAM_NAME}")
    conn.commit()

    cur.execute(
        "SELECT COUNT(*) FROM contacts WHERE opted_in = true"
    )
    total = cur.fetchone()[0]
    conn.close()

    print(f"\n  Destinatarios potenciales (opted_in): {total}")
    print("\nListo. Ve a Campañas → 'Vacaciones — Juguetes para tus peques' para revisar y enviar.")


if __name__ == "__main__":
    main()
