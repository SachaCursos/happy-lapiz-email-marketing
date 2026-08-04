"""Contact.regalados replaced form_submissions' 6 flat columns (capped at 2
recipients) as the source of truth for the birthday/REGALO automation. These
cover the merge/normalize logic and the up-to-5 template variable expansion —
no DB needed, these are pure functions over plain dicts and an in-memory
Contact instance."""
from datetime import date

from app.models.contact import Contact
from app.services.regalado_vars import (
    MAX_REGALADOS,
    merge_regalados_into_contact,
    parse_full_birthdate_iso,
    prepare_regalado_vars,
)
from app.services.birthday_enrollment import first_send_date, iter_regalado_birthdays


def make_contact(**overrides) -> Contact:
    defaults = dict(email="test@example.com", opted_in=True)
    defaults.update(overrides)
    return Contact(**defaults)


# ── parse_full_birthdate_iso ─────────────────────────────────────────────────

def test_parse_full_birthdate_iso_day_first_formats():
    assert parse_full_birthdate_iso("19-06-2020") == "2020-06-19"
    assert parse_full_birthdate_iso("19/06/2020") == "2020-06-19"
    assert parse_full_birthdate_iso("2020-06-19") == "2020-06-19"


def test_parse_full_birthdate_iso_unparseable_returns_none():
    assert parse_full_birthdate_iso("no es una fecha") is None
    assert parse_full_birthdate_iso("") is None
    assert parse_full_birthdate_iso(None) is None


# ── merge_regalados_into_contact ─────────────────────────────────────────────

def test_merge_adds_new_regalado():
    contact = make_contact()
    changed = merge_regalados_into_contact(contact, [
        {"relacion": "Para mi hijo", "nombre": "Mateo", "fecha": "19-06-2020"},
    ])
    assert changed is True
    assert contact.regalados == [
        {"relacion": "Para mi hijo", "nombre": "Mateo", "fecha_nacimiento": "2020-06-19"},
    ]


def test_merge_resubmitting_same_name_refreshes_not_duplicates():
    contact = make_contact()
    merge_regalados_into_contact(contact, [
        {"relacion": "Para mi hijo", "nombre": "Mateo", "fecha": "19-06-2020"},
    ])
    merge_regalados_into_contact(contact, [
        {"relacion": "Para mi hijo", "nombre": "mateo", "fecha": "20-06-2020"},
    ])
    assert len(contact.regalados) == 1
    assert contact.regalados[0]["fecha_nacimiento"] == "2020-06-20"


def test_merge_accumulates_distinct_people_across_calls():
    contact = make_contact()
    merge_regalados_into_contact(contact, [{"relacion": "hijo", "nombre": "Mateo", "fecha": "19-06-2020"}])
    merge_regalados_into_contact(contact, [{"relacion": "sobrina", "nombre": "Ale", "fecha": "01-01-2019"}])
    merge_regalados_into_contact(contact, [{"relacion": "nieto", "nombre": "Diego", "fecha": "03-03-2021"}])
    names = [r["nombre"] for r in contact.regalados]
    assert names == ["Mateo", "Ale", "Diego"]


def test_merge_caps_at_max_regalados():
    contact = make_contact()
    for i in range(MAX_REGALADOS + 3):
        merge_regalados_into_contact(contact, [
            {"relacion": "amigo", "nombre": f"Persona{i}", "fecha": "01-01-2020"},
        ])
    assert len(contact.regalados) == MAX_REGALADOS
    # keeps the most recently-added distinct people
    names = [r["nombre"] for r in contact.regalados]
    assert names == [f"Persona{i}" for i in range(3, MAX_REGALADOS + 3)]


def test_merge_no_change_returns_false():
    contact = make_contact()
    merge_regalados_into_contact(contact, [{"relacion": "hijo", "nombre": "Mateo", "fecha": "19-06-2020"}])
    changed = merge_regalados_into_contact(contact, [{"relacion": "hijo", "nombre": "Mateo", "fecha": "19-06-2020"}])
    assert changed is False


# ── prepare_regalado_vars: up to 5 slots ─────────────────────────────────────

