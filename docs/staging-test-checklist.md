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
1. En la tienda A, crear un contacto de prueba, un segmento y una **plantilla** (incluye probar "Instalar plantillas" y "Corregir logos" desde Configuración — antes del fix de 2026-07-22 estos dos botones tocaban plantillas de TODAS las tiendas, no solo la propia).
2. Confirmar que se guardan con el `shop_id` correcto (`SELECT shop_id FROM contacts WHERE email='...'`, `SELECT shop_id FROM templates WHERE name='...'`).
3. Loguearse en la tienda B y confirmar que esos registros no son visibles ni editables, y que las plantillas de la tienda B no fueron tocadas por los botones de la tienda A.

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

## 7. Envíos de prueba de automatizaciones y campañas

Verifica de punta a punta que el contenido real (no solo el endpoint) se renderiza y llega a la bandeja de entrada, para las automatizaciones más importantes.

Pasos:
1. Abrir una automatización (ej. carrito abandonado, cumpleaños) → botón "Enviar prueba" (`POST /api/automations/{id}/send-test`) → escribir el email de prueba → confirmar que llega un email por cada paso de la secuencia, con el footer mostrando el nombre correcto de la tienda (no "Happy Lápiz" a menos que sea esa la tienda).
2. Si el email de prueba tiene un carrito abandonado real en `carritos_abandonados`, confirmar que `{{ checkout_url }}` y `{{ cart_total }}` muestran datos reales (`cart_data_found: true` en la respuesta); si no, deben verse placeholders razonables, no vacíos ni errores de Jinja2.
3. Abrir una plantilla → "Enviar prueba" (`POST /api/templates/{id}/send-test`) — mismo chequeo.
4. Abrir una campaña → "Enviar prueba" (`POST /api/campaigns/{id}/send-test`, siempre va al email del usuario logueado) — mismo chequeo.

Resultado esperado: contenido correcto, footer con el nombre de tienda correcto, sin errores 500, sin placeholders rotos (`{{ variable_sin_definir }}` literal en el HTML).

## Hallazgos resueltos

