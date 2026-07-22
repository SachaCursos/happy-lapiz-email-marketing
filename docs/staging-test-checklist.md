# Checklist de pruebas de staging — arquitectura multi-tenant (`shops`)

Objetivo: confirmar que el modelo multi-tenant (`shops` + `shop_id` en cada tabla) funciona igual para cualquier tienda instalada, sin fugas de datos entre tenants, **antes** de migrar la tienda de producción (Happy Lápiz) a este esquema.

## Entorno

- Railway: workspace `sachacursos's Projects` → proyecto `valiant-surprise` → environment `staging`.
- Frontend: https://email-marketing-front-end-staging.up.railway.app
- Backend: https://email-marketing-back-end-staging.up.railway.app
- Postgres: Railway → servicio `Postgres` (staging) → tab `Console` → `psql -U postgres -c "..."`
- Al escribir SQL con hashes bcrypt (contienen `$`) en la consola, usar un heredoc `<< 'SQLEOF'` (comillas simples en el delimitador) para que la shell no intente expandir `$2b$12$...` como variables.

## Tiendas de prueba en staging (estado a 2026-07-21)

| shop_id | dominio | origen | estado |
|---|---|---|---|
| 24 | test-store777-zdvg4n5k.myshopify.com | instalada vía OAuth real (`/install`→`/callback`) | sync inicial OK, tiene owner y user |
| 23 | happy-lapiz.myshopify.com | creada por la migración de bootstrap (`0003_backfill_bootstrap_shop.py`) | **no** pasó por OAuth real; sin `shop_owner_email`; el user admin se creó manualmente por SQL para poder probar el dashboard |

Antes de dar por buena una migración de producción, lo ideal es hacer que Happy Lápiz en staging pase por el flujo real de instalación (test 1) en vez de depender del bootstrap.

## 1. Instalación de una tienda nueva vía OAuth

Pasos:
1. Ir a `{backend}/api/shopify/install?shop=<dominio>.myshopify.com`.
2. Aceptar el consentimiento en Shopify.
3. Confirmar que redirige de vuelta a la app y que se crea el `Shop` en la tabla `shops` con `status='active'`.
4. Confirmar que llega el email de "crear contraseña" al owner.
5. Crear la contraseña y loguearse.
6. Confirmar que `initial_sync_status` pasa a `complete` (revisar en DB o en el mensaje de la UI) y que `initial_sync_error` queda `NULL`.

Resultado esperado: shop activo, user creado, sync completo, sin errores en logs del backend durante el proceso.

## 2. Aislamiento entre tenants (shop_id scoping)

Pasos:
1. Loguearse como usuario de la tienda A (ej. `test-store777`, `hotboatvillarrica@gmail.com`).
2. Anotar contactos/campañas/segmentos visibles.
3. Loguearse como usuario de la tienda B (ej. Happy Lápiz, `tomasdamjanic@gmail.com`).
4. Confirmar que NO aparece ningún dato de la tienda A, y viceversa.
5. Revisar especialmente: Contactos, Campañas, Segmentos, Plantillas, Automatizaciones, Cupones, Productos, Analytics/Revenue.

Resultado esperado: cero superposición de datos entre tiendas.

## 3. CRUD básico por tenant sin fuga de datos

Pasos:
1. En la tienda A, crear un contacto de prueba, un segmento y una plantilla.
2. Confirmar que se guardan con el `shop_id` correcto (`SELECT shop_id FROM contacts WHERE email='...'`).
3. Loguearse en la tienda B y confirmar que esos registros no son visibles ni editables.

Resultado esperado: cada tienda solo ve y modifica sus propios datos.

## 4. Analytics/dashboard sin 500

Pasos:
1. Con cada tienda logueada, abrir el Dashboard y `Analytics` (`/api/analytics/overview`, `/api/analytics/revenue`).
2. Revisar la consola del navegador (Network + Console) buscando errores CORS o 500.
3. Si aparece un 500 "disfrazado" de error CORS, revisar los logs del backend en Railway — es el patrón típico de Starlette cuando una excepción no manejada evita el middleware de CORS (ya nos pasó con `shopify_orders` y `shopify_checkouts` faltantes).

Resultado esperado: 200 en ambos endpoints para ambas tiendas.

## 5. Webhooks GDPR de cumplimiento

Pasos:
1. Disparar manualmente (o vía Shopify CLI/Partner Dashboard test) los topics: `customers/data_request`, `customers/redact`, `shop/redact`, `app/uninstalled`.
2. Confirmar que el backend responde 200 en todos los casos (nunca debe 500 — ver `_dispatch_webhook_topic` en `shopify_webhooks.py`, que atrapa cualquier excepción y igual devuelve 200).
3. Para `customers/redact`: confirmar que solo se anonimiza el contacto de la tienda correspondiente (`shop_id` correcto), no de otras tiendas con el mismo email.
4. Para `shop/redact`: confirmar que borra/anonimiza todos los datos de esa tienda y no toca otras.

