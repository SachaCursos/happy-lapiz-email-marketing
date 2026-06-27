"""Normalize gift-recipient variables for email templates and automations."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Any

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


# ── Field aliases + form_submission merge (campaigns + birthday automations) ──

FIELD_ALIASES: dict[str, list[str]] = {
    "fecha_nacimiento": [
        "fecha_nacimiento",
        "fecha_nacimiento_regalado",
        "cual_es_su_fecha_de_nacimiento",
        "destinatario_cumpleanos",
    ],
    "fecha_nacimiento_regalado": [
        "fecha_nacimiento_regalado",
        "fecha_nacimiento",
        "cual_es_su_fecha_de_nacimiento",
        "destinatario_cumpleanos",
    ],
    "fecha_nacimiento2": [
        "fecha_nacimiento2",
        "fecha_nacimiento_regalado2",
    ],
    "fecha_nacimiento_regalado2": [
        "fecha_nacimiento_regalado2",
        "fecha_nacimiento2",
    ],
    "nombre_regalado": [
        "nombre_regalado",
        "destinatario_nombre",
    ],
    "nombre_regalado2": [
        "nombre_regalado2",
        "destinatario_nombre2",
    ],
    "relacion": [
        "relacion",
        "relacion_regalado",
        "para_quien",
    ],
    "relacion_regalado": [
        "relacion_regalado",
        "relacion",
        "para_quien",
    ],
    "relacion2": [
        "relacion2",
        "relacion_regalado2",
        "para_quien2",
    ],
    "relacion_regalado2": [
        "relacion_regalado2",
        "relacion2",
    ],
}


def get_regalado_field(data: dict, field: str) -> str:
    """Read a regalado field from a merged dict, trying known aliases."""
    for key in FIELD_ALIASES.get(field, [field]):
        v = data.get(key)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def parse_birthday_mmdd(raw_date: str) -> str | None:
    """Return MM-DD for a birthday string, or None if unparseable."""
    raw = (raw_date or "").strip()
    if not raw:
        return None
    try:
        if len(raw) == 10 and raw[4] in ("-", "/"):
            bday = datetime.strptime(raw.replace("/", "-"), "%Y-%m-%d").date()
            return f"{bday.month:02d}-{bday.day:02d}"
        for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                bday = datetime.strptime(raw, fmt).date()
                return f"{bday.month:02d}-{bday.day:02d}"
            except ValueError:
                continue
    except Exception:
        pass
    return None


def submission_to_regalado_dict(submission: Any) -> dict:
    """Map a FormSubmission row to canonical regalado field keys."""
    if not submission:
        return {}

    out: dict[str, str] = {}
    pairs = (
        ("relacion_regalado", submission.relacion_regalado),
        ("relacion", submission.relacion_regalado),
        ("para_quien", submission.relacion_regalado),
        ("nombre_regalado", submission.nombre_regalado),
        ("destinatario_nombre", submission.nombre_regalado),
        ("fecha_nacimiento_regalado", submission.fecha_nacimiento_regalado),
        ("fecha_nacimiento", submission.fecha_nacimiento_regalado),
        ("cual_es_su_fecha_de_nacimiento", submission.fecha_nacimiento_regalado),
        ("relacion_regalado2", submission.relacion_regalado2),
        ("relacion2", submission.relacion_regalado2),
        ("nombre_regalado2", submission.nombre_regalado2),
        ("destinatario_nombre2", submission.nombre_regalado2),
        ("fecha_nacimiento_regalado2", submission.fecha_nacimiento_regalado2),
        ("fecha_nacimiento2", submission.fecha_nacimiento_regalado2),
    )
    for key, val in pairs:
        if val and str(val).strip():
            out[key] = str(val).strip()

    ed = getattr(submission, "extra_data", None) or {}
    if isinstance(ed, dict):
        for k in ("para_quien", "destinatario_nombre", "cual_es_su_fecha_de_nacimiento", "destinatario_cumpleanos"):
            if ed.get(k) and k not in out:
                out[k] = str(ed[k]).strip()
        if ed.get("regalados"):
            out["regalados"] = ed["regalados"]

    return out


def merge_regalado_sources(custom_fields: dict | None, submission: Any) -> dict:
    """Merge contact custom_fields with form_submission data (submission fills gaps)."""
    data: dict = {}
    if isinstance(custom_fields, dict):
        data.update({k: v for k, v in custom_fields.items() if v is not None and v != ""})
    overlay = submission_to_regalado_dict(submission)
    for key, val in overlay.items():
        if key == "regalados":
            if not data.get("regalados"):
                data["regalados"] = val
            continue
        if val and not data.get(key):
            data[key] = val
    return data


def infer_relation_field(name_field: str, relation_field: str) -> str:
    """Default relation2 when the automation targets the second regalado."""
    if relation_field != "relacion":
        return relation_field
    if name_field in ("nombre_regalado2", "destinatario_nombre2"):
        return "relacion2"
    return relation_field
