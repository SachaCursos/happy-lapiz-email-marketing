"""
Marca como accepts_marketing=false los contactos que alguna vez se desuscribieron
(según el export de Klaviyo del 7 de junio 2026) y crea el segmento correspondiente.
"""
import os, csv, json, psycopg2
from datetime import datetime

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:nfKjyKqezPIGMgmneHgxdscnCFXypQQq@switchyard.proxy.rlwy.net:22708/railway")

DB  = os.environ["DATABASE_URL"]
CSV = os.path.join(os.path.dirname(__file__), "data", "unsubscribed_klaviyo_2026-06-07.csv")

conn = psycopg2.connect(DB)
cur  = conn.cursor()

# Leer emails del CSV
emails = []
with open(CSV) as f:
    for row in csv.DictReader(f):
        e = row["Email"].strip().lower()
        if e:
            emails.append(e)

print(f"Emails a marcar: {len(emails)}")

# Marcar accepts_marketing = false
cur.execute(
    "UPDATE contacts SET accepts_marketing = false, updated_at = NOW() WHERE lower(email) = ANY(%s)",
    (emails,)
)
print(f"Contactos actualizados: {cur.rowcount}")

# Obtener IDs para el segmento
cur.execute("SELECT id FROM contacts WHERE lower(email) = ANY(%s)", (emails,))
ids = [r[0] for r in cur.fetchall()]
print(f"IDs encontrados: {len(ids)}")

# Crear segmento (idempotente)
cur.execute("SELECT id FROM users LIMIT 1")
admin_id = cur.fetchone()[0]

cur.execute("SELECT id FROM segments WHERE name = 'Se desuscribieron alguna vez'")
existing = cur.fetchone()

if existing:
    cur.execute(
        "UPDATE segments SET conditions = %s::jsonb, updated_at = NOW() WHERE id = %s",
        (json.dumps({"operator": "AND", "rules": [{"field": "id", "op": "in", "value": ids}]}), existing[0])
    )
    print(f"Segmento actualizado (ID={existing[0]})")
else:
    cur.execute("""
        INSERT INTO segments (name, description, conditions, created_by, created_at, updated_at)
        VALUES (%s, %s, %s::jsonb, %s, NOW(), NOW()) RETURNING id
    """, (
        "Se desuscribieron alguna vez",
        "Contactos que alguna vez se desuscribieron del email marketing en Klaviyo (al 7 de junio 2026)",
        json.dumps({"operator": "AND", "rules": [{"field": "id", "op": "in", "value": ids}]}),
        admin_id,
    ))
    print(f"Segmento creado (ID={cur.fetchone()[0]})")

conn.commit()
conn.close()
print("Listo.")