def test_prepare_regalado_vars_expands_up_to_five_slots():
    vars_ = {
        "regalados": [
            {"relacion": "Para mi hijo", "nombre": "Mateo", "fecha_nacimiento": "2020-06-19"},
            {"relacion": "Para mi sobrina", "nombre": "Ale", "fecha_nacimiento": "2019-01-01"},
            {"relacion": "Para mi nieto", "nombre": "Diego", "fecha_nacimiento": "2021-03-03"},
            {"relacion": "Para mi hija", "nombre": "Sofia", "fecha_nacimiento": "2018-05-05"},
            {"relacion": "Para mi amiga", "nombre": "Vale", "fecha_nacimiento": "2017-07-07"},
        ],
    }
    out = prepare_regalado_vars(vars_)
    assert out["nombre_regalado"] == "Mateo"
    assert out["nombre_regalado2"] == "Ale"
    assert out["nombre_regalado3"] == "Diego"
    assert out["nombre_regalado4"] == "Sofia"
    assert out["nombre_regalado5"] == "Vale"
    assert out["nombres_regalados"] == "Mateo y Ale y Diego y Sofia y Vale"
    assert out["relacion_regalado3"] == "tu nieto"
    assert out["fecha_nacimiento_regalado5"] == "2017-07-07"


def test_prepare_regalado_vars_backward_compat_two_slots_from_flat_keys():
    """Callers that set the legacy flat keys directly (no `regalados` list) —
    the exact pre-refactor call shape — still work."""
    vars_ = {
        "nombre_regalado": "Mateo",
        "relacion_regalado": "Para mi hijo",
        "nombre_regalado2": "Ale",
        "relacion_regalado2": "Para mi sobrina",
    }
    out = prepare_regalado_vars(vars_)
    assert out["nombre_regalado"] == "Mateo"
    assert out["nombre_regalado2"] == "Ale"
    assert out["nombre_regalado3"] == ""
    assert out["nombres_regalados"] == "Mateo y Ale"


# ── iter_regalado_birthdays: N-slot loop + legacy fallback ──────────────────

def test_iter_regalado_birthdays_loops_full_list():
    data = {"regalados": [
        {"nombre": "Mateo", "relacion": "hijo", "fecha_nacimiento": "2020-06-19"},
        {"nombre": "Ale", "relacion": "sobrina", "fecha_nacimiento": "2019-08-04"},
        {"nombre": "Diego", "relacion": "nieto", "fecha_nacimiento": "2021-12-25"},
    ]}
    results = list(iter_regalado_birthdays(data))
    assert len(results) == 3
    labels = [r[0] for r in results]
    assert labels == ["fecha_nacimiento_regalado", "fecha_nacimiento_regalado2", "fecha_nacimiento_regalado3"]
    assert results[2][2]["nombre"] == "Diego"


def test_iter_regalado_birthdays_legacy_flat_keys_fallback():
    data = {
        "fecha_nacimiento_regalado": "19-06-2020",
        "nombre_regalado": "Mateo",
        "relacion_regalado": "hijo",
    }
    results = list(iter_regalado_birthdays(data))
    assert len(results) == 1
    assert results[0][0] == "fecha_nacimiento_regalado"
    assert results[0][2]["nombre"] == "Mateo"


def test_iter_regalado_birthdays_dedupes_same_mmdd():
    data = {"regalados": [
        {"nombre": "Mateo", "relacion": "hijo", "fecha_nacimiento": "2020-06-19"},
        {"nombre": "Twin", "relacion": "hijo", "fecha_nacimiento": "2022-06-19"},
    ]}
    results = list(iter_regalado_birthdays(data))
    assert len(results) == 1


# ── first_send_date: leap-day birthdays in non-leap years ──────────────────
# Found live in production logs: date(2026, 2, 29) raises ValueError, which
# silently dropped that regalado's reminder every single run (caught by an
# outer try/except at the automation-trigger level, so it never surfaced as
# an error to anyone — just a birthday reminder that never sent).

def test_first_send_date_leap_day_in_non_leap_year_falls_back_to_feb_28():
    result = first_send_date("29-02-2020", 30, date(2026, 1, 1))
    assert result is not None
    bday, first_send = result
    assert bday == date(2026, 2, 28)


def test_first_send_date_leap_day_in_leap_year_stays_feb_29():
    result = first_send_date("29-02-2020", 30, date(2028, 1, 1))
    assert result is not None
    bday, _first_send = result
    assert bday == date(2028, 2, 29)
