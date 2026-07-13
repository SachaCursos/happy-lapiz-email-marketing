#!/usr/bin/env python3
"""
Cleanup script: cancel birthday enrollments whose step timing no longer matches
the regalado birthday (wrong "faltan X días" window).

Covers:
  - Active step 1 enrolled too late (first send already past at enrollment)
  - Active step 2/3 left over after a bad step 1 was sent (birthday passed or
    days-until far from the step's intended window)

Run locally with Railway DB:
    DATABASE_URL="postgresql://..." python3 backend/cleanup_bad_birthday_enrollments.py

Apply:
    python3 backend/cleanup_bad_birthday_enrollments.py --confirm
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from sqlalchemy import text
from sqlmodel import Session, create_engine, select

from app.models.automation import Automation, AutomationEnrollment
from app.services.birthday_enrollment import (
    BIRTHDAY_STEP_TOLERANCE_DAYS,
    birthday_step_still_valid,
    intended_days_before_for_step,
    parse_enrollment_birthday,
)

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_file):
        for line in open(env_file):
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                DATABASE_URL = line.split("=", 1)[1].strip().strip('"').strip("'")
                break

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set. Export it or put it in backend/.env")
    sys.exit(1)

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)


def _eval_as_of(enrollment: AutomationEnrollment, today: date) -> date:
    """Use the scheduled send day when still in the future; otherwise today."""
    if enrollment.next_send_at:
        scheduled = enrollment.next_send_at.date() if hasattr(enrollment.next_send_at, "date") else enrollment.next_send_at
        return scheduled if scheduled > today else today
    return today


def main(dry_run: bool = True) -> None:
    engine = create_engine(DATABASE_URL, echo=False)
    today = datetime.utcnow().date()

    with Session(engine) as session:
        autos = session.exec(
            select(Automation).where(Automation.trigger_type == "birthday_reminder")
        ).all()
        if not autos:
            print("No birthday automations found.")
            return

        print(f"Today: {today}")
        print(f"Found {len(autos)} birthday automation(s): {[a.id for a in autos]}")
        print(f"Tolerance: ±{BIRTHDAY_STEP_TOLERANCE_DAYS} days\n")

        bad: list[dict] = []

        for auto in autos:
            enrollments = session.exec(
                select(AutomationEnrollment).where(
                    AutomationEnrollment.automation_id == auto.id,
                    AutomationEnrollment.status == "active",
                )
            ).all()
            print(f"Auto {auto.id} «{auto.name}»: {len(enrollments)} active enrollment(s)")

            for enr in enrollments:
                as_of = _eval_as_of(enr, today)
                ok, reason = birthday_step_still_valid(
                    auto, enr, as_of=as_of, steps=auto.steps or []
                )
                if ok:
                    continue

                extra = {}
                try:
                    extra = json.loads(enr.extra_vars_json or "{}")
                except Exception:
                    pass
                bday = parse_enrollment_birthday(extra)
                intended = intended_days_before_for_step(auto, enr.next_step, auto.steps or [])
                days_until = (bday - as_of).days if bday else None
                bad.append(
                    {
                        "id": enr.id,
                        "auto_id": auto.id,
                        "auto_name": auto.name,
                        "email": enr.contact_email,
                        "step": enr.next_step,
                        "bday": str(bday) if bday else None,
                        "as_of": str(as_of),
                        "days_until": days_until,
                        "intended": intended,
                        "next_send": str(enr.next_send_at),
                        "reason": reason,
                        "nombre_regalado": (extra.get("nombre_regalado") or "")[:40],
                    }
                )

        print(f"\nInvalid enrollments: {len(bad)}")
        if not bad:
            print("Nothing to clean up. Done.")
            return

        print("\n--- INVALID ENROLLMENTS ---")
        for b in bad:
            print(
                f"  id={b['id']} auto={b['auto_id']} step={b['step']} | {b['email']} | "
                f"regalado={b['nombre_regalado']!r} | bday={b['bday']} | "
                f"as_of={b['as_of']} days_until={b['days_until']} intended={b['intended']} | "
                f"{b['reason']}"
            )

        if dry_run:
            print(
                f"\n[DRY RUN] Would cancel {len(bad)} enrollment(s). "
                "Re-run with --confirm to apply."
            )
            return

        ids_to_cancel = [b["id"] for b in bad]
        session.execute(
            text(
                "UPDATE automation_enrollments SET status = 'cancelled' WHERE id = ANY(:ids)"
            ),
            {"ids": ids_to_cancel},
        )
        session.commit()
        print(f"\nDone. Cancelled {len(ids_to_cancel)} enrollment(s): {ids_to_cancel}")


if __name__ == "__main__":
    dry_run = "--confirm" not in sys.argv
    main(dry_run=dry_run)
