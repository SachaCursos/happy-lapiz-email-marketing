#!/usr/bin/env python3
"""Crea plantillas y automatizaciones (pausadas) del embudo de comportamiento en el
sitio: activo en el sitio / producto visto / producto agregado al carrito.
Ejecutar desde backend/: python seed_funnel_automations.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from sqlmodel import Session

from app.database import engine
from app.services.funnel_automations_seed import ensure_funnel_automations_setup

force = "--force" in sys.argv

with Session(engine) as session:
    result = ensure_funnel_automations_setup(session, force_templates=force)

if result is None:
    print("No se encontró la tienda Happy Lápiz — nada que hacer.")
else:
    print("Seed embudo on-site completado:")
    for a in result["automations"]:
        print(f"  {a['name']}: id={a['id']} status={a['status']} steps={a['steps']}")
    print("\nLas automatizaciones quedan en estado 'paused' — actívalas desde Automatizaciones cuando estés listo.")