Resultado esperado: 200 siempre, y el borrado/anonimizado queda acotado al `shop_id` correcto.

## 6. Desinstalación / reinstalación

Pasos:
1. Desinstalar la app desde el admin de Shopify de una tienda de prueba.
2. Confirmar que `app/uninstalled` deja el shop en `status='uninstalled'`.
3. Reinstalar la misma tienda.
4. Confirmar que no se duplican filas en `shops` ni se generan contactos/datos duplicados.

Resultado esperado: reinstalación limpia, sin duplicados, sin errores.

## Hallazgos resueltos

- **`klaviyo_campaigns`/`asuntos_email` inexistentes rompían `/api/analytics/revenue`, `/klaviyo-campaigns` y `/asuntos` con un 500 (encontrado 2026-07-21, test #4).** Ambas tablas son de un import histórico de Klaviyo que nunca corrió en staging. Arreglado en `analytics.py` con un chequeo `to_regclass` que degrada a resultado vacío en vez de crashear (mismo patrón que `_shopify_orders_schema_ready` en `sync_shopify_orders.py`).

## Hallazgos resueltos (cont.)

- **Branding "Happy Lápiz" hardcodeado en el chrome de la app (encontrado 2026-07-21, test #2; arreglado el mismo día).** Se agregó `shops.name` (poblado desde `shop.json` de Shopify en el OAuth callback, con fallback al dominio sin `.myshopify.com`), expuesto en `GET /api/auth/me` como `shop_name`. El frontend ahora usa ese valor en: sidebar (`components/layout/sidebar.tsx`), header móvil (`app/(dashboard)/layout.tsx`), página "Marca" (`app/(dashboard)/brand/page.tsx`). La página de login y el `<title>` de la pestaña (`app/layout.tsx`) se genericizaron a "Email Marketing" ya que no hay tienda conocida antes de autenticar. También se genericizaron textos menores en `contacts/[id]/page.tsx`, `variables/page.tsx`, `settings/page.tsx` y `unsubscribe/page.tsx`.

## Hallazgos conocidos (no resueltos)

- **Branding de ejemplo/demo "Happy Lápiz" en contenido de presets (no chrome de la app).** `components/TemplateBlockEditor.tsx` (paleta de colores por defecto, producto de ejemplo "Marcadores Happy Lápiz Set 12 colores") y `app/(dashboard)/forms/[id]/page.tsx` (preset "Diseño Happy Lápiz", tipografía sugerida) tienen contenido de ejemplo específico de Happy Lápiz que otras tiendas verían como opciones/presets. No es incorrecto per se (son plantillas de ejemplo editables), pero sería mejor experiencia que fueran neutrales o configurables por tienda. Baja prioridad — no bloquea el uso normal de la app por otro merchant.
- **Página pública de unsubscribe no muestra el nombre real de la tienda que envió el email.** `app/unsubscribe/page.tsx` es una página no autenticada; hoy dice "Ya no recibirás emails de nuestra parte" en vez del nombre real de la tienda. Arreglarlo del todo requeriría que `GET /api/contacts/unsubscribe` devuelva también el nombre de la tienda asociada al contacto. Quedó pendiente.

## Registro de corridas

| Fecha | Tests corridos | Resultado | Notas |
|---|---|---|---|
| 2026-07-21 | Parcial: login manual (bootstrap) tienda Happy Lápiz | OK | Se creó el user admin de Happy Lápiz a mano por SQL (bootstrap shop nunca pasó por OAuth real) |
| 2026-07-21 | Test 2: aislamiento entre tenants (Happy Lápiz vs test-store777) | Parcial | Datos (contactos/campañas) correctamente aislados en 0/0. Encontrado: branding hardcodeado "Happy Lápiz" visible para test-store777 (ver Hallazgos conocidos) |
| 2026-07-21 | Test 3: CRUD por tenant sin fuga (contacto creado en test-store777) | OK | Contacto creado quedó con `shop_id=24` correcto; invisible en la lista de Happy Lápiz; acceso directo por URL a `/contacts/1` devuelve "Contacto no encontrado" (sin IDOR). Contacto de prueba eliminado después del test |
| 2026-07-21 | Test 4: analytics/dashboard sin 500 | OK (tras fix) | `/api/analytics/revenue` daba 500/503 por `klaviyo_campaigns` inexistente. Arreglado y verificado: `revenue`, `klaviyo-campaigns` y `asuntos` devuelven 200 |
| 2026-07-21 | Fix branding hardcodeado (chrome de la app) | OK | `shops.name` agregado + expuesto en `/auth/me`; sidebar/header/marca/login/title ahora dinámicos o genéricos. Pendiente re-probar visualmente tras el deploy |
