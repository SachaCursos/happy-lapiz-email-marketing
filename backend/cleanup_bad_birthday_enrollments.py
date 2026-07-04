#!/usr/bin/env python3
"""
Cleanup script: cancel birthday enrollments created incorrectly.

An enrollment is wrong when the ideal first-send date (bday - days_before)
was already in the past at the time of enrollment — meaning the step-1 email
would say "faltan 30 días" but the birthday was only days away.

Run locally with Railway DB:
    DATABASE_URL="postgresql://..." python3 backend/cleanup_bad_birthday_enrollments.py

Run on Railway:
    railway run python3 backend/cleanup_bad_birthday_enrollments.py
"""

import json
import os
import sys
from datetime import date, datetime, timedelta

# Allow running from repo root or from backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from sqlmodel import Session, create_engine, select

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    # Try loading from .env in the backend directory
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

# SQLAlchemy needs postgresql:// not postgres://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)


def main(dry_run: bool = True):
    engine = create_engine(DATABASE_URL, echo=False)

    with Session(engine) as session:
        # Find all birthday automation IDs
        rows = session.exec(
            session.exec.__self__.execute(  # type: ignore
                __import__("sqlalchemy").text(
                    "SELECT id FROM automations WHERE trigger_type = 'birthday_reminder'"
                )
            )
        ) if False else None

        from sqlalchemy import text

        auto_ids = [
            r[0]
            for r in session.execute(
                text("SELECT id FROM automations WHERE trigger_type = 'birthday_reminder'")
            ).fetchall()
        ]

        if not auto_ids:
            print("No birthday automations found.")
            return

        print(f"Found {len(auto_ids)} birthday automation(s): {auto_ids}")

        # Get all active enrollments on step 1 (email not yet sent)
        rows = session.execute(
            text(
                """
                SELECT id, automation_id, contact_email, trigger_key,
                       enrolled_at, next_step, status, extra_vars_json
                FROM automation_enrollments
                WHERE automation_id = ANY(:ids)
                  AND status = 'active'
                  AND next_step = 1
                """
            ),
            {"ids": auto_ids},
        ).fetchall()

        print(f"Active step-1 enrollments: {len(rows)}")

        bad = []
        skipped = 0

        for row in rows:
            (
                enr_id,
                auto_id,
                contact_email,
                trigger_key,
                enrolled_at,
                next_step,
                status,
                extra_vars_json,
            ) = row

            # Parse days_before from trigger_key: birthday:{owner}:{field}:{year}:{days_before}
            parts = trigger_key.split(":")
            if len(parts) < 5 or parts[0] != "birthday":
                skipped += 1
                continue

            try:
                days_before = int(parts[-1])
            except ValueError:
                skipped += 1
                continue

            # Get birthday date from extra_vars_json
            try:
                extra_vars = json.loads(extra_vars_json or "{}")
                bday_str = extra_vars.get("fecha_cumpleanos", "")
                if not bday_str:
                    skipped += 1
                    continue
                bday = date.fromisoformat(bday_str)
            except Exception:
                skipped += 1
                continue

            first_send = bday - timedelta(days=days_before)
            enrolled_date = enrolled_at.date() if hasattr(enrolled_at, "date") else enrolled_at

            if first_send < enrolled_date:
                days_late = (enrolled_date - first_send).days
                bad.append(
                    {
                        "id": enr_id,
                        "email": contact_email,
                        "bday": bday_str,
                        "days_before": days_before,
                        "first_send": first_send,
                        "enrolled_at": enrolled_date,
                        "days_late": days_late,
                    }
                )

        print(f"Skipped (bad trigger_key or missing birthday): {skipped}")
        print(f"\nInvalid enrollments found: {len(bad)}")

        if not bad:
            print("Nothing to clean up. Done.")
            return

        print("\n--- INVALID ENROLLMENTS ---")
        for b in bad:
            print(
                f"  id={b['id']} | {b['email']} | bday={b['bday']} | "
                f"first_send={b['first_send']} | enrolled={b['enrolled_at']} "
                f"({b['days_late']}d late)"
            )

        if dry_run:
            print(
                f"\n[DRY RUN] Would cancel {len(bad)} enrollment(s). "
                "Re-run with --confirm to apply."
            )
            return

        answer = input(f"\nCancel these {len(bad)} enrollment(s)? [y/N] ").strip().lower()
        if answer != "y":
            print("Aborted.")
            return

        ids_to_cancel = [b["id"] for b in bad]
        session.execute(
            text(
                "UPDATE automation_enrollments SET status = 'cancelled' WHERE id = ANY(:ids)"
            ),
            {"ids": ids_to_cancel},
        )
        session.commit()
        print(f"Done. Cancelled {len(ids_to_cancel)} enrollment(s).")


if __name__ == "__main__":
    dry_run = "--confirm" not in sys.argv
    main(dry_run=dry_run)
