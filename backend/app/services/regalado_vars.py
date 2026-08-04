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


_INVALID_NAME_TOKENS = frozenset({
    "tu", "mi", "su", "el", "la", "los", "las", "un", "una", "unos", "unas",
    "de", "del", "al", "y", "o", "a", "en", "para", "por",
})


def is_valid_person_name(name: str) -> bool:
    """Return False for empty, too-short, vowelless, or obvious gibberish names."""
    raw = (name or "").strip()
    if not raw or len(raw) < 2 or len(raw) > 40:
        return False

    # Relation phrases accidentally stored as nombre (e.g. re-running prepare)
    low_full = raw.lower()
    if low_full.startswith(("tu ", "mi ", "para ", "su ")):
        return False

    letters = "".join(
        c for c in unicodedata.normalize("NFD", raw)
        if unicodedata.category(c) != "Mn" and c.isalpha()
    )
    if len(letters) < 2:
        return False

    low = letters.lower()
    if low in _INVALID_NAME_TOKENS:
        return False
    # Require a vowel — catches "Mt", "Xyz", initials without a real name
    if not re.search(r"[aeiouáéíóúü]", low):
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


MAX_REGALADOS = 5


def prepare_regalado_vars(vars_: dict) -> dict:
    """Set display-ready regalado variables (up to MAX_REGALADOS) with name
    fallback to relation (tu-form). Slots 1-2 also read the legacy flat keys
    (nombre_regalado/relacion_regalado/…) for templates/callers that set those
    directly instead of a `regalados` list; slots 3+ only come from the list."""
    regalados = vars_.get("regalados")
    if not isinstance(regalados, list):
        regalados = []

    legacy_rel = [
        _pick(vars_, "relacion_regalado", "relacion", "para_quien"),
        _pick(vars_, "relacion_regalado2", "relacion2", "para_quien2"),
    ]
    legacy_nombre = [
        sanitize_regalado_name(_pick(vars_, "nombre_regalado", "destinatario_nombre")),
        sanitize_regalado_name(_pick(vars_, "nombre_regalado2", "destinatario_nombre2")),
    ]
    legacy_fecha = [
        _pick(vars_, "fecha_nacimiento_regalado", "fecha_nacimiento", "cual_es_su_fecha_de_nacimiento"),
        _pick(vars_, "fecha_nacimiento_regalado2", "fecha_nacimiento2", "cual_es_su_fecha_de_nacimiento2"),
    ]

    rels: list[str] = []
    nombres: list[str | None] = []
    fechas: list[str] = []
    for i in range(MAX_REGALADOS):
        rel = relacion_to_tu(legacy_rel[i]) if i < 2 else ""
        nombre = legacy_nombre[i] if i < 2 else None
        fecha = legacy_fecha[i] if i < 2 else ""
        if i < len(regalados):
            lr, ln, lf = _regalado_from_list(regalados, i)
            if lr:
                rel = lr
            if ln:
                nombre = ln
            if lf:
                fecha = lf or fecha
        rels.append(rel)
        nombres.append(nombre)
        fechas.append(fecha)

    displays = [nombres[i] or rels[i] for i in range(MAX_REGALADOS)]
    parts = [p for p in displays if p]

    out: dict[str, str] = {"nombres_regalados": " y ".join(parts)}
    for i in range(MAX_REGALADOS):
        suffix = "" if i == 0 else str(i + 1)
        out[f"nombre_regalado{suffix}"] = displays[i]
        out[f"relacion{suffix}"] = rels[i]
        out[f"relacion_regalado{suffix}"] = rels[i]
        out[f"fecha_nacimiento{suffix}"] = fechas[i]
        out[f"fecha_nacimiento_regalado{suffix}"] = fechas[i]
    vars_.update(out)
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


def gift_recipient_to_regalado_dict(recipient: Any) -> dict:
    """Map a GiftRecipient row to canonical regalado field keys."""
    if not recipient:
        return {}
    out: dict[str, str] = {}
    if recipient.nombre_regalado:
        out["nombre_regalado"] = str(recipient.nombre_regalado).strip()
        out["destinatario_nombre"] = out["nombre_regalado"]
    if recipient.relacion:
        out["relacion"] = str(recipient.relacion).strip()
        out["relacion_regalado"] = out["relacion"]
        out["para_quien"] = out["relacion"]
    if recipient.fecha_nacimiento_regalado:
        fecha = str(recipient.fecha_nacimiento_regalado)
        out["fecha_nacimiento_regalado"] = fecha
        out["fecha_nacimiento"] = fecha
        out["cual_es_su_fecha_de_nacimiento"] = fecha
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


# ── Contact.regalados: single source of truth (replaces form_submissions'
# capped-at-2 flat columns and gift_recipients as a read path) ────────────────

def parse_full_birthdate_iso(raw_date: str | None) -> str | None:
    """Parse a free-text birthdate (day-first, same assumption as
    parse_birthday_mmdd) into 'YYYY-MM-DD'. None if unparseable."""
    raw = (raw_date or "").strip()
    if not raw:
        return None
    try:
        if len(raw) == 10 and raw[4] in ("-", "/"):
            return datetime.strptime(raw.replace("/", "-"), "%Y-%m-%d").date().isoformat()
        for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw, fmt).date().isoformat()
            except ValueError:
                continue
    except Exception:
        pass
    return None


def _normalize_name_key(name: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", (name or "").strip().lower())
        if unicodedata.category(c) != "Mn"
    )


def merge_regalados_into_contact(contact: Any, nuevos: list[dict]) -> bool:
    """Merge newly-submitted regalados into contact.regalados: dedupe by
    normalized name (a resubmission for the same person refreshes their data
    in place, it doesn't add a duplicate), capped at MAX_REGALADOS distinct
    people. `nuevos` items use the same loose keys forms.py already parses
    (relacion/para_quien, nombre/destinatario_nombre,
    fecha/fecha_nacimiento/cual_es_su_fecha_de_nacimiento — free text, parsed
    to ISO here). Returns True if contact.regalados changed."""
    existing = contact.regalados if isinstance(contact.regalados, list) else []
    merged: dict[str, dict] = {}
    order: list[str] = []

    def _add(item: dict, *, is_new: bool) -> None:
        relacion = _pick(item, "relacion", "para_quien", "relacion_regalado")
        nombre = sanitize_regalado_name(
            _pick(item, "nombre", "destinatario_nombre", "nombre_regalado")
        ) or ""
        if not nombre and not relacion:
            return
        if is_new:
            fecha = parse_full_birthdate_iso(
                _pick(item, "fecha_nacimiento", "fecha", "cual_es_su_fecha_de_nacimiento")
            )
        else:
            fecha = item.get("fecha_nacimiento") or None
        key = _normalize_name_key(nombre) if nombre else f"_sin_nombre_{len(order)}"
        if key not in merged:
            order.append(key)
        merged[key] = {"relacion": relacion, "nombre": nombre, "fecha_nacimiento": fecha}

    for item in existing:
        if isinstance(item, dict):
            _add(item, is_new=False)
    for item in nuevos:
        if isinstance(item, dict):
            _add(item, is_new=True)

    order = order[-MAX_REGALADOS:]
    new_list = [merged[k] for k in order]

    if new_list == existing:
        return False
    contact.regalados = new_list
    return True
