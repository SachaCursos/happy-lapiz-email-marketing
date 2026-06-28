"""Block catalog and template compositions for Happy Lápiz."""

from app.services.template_block_compiler import make_block

HL_LOGO = "https://cdn.shopify.com/s/files/1/0556/5343/3495/files/LOGO_HappyLapiz.png?v=1621889822"
FF = "'Helvetica Neue', Arial, sans-serif"

# sort_order < 50 → se cargan al crear plantilla nueva (starter mínimo)
# sort_order >= 100 → catálogo / galería de opciones


def _hero_logo_content(
    subtitle: str,
    title_html: str,
    body: str,
    *,
    logo_width: int = 120,
    logo_margin_bottom: int = 20,
    subtitle_size: int = 13,
    title_size: int = 26,
    body_size: int = 15,
    text_gap: int = 12,
) -> str:
    return (
        f'<p style="margin:0 0 {logo_margin_bottom}px;text-align:center;">'
        f'<a href="https://www.happylapiz.cl" style="text-decoration:none;">'
        f'<img src="{HL_LOGO}" alt="Happy L&#225;piz" width="{logo_width}" '
        f'style="height:auto;display:inline-block;max-width:45%;" /></a></p>'
        f'<p style="margin:0;font-size:{subtitle_size}px;font-weight:600;color:rgba(255,255,255,0.9);'
        f'text-transform:uppercase;letter-spacing:1.2px;text-align:center;">{subtitle}</p>'
        f'<p style="margin:{text_gap}px 0 0;font-size:{title_size}px;font-weight:800;color:#ffffff;'
        f'line-height:1.2;text-align:center;">{title_html}</p>'
        f'<p style="margin:{text_gap}px 0 0;font-size:{body_size}px;color:#ffffff;line-height:1.45;'
        f'text-align:center;opacity:0.95;">{body}</p>'
    )


