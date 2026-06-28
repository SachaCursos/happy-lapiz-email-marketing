"""Block catalog and template compositions for Happy Lápiz."""

from app.services.template_block_compiler import make_block

HL_LOGO = "https://cdn.shopify.com/s/files/1/0556/5343/3495/files/LOGO_HappyLapiz.png?v=1621889822"
FF = "'Helvetica Neue', Arial, sans-serif"

# sort_order < 50 → se cargan al crear plantilla nueva (starter mínimo)
# sort_order >= 100 → catálogo / galería de opciones


def _hero_logo_content(subtitle: str, title_html: str, body: str) -> str:
    return (
        f'<p style="margin:0 0 20px;text-align:center;">'
        f'<a href="https://www.happylapiz.cl" style="text-decoration:none;">'
        f'<img src="{HL_LOGO}" alt="Happy L&#225;piz" width="120" '
        f'style="height:auto;display:inline-block;" /></a></p>'
        f'<p style="margin:0;font-size:13px;font-weight:600;color:rgba(255,255,255,0.9);'
        f'text-transform:uppercase;letter-spacing:1.5px;text-align:center;">{subtitle}</p>'
        f'<p style="margin:12px 0 0;font-size:26px;font-weight:800;color:#ffffff;line-height:1.25;text-align:center;">'
        f"{title_html}</p>"
        f'<p style="margin:12px 0 0;font-size:15px;color:#ffffff;line-height:1.6;text-align:center;opacity:0.95;">'
        f"{body}</p>"
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
            ),
            "bg_color": "#f97316",
            "text_color": "#ffffff",
            "padding_y": "40",
            "padding_x": "32",
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
                "<table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" border=\"0\" style=\"border-collapse:collapse;\">"
                "<tr><td style=\"padding:8px 0;vertical-align:top;width:36px;font-size:22px;\">&#127912;</td>"
                "<td style=\"padding:8px 0;vertical-align:top;\">"
                "<p style=\"font-weight:700;color:#111;font-size:14px;margin:0 0 2px;\">Arte y manualidades</p>"
                "<p style=\"color:#6b7280;font-size:13px;margin:0;line-height:1.5;\">Pinturas, marcadores y kits creativos.</p>"
                "</td></tr>"
                "<tr><td style=\"padding:8px 0;vertical-align:top;font-size:22px;\">&#129513;</td>"
                "<td style=\"padding:8px 0;vertical-align:top;\">"
                "<p style=\"font-weight:700;color:#111;font-size:14px;margin:0 0 2px;\">Juegos de mesa y puzzles</p>"
                "<p style=\"color:#6b7280;font-size:13px;margin:0;line-height:1.5;\">Diversi&#243;n en familia que desarrolla l&#243;gica.</p>"
                "</td></tr>"
                "<tr><td style=\"padding:8px 0;vertical-align:top;font-size:22px;\">&#128300;</td>"
                "<td style=\"padding:8px 0;vertical-align:top;\">"
                "<p style=\"font-weight:700;color:#111;font-size:14px;margin:0 0 2px;\">Ciencia y exploraci&#243;n</p>"
                "<p style=\"color:#6b7280;font-size:13px;margin:0;line-height:1.5;\">Experimentos y kits para el hogar.</p>"
                "</td></tr></table></div>"
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
