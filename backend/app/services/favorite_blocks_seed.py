"""Default favorite blocks for Happy Lápiz email templates."""

HL_LOGO = "https://cdn.shopify.com/s/files/1/0556/5343/3495/files/LOGO_HappyLapiz.png?v=1621889822"

DEFAULT_FAVORITE_BLOCKS: list[dict] = [
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
        "name": "Hero — Banner morado",
        "block_type": "text",
        "sort_order": 20,
        "props": {
            "content": (
                "<p style=\"margin:0;font-size:22px;font-weight:800;color:#ffffff;line-height:1.3;"
                "font-family:'Helvetica Neue',Arial,sans-serif;\">&#161;Hola, {{ nombre }}! &#127775;</p>"
                "<p style=\"margin:12px 0 0;font-size:15px;color:#ddd6fe;line-height:1.6;"
                "font-family:'Helvetica Neue',Arial,sans-serif;\">Tu mensaje destacado aqu&#237;.</p>"
            ),
            "bg_color": "#682ae7",
            "text_color": "#ffffff",
            "padding_y": "36",
            "padding_x": "32",
            "font_family": "'Helvetica Neue', Arial, sans-serif",
        },
    },
    {
        "name": "Hero — Banner vacaciones (naranja/morado)",
        "block_type": "text",
        "sort_order": 25,
        "props": {
            "content": (
                "<p style=\"margin:0;font-size:13px;font-weight:600;color:rgba(255,255,255,0.9);"
                "text-transform:uppercase;letter-spacing:1.5px;\">Vacaciones con alegr&#237;a</p>"
                "<p style=\"margin:12px 0 0;font-size:26px;font-weight:800;color:#ffffff;line-height:1.25;\">"
                "&#161;Hola {{ first_name or nombre }}!<br/>Que tus peques disfruten al m&#225;ximo</p>"
                "<p style=\"margin:12px 0 0;font-size:15px;color:#ffffff;line-height:1.6;opacity:0.95;\">"
                "Llegaron las vacaciones: jugar, crear y aprender juntos en casa.</p>"
            ),
            "bg_color": "#f97316",
            "text_color": "#ffffff",
            "padding_y": "40",
            "padding_x": "32",
            "font_family": "'Helvetica Neue', Arial, sans-serif",
        },
    },
    {
        "name": "Párrafo — Cuerpo estándar",
        "block_type": "text",
        "sort_order": 30,
        "props": {
            "content": (
                "<p style=\"margin:0;font-size:15px;line-height:1.75;color:#374151;"
                "font-family:'Helvetica Neue',Arial,sans-serif;\">"
                "Hola {{ first_name or nombre }}, escribe tu mensaje aqu&#237;. "
                "En <strong>Happy L&#225;piz</strong> encontrar&#225;s juguetes educativos para cada edad."
                "</p>"
            ),
            "bg_color": "#ffffff",
            "text_color": "#374151",
            "padding_y": "24",
            "padding_x": "32",
            "font_family": "'Helvetica Neue', Arial, sans-serif",
        },
    },
    {
        "name": "Botón CTA — Morado",
        "block_type": "button",
        "sort_order": 40,
        "props": {
            "text": "Ver catálogo →",
            "url": "https://www.happylapiz.cl",
            "bg_color": "#682ae7",
            "text_color": "#ffffff",
            "align": "center",
            "border_radius": "30",
            "font_size": "15",
            "letter_spacing": "0",
            "font_family": "'Helvetica Neue', Arial, sans-serif",
            "full_width": False,
        },
    },
    {
        "name": "Botón CTA — Barra ancho completo",
        "block_type": "button",
        "sort_order": 45,
        "props": {
            "text": "Comprar ahora",
            "url": "https://www.happylapiz.cl/collections/all",
            "bg_color": "#111111",
            "text_color": "#ffffff",
            "align": "center",
            "border_radius": "0",
            "font_size": "16",
            "letter_spacing": "1",
            "font_family": "'Helvetica Neue', Arial, sans-serif",
            "full_width": True,
        },
    },
    {
        "name": "Grilla — Productos recomendados",
        "block_type": "product_grid",
        "sort_order": 50,
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
        "sort_order": 60,
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
        "sort_order": 70,
        "props": {
            "color": "#f3f4f6",
            "thickness": "1",
            "padding_y": "8",
        },
    },
    {
        "name": "Pie — Footer Happy Lápiz",
        "block_type": "text",
        "sort_order": 80,
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
            "font_family": "'Helvetica Neue', Arial, sans-serif",
        },
    },
]