BLOCK_CATALOG: list[dict] = [
    # ── Starters (nueva plantilla) ───────────────────────────────────────────
    {
        "name": "Encabezado — Logo Happy Lápiz",
        "block_type": "header",
        "sort_order": 10,
        "props": {
            "logo_url": HL_LOGO,
            "logo_width": "160",
            "bg_color": "#ffffff",
            "link": "https://www.happylapiz.cl",
        },
    },
    {
        "name": "Hero — Vacaciones con logo centrado",
        "block_type": "text",
        "sort_order": 15,
        "props": {
            "content": _hero_logo_content(
                "Vacaciones con alegr&#237;a",
                "&#161;Hola {{ first_name or nombre }}!<br/>Que tus peques disfruten al m&#225;ximo",
                "Llegaron las vacaciones: jugar, crear y aprender juntos en casa.",
                logo_width=88,
                logo_margin_bottom=10,
                subtitle_size=11,
                title_size=20,
                body_size=13,
                text_gap=8,
            ),
            "bg_color": "#f97316",
            "text_color": "#ffffff",
            "padding_y": "22",
            "padding_x": "24",
            "font_family": FF,
        },
    },
    # ── Heroes (catálogo) ────────────────────────────────────────────────────
    {
        "name": "Hero — Banner morado",
        "block_type": "text",
        "sort_order": 100,
        "props": {
            "content": (
                "<p style=\"margin:0;font-size:22px;font-weight:800;color:#ffffff;line-height:1.3;"
                f"font-family:{FF};\">&#161;Hola, {{ nombre }}! &#127775;</p>"
                "<p style=\"margin:12px 0 0;font-size:15px;color:#ddd6fe;line-height:1.6;"
                f"font-family:{FF};\">Tu mensaje destacado aqu&#237;.</p>"
            ),
            "bg_color": "#682ae7",
            "text_color": "#ffffff",
            "padding_y": "36",
            "padding_x": "32",
            "font_family": FF,
        },
    },
    {
        "name": "Hero — Banner vacaciones (naranja)",
        "block_type": "text",
        "sort_order": 105,
        "props": {
            "content": (
                "<p style=\"margin:0;font-size:13px;font-weight:600;color:rgba(255,255,255,0.9);"
                "text-transform:uppercase;letter-spacing:1.5px;text-align:center;\">Vacaciones con alegr&#237;a</p>"
                "<p style=\"margin:12px 0 0;font-size:26px;font-weight:800;color:#ffffff;line-height:1.25;text-align:center;\">"
                "&#161;Hola {{ first_name or nombre }}!<br/>Que tus peques disfruten al m&#225;ximo</p>"
                "<p style=\"margin:12px 0 0;font-size:15px;color:#ffffff;line-height:1.6;text-align:center;opacity:0.95;\">"
                "Llegaron las vacaciones: jugar, crear y aprender juntos en casa.</p>"
            ),
            "bg_color": "#f97316",
            "text_color": "#ffffff",
            "padding_y": "40",
            "padding_x": "32",
            "font_family": FF,
        },
    },
    {
        "name": "Hero — Morado con logo centrado",
        "block_type": "text",
        "sort_order": 110,
        "props": {
            "content": _hero_logo_content(
                "Bienvenido/a a Happy L&#225;piz",
                "&#161;Hola, {{ nombre }}! &#127775;",
                "Nos alegra tenerte en nuestra comunidad de juguetes educativos.",
            ),
            "bg_color": "#682ae7",
            "text_color": "#ffffff",
            "padding_y": "40",
            "padding_x": "32",
            "font_family": FF,
        },
    },
    {
        "name": "Hero — Naranja degradado con logo",
        "block_type": "text",
        "sort_order": 115,
        "props": {
            "content": _hero_logo_content(
                "Ofertas de temporada",
                "&#161;Hola {{ first_name or nombre }}!<br/>Descubre lo nuevo",
                "Juguetes educativos seleccionados para estimular la creatividad.",
            ),
            "bg_color": "#ea580c",
            "text_color": "#ffffff",
            "padding_y": "40",
            "padding_x": "32",
            "font_family": FF,
        },
    },
    # ── Cuerpo ───────────────────────────────────────────────────────────────
    {
        "name": "Párrafo — Cuerpo estándar",
        "block_type": "text",
        "sort_order": 120,
        "props": {
            "content": (
                f"<p style=\"margin:0;font-size:15px;line-height:1.75;color:#374151;font-family:{FF};\">"
                "Hola {{ first_name or nombre }}, escribe tu mensaje aqu&#237;. "
                "En <strong>Happy L&#225;piz</strong> encontrar&#225;s juguetes educativos para cada edad."
                "</p>"
            ),
            "bg_color": "#ffffff",
            "text_color": "#374151",
            "padding_y": "24",
            "padding_x": "32",
            "font_family": FF,
        },
    },
    {
        "name": "Párrafo — Vacaciones (cuerpo)",
        "block_type": "text",
        "sort_order": 125,
        "props": {
            "content": (
                f"<p style=\"margin:0;font-size:15px;line-height:1.75;color:#374151;font-family:{FF};\">"
                "En <strong>Happy L&#225;piz</strong> reunimos juguetes educativos que mantienen a los ni&#241;os entretenidos "
                "<em>y</em> estimulan su creatividad. Sin pantallas de m&#225;s: manos a la obra, imaginaci&#243;n encendida."
                "</p>"
            ),
            "bg_color": "#ffffff",
            "text_color": "#374151",
            "padding_y": "28",
            "padding_x": "32",
            "font_family": FF,
        },
    },
    {
        "name": "Caja — Ideas para vacaciones (naranja claro)",
        "block_type": "text",
        "sort_order": 130,
        "props": {
            "content": (
                "<div style=\"background:#fff7ed;border:1px solid #fed7aa;border-radius:14px;padding:24px;\">"
                "<p style=\"font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;"
                "color:#ea580c;margin:0 0 14px;\">Ideas para estas vacaciones</p>"
                "<div style=\"padding:6px 0;\">"
                "<p style=\"margin:0 0 4px;font-size:20px;line-height:1;\">&#127912;</p>"
                "<p style=\"font-weight:700;color:#111;font-size:14px;margin:0 0 2px;\">Arte y manualidades</p>"
                "<p style=\"color:#6b7280;font-size:13px;margin:0;line-height:1.5;\">Pinturas, marcadores y kits creativos.</p>"
                "</div>"
                "<div style=\"padding:6px 0;\">"
                "<p style=\"margin:0 0 4px;font-size:20px;line-height:1;\">&#129513;</p>"
                "<p style=\"font-weight:700;color:#111;font-size:14px;margin:0 0 2px;\">Juegos de mesa y puzzles</p>"
                "<p style=\"color:#6b7280;font-size:13px;margin:0;line-height:1.5;\">Diversi&#243;n en familia que desarrolla l&#243;gica.</p>"
                "</div></div>"
            ),
            "bg_color": "#ffffff",
            "text_color": "#374151",
            "padding_y": "8",
            "padding_x": "32",
            "font_family": FF,
        },
    },
    {
        "name": "Caja — Tip morado",
        "block_type": "text",
        "sort_order": 135,
        "props": {
            "content": (
                "<div style=\"background:#f5f3ff;border-radius:12px;padding:20px 24px;text-align:center;\">"
                "<p style=\"font-size:14px;color:#5b21b6;margin:0;line-height:1.6;\">"
                "<strong>&#128161; Tip:</strong> Filtra por edad en la tienda y encuentra el regalo ideal en minutos."
                "</p></div>"
            ),
            "bg_color": "#ffffff",
            "text_color": "#5b21b6",
            "padding_y": "8",
            "padding_x": "32",
            "font_family": FF,
        },
    },
    {
        "name": "Nota — Envío centrada",
        "block_type": "text",
        "sort_order": 140,
        "props": {
            "content": (
                f"<p style=\"margin:0;font-size:13px;color:#9ca3af;text-align:center;line-height:1.5;font-family:{FF};\">"
                "Env&#237;o a todo Chile &middot; Productos pensados para cada edad"
                "</p>"
            ),
            "bg_color": "#ffffff",
            "text_color": "#9ca3af",
            "padding_y": "8",
            "padding_x": "32",
            "font_family": FF,
        },
    },
    # ── Botones CTA (bloques separados — URL editable en panel) ──────────────
    {
        "name": "Botón CTA — Morado",
        "block_type": "button",
        "sort_order": 150,
        "props": {
            "text": "Ver catálogo →",
            "url": "https://www.happylapiz.cl",
            "bg_color": "#682ae7",
            "text_color": "#ffffff",
            "align": "center",
            "border_radius": "30",
            "font_size": "15",
            "letter_spacing": "0",
            "font_family": FF,
            "full_width": False,
        },
    },
    {
        "name": "Botón CTA — Naranja",
        "block_type": "button",
        "sort_order": 155,
        "props": {
            "text": "Ver juguetes para vacaciones →",
            "url": "https://www.happylapiz.cl/collections/all",
            "bg_color": "#f97316",
            "text_color": "#ffffff",
            "align": "center",
            "border_radius": "30",
            "font_size": "15",
            "letter_spacing": "0",
            "font_family": FF,
            "full_width": False,
        },
    },
    {
        "name": "Botón CTA — Morado vacaciones",
        "block_type": "button",
        "sort_order": 156,
        "props": {
            "text": "Ver juguetes para vacaciones →",
            "url": "https://www.happylapiz.cl/collections/all",
            "bg_color": "#682ae7",
            "text_color": "#ffffff",
            "align": "center",
            "border_radius": "30",
            "font_size": "15",
            "letter_spacing": "0",
            "font_family": FF,
            "full_width": False,
        },
    },
    {
        "name": "Botón CTA — Barra ancho completo",
        "block_type": "button",
        "sort_order": 160,
        "props": {
            "text": "Comprar ahora",
            "url": "https://www.happylapiz.cl/collections/all",
            "bg_color": "#111111",
            "text_color": "#ffffff",
            "align": "center",
            "border_radius": "0",
            "font_size": "16",
            "letter_spacing": "1",
            "font_family": FF,
            "full_width": True,
        },
    },
    # ── Otros ────────────────────────────────────────────────────────────────
    {
        "name": "Grilla — Productos recomendados",
        "block_type": "product_grid",
        "sort_order": 170,
        "props": {
            "variable": "recommended_products_html",
            "bg_color": "#ffffff",
            "btn_color": "#f97316",
            "padding_y": "16",
            "padding_x": "0",
        },
    },
    {
        "name": "Cupón — Código descuento",
        "block_type": "coupon",
        "sort_order": 180,
        "props": {
            "title": "Tu código de descuento",
            "code": "{{ coupon_code }}",
            "subtitle": "Úsalo en tu próxima compra",
            "bg_color": "#f9fafb",
            "text_color": "#111111",
            "border_color": "#682ae7",
            "code_bg": "#ffffff",
            "code_color": "#682ae7",
            "padding_y": "28",
        },
    },
    {
        "name": "Divisor — Línea suave",
        "block_type": "divider",
        "sort_order": 190,
        "props": {"color": "#f3f4f6", "thickness": "1", "padding_y": "8"},
    },
    {
        "name": "Pie — Footer Happy Lápiz",
        "block_type": "text",
        "sort_order": 200,
        "props": {
            "content": (
                "<p style=\"margin:0 0 8px;text-align:center;\">"
                f"<img src=\"{HL_LOGO}\" alt=\"Happy L&#225;piz\" width=\"100\" "
                "style=\"height:auto;display:inline-block;opacity:0.5;\" /></p>"
                "<p style=\"margin:0;font-size:12px;color:#d1d5db;text-align:center;\">"
                "Juguetes educativos &middot; Chile</p>"
            ),
            "bg_color": "#ffffff",
            "text_color": "#d1d5db",
            "padding_y": "20",
            "padding_x": "32",
            "font_family": FF,
        },
    },
    {
        "name": "Pie — Footer con baja",
        "block_type": "text",
        "sort_order": 205,
        "props": {
            "content": (
                "<div style=\"border-top:1px solid #f3f4f6;padding-top:20px;text-align:center;\">"
                f"<img src=\"{HL_LOGO}\" alt=\"Happy L&#225;piz\" width=\"100\" "
                "style=\"height:auto;display:inline-block;opacity:0.5;margin-bottom:10px;\" />"
                "<p style=\"font-size:12px;color:#d1d5db;margin:4px 0;\">Juguetes educativos &middot; Chile</p>"
                "<p style=\"font-size:12px;color:#d1d5db;margin:6px 0;\">"
                "<a href=\"##unsub##\" style=\"color:#d1d5db;\">Cancelar suscripci&#243;n</a></p>"
                "</div>"
            ),
            "bg_color": "#ffffff",
            "text_color": "#d1d5db",
            "padding_y": "20",
            "padding_x": "32",
            "font_family": FF,
        },
    },
]

