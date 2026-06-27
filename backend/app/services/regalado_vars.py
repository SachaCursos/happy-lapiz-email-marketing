"""Normalize gift-recipient variables for email templates and automations."""
from __future__ import annotations

import re
import unicodedata

_GIBBERISH_SUBSTRINGS = (
    "asdf", "qwer", "zxcv", "hjkl", "sdfg", "fdsa", "jkl",
    "test", "prueba", "xxx", "aaa", "bbb", "ccc", "ddd",
    "asas", "sjsj", "jsjs", "qqq", "www", "lol", "hola",
)

_RELACION_TU_PAIRS = (
    ("para mi sobrina", "tu sobrina"),
    ("para mi sobrino", "tu sobrino"),
    ("para mi nieta", "tu nieta"),
    ("para mi nieto", "tu nieto"),
    ("para mi hija", "tu hija"),
    ("para mi hijo", "tu hijo"),
    ("para mí", "ti"),
    ("para mi", "ti"),
    ("mi sobrina", "tu sobrina"),
    ("mi sobrino", "tu sobrino"),
    ("mi nieta", "tu nieta"),
    ("mi nieto", "tu nieto"),
    ("mi hija", "tu hija"),
    ("mi hijo", "tu hijo"),
    ("sobrina", "tu sobrina"),
    ("sobrino", "tu sobrino"),
    ("nieta", "tu nieta"),
    ("nieto", "tu nieto"),
    ("hija", "tu hija"),
    ("hijo", "tu hijo"),
    ("amiga", "tu amiga"),
    ("amigo", "tu amigo"),
    ("mamá", "tu mamá"),
    ("mama", "tu mamá"),
    ("papá", "tu papá"),
    ("papa", "tu papá"),
    ("pareja", "tu pareja"),
)

_NAME_PAIR_RE = re.compile(
    r"\{\{\s*nombre_regalado\s*\}\}(?:\s*[,;]?\s*)\{\{\s*nombre_regalado2\s*\}\}",
    re.IGNORECASE,
)


def is_valid_person_name(name: str) -> bool:
    """Return False for obvious gibberish like 'asasjsa'."""
    raw = (name or "").strip()
    if not raw or len(raw) < 2 or len(raw) > 40:
        return False

    letters = "".join(
        c for c in unicodedata.normalize("NFD", raw)
        if unicodedata.category(c) != "Mn" and c.isalpha()
    )
    if len(letters) < 2:
        return False

    low = letters.lower()
    if len(low) >= 3 and not re.search(r"[aeiouáéíóúü]", low):
        return False
    if re.search(r"(.)\1{3,}", low):
        return False
    for pat in _GIBBERISH_SUBSTRINGS:
        if pat in low:
            return False
    if len(low) >= 5 and len(set(low)) / len(low) < 0.38:
        return False
    if len(low) >= 6:
        for i in range(len(low) - 1):
            chunk = low[i : i + 2]
            if low.count(chunk) >= 3:
                return False
    if re.search(r"[bcdfghjklmnpqrstvwxyz]{5,}", low):
        return False
    return True


def sanitize_regalado_name(name: str | None) -> str | None:
    """Return first name if valid, else None."""
    if not name:
        return None
    first = str(name).strip().split()[0]
    return first if is_valid_person_name(first) else None


def relacion_to_tu(relacion: str | None) -> str:
    """'Para mi hijo' / 'Mi hijo' → 'tu hijo' for use in email copy."""
    s = (relacion or "").strip().lower()
    if not s or s in {"otro", "otra"}:
        return ""

    for src, dst in _RELACION_TU_PAIRS:
        if src in s:
            return dst

    normalized = re.sub(r"^para\s+mi\s+", "tu ", s)
    normalized = re.sub(r"^mi\s+", "tu ", normalized)
    if normalized != s:
        return normalized
    return s


def _pick(d: dict, *keys: str) -> str:
    for k in keys:
        v = d.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def _regalado_from_list(regalados: list, idx: int) -> tuple[str, str | None, str]:
    if idx >= len(regalados) or not isinstance(regalados[idx], dict):
        return "", None, ""
    item = regalados[idx]
    rel = relacion_to_tu(_pick(item, "para_quien", "relacion", "relacion_regalado"))
    nombre = sanitize_regalado_name(_pick(item, "destinatario_nombre", "nombre", "nombre_regalado"))
    fecha = _pick(item, "cual_es_su_fecha_de_nacimiento", "destinatario_cumpleanos", "fecha_nacimiento", "fecha")
    return rel, nombre, fecha


def prepare_regalado_vars(vars_: dict) -> dict:
    """Set display-ready regalado variables with name fallback to relation (tu-form)."""
    regalados = vars_.get("regalados")
    if not isinstance(regalados, list):
        regalados = []

    r1_rel = relacion_to_tu(_pick(vars_, "relacion_regalado", "relacion", "para_quien"))
    r2_rel = relacion_to_tu(_pick(vars_, "relacion_regalado2", "relacion2", "para_quien2"))
    n1 = sanitize_regalado_name(_pick(vars_, "nombre_regalado", "destinatario_nombre"))
    n2 = sanitize_regalado_name(_pick(vars_, "nombre_regalado2", "destinatario_nombre2"))
    fecha1 = _pick(vars_, "fecha_nacimiento_regalado", "fecha_nacimiento", "cual_es_su_fecha_de_nacimiento")
    fecha2 = _pick(vars_, "fecha_nacimiento_regalado2", "fecha_nacimiento2", "cual_es_su_fecha_de_nacimiento2")

    if regalados:
        lr, ln, lf = _regalado_from_list(regalados, 0)
        if lr:
            r1_rel = lr
        if ln:
            n1 = ln
        if lf:
            fecha1 = lf or fecha1
        if len(regalados) > 1:
            lr2, ln2, lf2 = _regalado_from_list(regalados, 1)
            if lr2:
                r2_rel = lr2
            if ln2:
                n2 = ln2
            if lf2:
                fecha2 = lf2 or fecha2

    display1 = n1 or r1_rel
    display2 = n2 or r2_rel
    parts = [p for p in (display1, display2) if p]

    vars_.update({
        "nombre_regalado": display1,
        "nombre_regalado2": display2,
        "relacion": r1_rel,
        "relacion_regalado": r1_rel,
        "relacion2": r2_rel,
        "relacion_regalado2": r2_rel,
        "fecha_nacimiento": fecha1,
        "fecha_nacimiento_regalado": fecha1,
        "fecha_nacimiento2": fecha2,
        "fecha_nacimiento_regalado2": fecha2,
        "nombres_regalados": " y ".join(parts),
    })
    return vars_


def preprocess_regalado_template(text: str) -> str:
    """Replace '{{ nombre_regalado }} {{ nombre_regalado2 }}' with '{{ nombres_regalados }}'."""
    if not text:
        return text
    return _NAME_PAIR_RE.sub("{{ nombres_regalados }}", text)


def sanitize_regalados_list(regalados: list[dict]) -> list[dict]:
    """Clear invalid names in parsed regalados before DB insert."""
    out = []
    for item in regalados:
        row = dict(item)
        nombre = _pick(row, "nombre", "destinatario_nombre")
        clean = sanitize_regalado_name(nombre)
        if "nombre" in row:
            row["nombre"] = clean or ""
        if "destinatario_nombre" in row:
            row["destinatario_nombre"] = clean or ""
        out.append(row)
    return out