- **`klaviyo_campaigns`/`asuntos_email` inexistentes rompían `/api/analytics/revenue`, `/klaviyo-campaigns` y `/asuntos` con un 500 (encontrado 2026-07-21, test #4).** Ambas tablas son de un import histórico de Klaviyo que nunca corrió en staging. Arreglado en `analytics.py` con un chequeo `to_regclass` que degrada a resultado vacío en vez de crashear (mismo patrón que `_shopify_orders_schema_ready` en `sync_shopify_orders.py`).

## Hallazgos resueltos (cont.)

- **React Query no invalidaba el caché de `["me"]` al hacer login/logout (encontrado 2026-07-22, al verificar el fix de branding).** Al loguearse con una cuenta distinta en la misma pestaña (sin recarga completa), el sidebar seguía mostrando el nombre de la tienda anterior por `staleTime: 5min` en `app/providers.tsx`. Arreglado llamando `queryClient.clear()` en el login (`app/(auth)/login/page.tsx`) y en el logout (`components/layout/sidebar.tsx`).
- **Branding "Happy Lápiz" hardcodeado en el chrome de la app (encontrado 2026-07-21, test #2; arreglado el mismo día).** Se agregó `shops.name` (poblado desde `shop.json` de Shopify en el OAuth callback, con fallback al dominio sin `.myshopify.com`), expuesto en `GET /api/auth/me` como `shop_name`. El frontend ahora usa ese valor en: sidebar (`components/layout/sidebar.tsx`), header móvil (`app/(dashboard)/layout.tsx`), página "Marca" (`app/(dashboard)/brand/page.tsx`). La página de login y el `<title>` de la pestaña (`app/layout.tsx`) se genericizaron a "Email Marketing" ya que no hay tienda conocida antes de autenticar. También se genericizaron textos menores en `contacts/[id]/page.tsx`, `variables/page.tsx`, `settings/page.tsx` y `unsubscribe/page.tsx`.

- **Footer hardcodeado "Happy Lápiz" en TODOS los emails reales enviados a clientes (encontrado y arreglado 2026-07-22).** Más grave que el branding de UI: `email_sender.py`'s `_FOOTER` decía "cliente de Happy Lápiz" en cada campaña y cada paso de automatización enviados a clientes reales de cualquier tienda. `_inject_footer` ahora recibe `shop_name` (vía `Shop.display_name()`), enhebrado en `_send_one`/`send_campaign_sync` (campañas), `_send_email_step` (automatizaciones) y ambos send-test. De paso se sacó un fallback hardcodeado `happylapiz.cl` en el send-test de plantillas.
- **`seed-templates` y `fix-logo` (botones "Instalar plantillas"/"Corregir logos" en Configuración) operaban sobre plantillas/campañas/segmentos de TODAS las tiendas, sin filtrar por `shop_id` (encontrado y arreglado 2026-07-22).** Cualquier admin de cualquier tienda podía sobreescribir o re-marcar (con el logo real de Happy Lápiz) las plantillas de otra tienda. Ambos endpoints ahora requieren `get_current_shop` y acotan todas sus queries/creaciones a `shop.id`.
- **`TemplateBlockEditor.tsx`: el bloque "header" ponía `alt="Happy Lápiz"` en el `<img>` del logo de CADA email real enviado (no solo en el editor) (encontrado y arreglado 2026-07-22).** Cambiado a `alt="Logo"`. También se genericizaron dos placeholders visibles solo en el editor (nombre de marca sin logo, producto de ejemplo del bloque de recomendaciones).
- **Presets de ejemplo con texto "Happy Lápiz" en el editor de formularios (encontrado y arreglado 2026-07-22).** `app/(dashboard)/forms/[id]/page.tsx` y `forms/new/page.tsx`: labels como "Diseño Happy Lápiz" / "Tipografía oficial Happy Lápiz" ahora dicen "Diseño de ejemplo" / "Tipografía sugerida". Los valores de color/tipografía en sí no cambiaron, solo el texto.
- **Página pública de unsubscribe no mostraba el nombre real de la tienda (encontrado y arreglado 2026-07-22).** `GET`/`POST /api/contacts/unsubscribe` ahora devuelven `shop_name` (resuelto vía `contact.shop_id` → `Shop.display_name()`), usado tanto en la página pública como en el email de notificación interna a `NOTIFY_EMAIL`.

## Hallazgos conocidos (no resueltos)

- **`plantillas_de_la_marca` (usada por `GET /api/admin/brand`, la página "Marca") es una tabla completamente global, sin columna `shop_id`.** Todas las tiendas ven los mismos colores/logos/tipografía — hoy son los de Happy Lápiz. A diferencia de los demás hallazgos de branding, este requiere un cambio de esquema (agregar `shop_id`, decidir qué pasa con tiendas que no configuraron nada — ¿default neutral o vacío?) y una UI para que cada tienda suba sus propios assets. Bloqueante real para vender a otro merchant si le importa que el editor de "Marca" muestre sus propios colores. No abordado en esta sesión — necesita diseño de producto, no solo un fix rápido.
- **Campaña legada con `shop_id = NULL` (`campaigns.id=1`, "Bienvenida - Happy Lápiz").** Quedó huérfana de antes de la migración multi-tenant — invisible en la UI de cualquier tienda (`WHERE shop_id = shop.id` nunca matchea NULL). No causa fugas ni errores, pero es basura en la base. Se puede borrar o backfillear a `shop_id=23` cuando se confirme que nadie la necesita.

## Registro de corridas

| Fecha | Tests corridos | Resultado | Notas |
|---|---|---|---|
| 2026-07-21 | Parcial: login manual (bootstrap) tienda Happy Lápiz | OK | Se creó el user admin de Happy Lápiz a mano por SQL (bootstrap shop nunca pasó por OAuth real) |
| 2026-07-21 | Test 2: aislamiento entre tenants (Happy Lápiz vs test-store777) | Parcial | Datos (contactos/campañas) correctamente aislados en 0/0. Encontrado: branding hardcodeado "Happy Lápiz" visible para test-store777 (ver Hallazgos conocidos) |
| 2026-07-21 | Test 3: CRUD por tenant sin fuga (contacto creado en test-store777) | OK | Contacto creado quedó con `shop_id=24` correcto; invisible en la lista de Happy Lápiz; acceso directo por URL a `/contacts/1` devuelve "Contacto no encontrado" (sin IDOR). Contacto de prueba eliminado después del test |
| 2026-07-21 | Test 4: analytics/dashboard sin 500 | OK (tras fix) | `/api/analytics/revenue` daba 500/503 por `klaviyo_campaigns` inexistente. Arreglado y verificado: `revenue`, `klaviyo-campaigns` y `asuntos` devuelven 200 |
| 2026-07-21 | Fix branding hardcodeado (chrome de la app) | OK | `shops.name` agregado + expuesto en `/auth/me`; sidebar/header/marca/login/title ahora dinámicos o genéricos |
| 2026-07-22 | Verificación visual: login Happy Lápiz → logout → login test-store777 (misma pestaña) | OK (tras 2do fix) | Encontrado y arreglado: React Query no invalidaba `["me"]` en login/logout, mostraba la tienda anterior. Tras el fix: sidebar muestra "happy-lapiz" y "test-store777-zdvg4n5k" correctamente para cada cuenta |