DEPRECATED_BLOCK_NAMES = [
    "Hero — Banner vacaciones (naranja/morado)",
]

# Alias for backward compatibility
DEFAULT_FAVORITE_BLOCKS = BLOCK_CATALOG


STARTER_SORT_ORDER_MAX = 49


def _label_block(text: str, block_id: str) -> dict:
    return make_block(
        "text",
        {
            "content": (
                f"<p style=\"margin:0;font-size:11px;font-weight:700;text-transform:uppercase;"
                f"letter-spacing:1.2px;color:#9ca3af;text-align:center;font-family:{FF};\">"
                f"&#9472;&#9472; {text} &#9472;&#9472;</p>"
            ),
            "bg_color": "#f9fafb",
            "text_color": "#9ca3af",
            "padding_y": "12",
            "padding_x": "32",
            "font_family": FF,
        },
        block_id,
    )


def _block_from_catalog_entry(entry: dict, block_id: str) -> dict:
    return make_block(entry["block_type"], entry["props"], block_id)


def _catalog(name: str) -> dict:
    return next(b for b in BLOCK_CATALOG if b["name"] == name)


def vacaciones_blocks() -> list[dict]:
    """Plantilla Vacaciones compuesta bloque por bloque (sin HTML monolítico)."""
    return [
        _block_from_catalog_entry(_catalog("Hero — Vacaciones con logo centrado"), "hero_vac_1"),
        _block_from_catalog_entry(_catalog("Párrafo — Vacaciones (cuerpo)"), "body_vac_1"),
        _block_from_catalog_entry(_catalog("Caja — Ideas para vacaciones (naranja claro)"), "ideas_vac_1"),
        _block_from_catalog_entry(_catalog("Botón CTA — Morado vacaciones"), "cta_vac_1"),
        _block_from_catalog_entry(_catalog("Nota — Envío centrada"), "note_vac_1"),
        _block_from_catalog_entry(_catalog("Caja — Tip morado"), "tip_vac_1"),
        _block_from_catalog_entry(_catalog("Pie — Footer con baja"), "footer_vac_1"),
    ]


