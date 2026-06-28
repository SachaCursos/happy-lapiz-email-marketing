#!/usr/bin/env python3
"""Crea plantillas, cupón REGALO y automatización de cumpleaños. Ejecutar desde backend/: python seed_birthday_automation.py"""
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(__file__))

from sqlmodel import Session

from app.database import engine
from app.services.birthday_automation_seed import ensure_birthday_reminder_setup

force = "--force" in sys.argv

with Session(engine) as session:
    result = ensure_birthday_reminder_setup(session, force_templates=force)

print("Seed cumpleaños REGALO completado:")
for k, v in result.items():
    print(f"  {k}: {v}")
print("\nLa automatización queda en estado 'paused' — actívala desde Automatizaciones cuando estés listo.")