def bienvenida_blocks() -> list[dict]:
    """Plantilla Bienvenida compuesta bloque por bloque."""
    return [
        _block_from_catalog_entry(_catalog("Encabezado — Logo Happy Lápiz"), "hdr_bien_1"),
        _block_from_catalog_entry(_catalog("Hero — Morado con logo centrado"), "hero_bien_1"),
        make_block(
            "text",
            {
                "content": (
                    f"<p style=\"margin:0;font-size:15px;line-height:1.75;color:#374151;font-family:{FF};\">"
                    "Hola {{ first_name or nombre or 'amigo/a' }}, ahora eres parte de nuestra comunidad. "
                    "Desde aqu&#237; te haremos llegar novedades del cat&#225;logo, ofertas exclusivas "
                    "y contenido educativo pensado para el desarrollo de los peque&#241;os."
                    "</p>"
                ),
                "bg_color": "#ffffff",
                "text_color": "#374151",
                "padding_y": "28",
                "padding_x": "32",
                "font_family": FF,
            },
            "body_bien_1",
        ),
        make_block(
            "text",
            {
                "content": (
                    "<div style=\"background:#f5f3ff;border-radius:14px;padding:24px;\">"
                    "<p style=\"font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;"
                    "color:#7c3aed;margin:0 0 14px;\">&#191;Qu&#233; encontrar&#225;s?</p>"
                    "<p style=\"margin:0 0 10px;font-size:14px;color:#111;\"><strong>&#127981; Juguetes educativos</strong> "
                    "<span style=\"color:#6b7280;\">curados para cada etapa.</span></p>"
                    "<p style=\"margin:0 0 10px;font-size:14px;color:#111;\"><strong>&#127873; Ofertas primero</strong> "
                    "<span style=\"color:#6b7280;\">acceso anticipado a lanzamientos.</span></p>"
                    "<p style=\"margin:0;font-size:14px;color:#111;\"><strong>&#128218; Tips de crianza</strong> "
                    "<span style=\"color:#6b7280;\">ideas para estimular a tus hijos.</span></p>"
                    "</div>"
                ),
                "bg_color": "#ffffff",
                "text_color": "#374151",
                "padding_y": "8",
                "padding_x": "32",
                "font_family": FF,
            },
            "benefits_bien_1",
        ),
        _block_from_catalog_entry(_catalog("Botón CTA — Morado"), "cta_bien_1"),
        _block_from_catalog_entry(_catalog("Pie — Footer con baja"), "footer_bien_1"),
    ]


def galeria_blocks() -> list[dict]:
    """Plantilla galería: todas las opciones del catálogo para elegir favoritos."""
    blocks: list[dict] = [
        make_block(
            "text",
            {
                "content": (
                    f"<p style=\"margin:0;font-size:16px;font-weight:700;color:#111;text-align:center;font-family:{FF};\">"
                    "Galer&#237;a de bloques Happy L&#225;piz</p>"
                    f"<p style=\"margin:8px 0 0;font-size:13px;color:#6b7280;text-align:center;line-height:1.5;font-family:{FF};\">"
                    "Revisa cada opci&#243;n abajo. Las que te gusten, gu&#225;rdalas como favorito desde el panel derecho. "
                    "<strong>No env&#237;es esta plantilla tal cual.</strong>"
                    "</p>"
                ),
                "bg_color": "#ffffff",
                "text_color": "#374151",
                "padding_y": "28",
                "padding_x": "32",
                "font_family": FF,
            },
            "galeria_intro",
        ),
    ]
    idx = 0
    for entry in BLOCK_CATALOG:
        blocks.append(_label_block(entry["name"], f"galeria_lbl_{idx}"))
        blocks.append(_block_from_catalog_entry(entry, f"galeria_blk_{idx}"))
        blocks.append(
            make_block("divider", {"color": "#e5e7eb", "thickness": "1", "padding_y": "4"}, f"galeria_div_{idx}")
        )
        idx += 1
    return blocks


VACACIONES_NAME = "Vacaciones — Juguetes para tus peques"
VACACIONES_SUBJECT = "{{nombre or 'Hola'}}, ideas para las vacaciones de tus pequeños ☀️"
VACACIONES_PREVIEW = "Juegos, creatividad y aprendizaje para que disfruten al máximo sus vacaciones."

BIENVENIDA_NAME = "Bienvenida — Happy Lápiz"
BIENVENIDA_SUBJECT = "{{nombre or 'amigo/a'}}, bienvenido/a a Happy Lápiz 🎨"
BIENVENIDA_PREVIEW = "Nos alegra tenerte aquí. Descubre nuestro catálogo de juguetes educativos."

GALERIA_NAME = "Galería — Opciones de bloques (no enviar)"
GALERIA_SUBJECT = "Galería interna — opciones de bloques"
GALERIA_PREVIEW = "Plantilla de referencia para elegir bloques favoritos. No usar en campañas."

BIRTHDAY_30_NAME = "Cumpleaños regalado — 30 días antes"
BIRTHDAY_30_SUBJECT = "{{ nombre_regalado or 'Tu peque' }} cumple en 30 días — regalo doble en Happy Lápiz 🎁"
BIRTHDAY_30_PREVIEW = "Compra 1 regalo y enviamos 1 producto de regalo. Tu código exclusivo está aquí."

BIRTHDAY_15_NAME = "Cumpleaños regalado — 15 días antes"
BIRTHDAY_15_SUBJECT = "Faltan 15 días para el cumple de {{ nombre_regalado or 'tu peque' }} — código REGALO 🎂"
BIRTHDAY_15_PREVIEW = "Aún estás a tiempo de elegir el regalo perfecto con nuestra promo 1+1."

BIRTHDAY_7_NAME = "Cumpleaños regalado — 7 días antes"
BIRTHDAY_7_SUBJECT = "¡Última semana! El cumple de {{ nombre_regalado or 'tu peque' }} está a la vuelta 🎈"
BIRTHDAY_7_PREVIEW = "Últimos días para usar tu código y recibir un regalo extra para el cumpleañero."


def _regalo_promo_box() -> str:
    return (
        "<div style=\"background:#fdf2f8;border:1px solid #fbcfe8;border-radius:14px;padding:24px;\">"
        "<p style=\"font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;"
        "color:#db2777;margin:0 0 10px;\">Promoci&#243;n cumplea&#241;os 1+1</p>"
        "<p style=\"margin:0 0 8px;font-size:17px;font-weight:800;color:#111;line-height:1.3;\">"
        "Compra 1 regalo &#127873; y enviamos 1 regalo para "
        "{{ nombre_regalado or 'tu peque' }}</p>"
        f"<p style=\"margin:0;font-size:14px;color:#6b7280;line-height:1.6;font-family:{FF};\">"
        "Usa tu c&#243;digo al comprar cualquier producto. Nosotros agregamos un producto de regalo "
        "para sorprender a {{ relacion or nombre_regalado or 'tu peque' }} en su cumplea&#241;os."
        "</p></div>"
    )


def _birthday_hero(days: int, *, urgent: bool = False) -> str:
    if urgent:
        subtitle = "&#218;ltima semana"
        title = (
            "&#161;El cumple de {{ nombre_regalado or 'tu peque' }} "
            "est&#225; a la vuelta de la esquina!"
        )
        body = (
            "Hola {{ first_name or nombre }}, quedan pocos d&#237;as. "
            "Aprovecha tu c&#243;digo REGALO antes de que se acabe el tiempo."
        )
        bg = "#be185d"
    elif days <= 15:
        subtitle = f"Faltan {days} d&#237;as"
        title = (
            "El cumple de {{ nombre_regalado or 'tu peque' }} "
            "se acerca &#127874;"
        )
        body = (
            "Hola {{ first_name or nombre }}, es buen momento para elegir el regalo "
            "y activar la promo: t&#250; compras uno, nosotros enviamos otro."
        )
        bg = "#db2777"
    else:
        subtitle = f"Faltan {days} d&#237;as"
        title = (
            "&#161;Ya falta poco para el cumple de {{ nombre_regalado or 'tu peque' }}!"
        )
        body = (
            "Hola {{ first_name or nombre }}, queremos ayudarte a sorprender a "
            "{{ nombre_regalado or 'tu peque' }} con un regalo que estimule su creatividad."
        )
        bg = "#ec4899"
    return _hero_logo_content(
        subtitle,
        title,
        body,
        logo_width=92,
        logo_margin_bottom=12,
        subtitle_size=11,
        title_size=21,
        body_size=14,
        text_gap=10,
    )


def _birthday_coupon_block() -> dict:
    return make_block(
        "coupon",
        {
            "title": "Tu c&#243;digo exclusivo REGALO",
            "code": "{{ coupon_code }}",
            "subtitle": "Sin descuento en precio — identifica tu pedido para el regalo 1+1",
            "bg_color": "#ffffff",
            "text_color": "#111111",
            "border_color": "#db2777",
        },
        "coupon_bday",
    )


def _birthday_cta_block(block_id: str) -> dict:
    return make_block(
        "button",
        {
            "text": "Elegir regalo con beneficio 1+1 →",
            "url": "https://www.happylapiz.cl/discount/{{ coupon_code }}?redirect=/collections/all",
            "bg_color": "#db2777",
            "text_color": "#ffffff",
            "align": "center",
            "border_radius": "30",
            "font_size": "15",
            "letter_spacing": "0",
            "font_family": FF,
            "full_width": False,
        },
        block_id,
    )


def _birthday_blocks(days: int, *, urgent: bool = False) -> list[dict]:
    """Plantilla de recordatorio de cumpleaños para N días antes."""
    if days <= 7 or urgent:
        body_extra = (
            f"<p style=\"margin:0;font-size:15px;line-height:1.75;color:#374151;font-family:{FF};\">"
            "<strong>Recuerda:</strong> al usar tu c&#243;digo en el checkout, nuestro equipo identifica "
            "tu pedido y agrega un producto de regalo para {{ nombre_regalado or 'tu peque' }}. "
            "&#161;No dejes pasar esta semana!"
            "</p>"
        )
        tip = (
            "<div style=\"background:#fff1f2;border-radius:12px;padding:18px 22px;text-align:center;\">"
            "<p style=\"font-size:14px;color:#be123c;margin:0;line-height:1.6;\">"
            "<strong>&#9200; &#218;ltimos d&#237;as:</strong> env&#237;o a todo Chile. "
            "Compra con tiempo para que el regalo llegue antes del cumplea&#241;os."
            "</p></div>"
        )
    elif days <= 15:
        body_extra = (
            f"<p style=\"margin:0;font-size:15px;line-height:1.75;color:#374151;font-family:{FF};\">"
            "En <strong>Happy L&#225;piz</strong> encontrar&#225;s juguetes educativos por edad e intereses. "
            "Con tu c&#243;digo REGALO activamos el beneficio: <em>compras t&#250; un regalo, "
            "nosotros enviamos otro</em> para {{ nombre_regalado or 'tu peque' }}."
            "</p>"
        )
        tip = (
            "<div style=\"background:#f5f3ff;border-radius:12px;padding:18px 22px;text-align:center;\">"
            "<p style=\"font-size:14px;color:#5b21b6;margin:0;line-height:1.6;\">"
            "<strong>&#128161; Tip:</strong> Filtra por edad en la tienda y encuentra el regalo ideal en minutos."
            "</p></div>"
        )
    else:
        body_extra = (
            f"<p style=\"margin:0;font-size:15px;line-height:1.75;color:#374151;font-family:{FF};\">"
            "Todav&#237;a tienes tiempo para planear una sorpresa especial. "
            "Registra tu pedido con el c&#243;digo de abajo y nosotros nos encargamos del regalo extra "
            "para {{ nombre_regalado or 'tu peque' }} — sin descuento en el precio, "
            "solo el beneficio 1+1."
            "</p>"
        )
        tip = _catalog("Caja — Tip morado")["props"]["content"]

    hero_bg = "#be185d" if urgent else ("#db2777" if days <= 15 else "#ec4899")
    return [
        make_block(
            "text",
            {
                "content": _birthday_hero(days, urgent=urgent),
                "bg_color": hero_bg,
                "text_color": "#ffffff",
                "padding_y": "28",
                "padding_x": "28",
                "font_family": FF,
            },
            f"hero_bday_{days}",
        ),
        make_block(
            "text",
            {
                "content": body_extra,
                "bg_color": "#ffffff",
                "text_color": "#374151",
                "padding_y": "24",
                "padding_x": "32",
                "font_family": FF,
            },
            f"body_bday_{days}",
        ),
        make_block(
            "text",
            {
                "content": _regalo_promo_box(),
                "bg_color": "#ffffff",
                "text_color": "#374151",
                "padding_y": "8",
                "padding_x": "32",
                "font_family": FF,
            },
            f"promo_bday_{days}",
        ),
        _birthday_coupon_block(),
        _birthday_cta_block(f"cta_bday_{days}"),
        make_block(
            "text",
            {
                "content": tip,
                "bg_color": "#ffffff",
                "text_color": "#5b21b6",
                "padding_y": "8",
                "padding_x": "32",
                "font_family": FF,
            },
            f"tip_bday_{days}",
        ),
        _block_from_catalog_entry(_catalog("Pie — Footer con baja"), f"footer_bday_{days}"),
    ]


def birthday_reminder_30_blocks() -> list[dict]:
    return _birthday_blocks(30)


def birthday_reminder_15_blocks() -> list[dict]:
    return _birthday_blocks(15)


def birthday_reminder_7_blocks() -> list[dict]:
    return _birthday_blocks(7, urgent=True)
