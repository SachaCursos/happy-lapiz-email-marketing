"""Background job scheduler with per-task intervals and overlap protection."""

from __future__ import annotations

import logging
import threading
import time

from sqlmodel import Session, select

from app.database import engine as db_engine
from app.models.campaign import Campaign

logger = logging.getLogger(__name__)

# Seconds between runs per task
INTERVAL_ENROLLMENTS = 60
INTERVAL_FAST_TRIGGERS = 60
INTERVAL_TRIGGERS = 15 * 60
INTERVAL_SCHEDULED_CAMPAIGNS = 2 * 60
INTERVAL_RESUME_SENDS_ACTIVE = 30
INTERVAL_RESUME_SENDS_IDLE = 5 * 60
INTERVAL_EVERGREEN = 60 * 60
INTERVAL_EVERGREEN_FOLLOWUPS = 5 * 60
INTERVAL_SHOPIFY_SYNC = 5 * 60
INTERVAL_ABANDONED_CHECKOUTS = 5 * 60

_scheduler_lock = threading.Lock()
_last_run: dict[str, float] = {}


def _due(name: str, interval_sec: int) -> bool:
    now = time.monotonic()
    if now - _last_run.get(name, 0.0) < interval_sec:
        return False
    _last_run[name] = now
    return True


def _run_guarded(fn, timeout_sec: int, label: str) -> None:
    if not _scheduler_lock.acquire(blocking=False):
        logger.warning("Scheduler busy — skipping %s", label)
        return
    try:
        t = threading.Thread(target=fn, daemon=True, name=f"sched-{label}")
        t.start()
        t.join(timeout=timeout_sec)
        if t.is_alive():
            logger.error("Scheduler task '%s' timed out after %ds (still running)", label, timeout_sec)
    finally:
        _scheduler_lock.release()


def _has_sending_campaigns() -> bool:
    with Session(db_engine) as session:
        return session.exec(
            select(Campaign.id).where(Campaign.status == "sending").limit(1)
        ).first() is not None


def _tick() -> None:
    from app.services.automation_engine import (
        process_ready_enrollments,
        run_fast_automation_triggers,
        run_slow_automation_triggers,
        run_scheduled_campaigns,
        _run_automation_triggers_filtered,
    )
    from app.services.email_sender import resume_pending_campaign_sends
    from app.services.evergreen_engine import process_evergreen_followups, run_evergreen_campaigns
    from app.services.sync_shopify_orders import sync_contacts_from_shopify_orders
    from app.services.sync_abandoned_checkouts import sync_abandoned_checkouts

    def _shopify_sync_and_enroll() -> None:
        sync_contacts_from_shopify_orders()
        _run_automation_triggers_filtered(
            only=frozenset({"placed_order", "ordered_product", "fulfilled_order", "cancelled_order"})
        )

    def _abandoned_sync_and_enroll() -> None:
        sync_abandoned_checkouts()
        _run_automation_triggers_filtered(only=frozenset({"abandoned_cart"}))

    sending_active = _has_sending_campaigns()

    resume_interval = (
        INTERVAL_RESUME_SENDS_ACTIVE if sending_active else INTERVAL_RESUME_SENDS_IDLE
    )
    if _due("resume_sends", resume_interval):
        timeout = 200 if sending_active else 120
        _run_guarded(resume_pending_campaign_sends, timeout, "resume_sends")

    if _due("enrollments", INTERVAL_ENROLLMENTS):
        _run_guarded(process_ready_enrollments, 120, "enrollments")

    if _due("fast_triggers", INTERVAL_FAST_TRIGGERS):
        _run_guarded(run_fast_automation_triggers, 120, "fast_triggers")

    if _due("triggers", INTERVAL_TRIGGERS):
        _run_guarded(run_slow_automation_triggers, 300, "slow_triggers")

    if _due("scheduled_campaigns", INTERVAL_SCHEDULED_CAMPAIGNS):
        _run_guarded(run_scheduled_campaigns, 120, "scheduled_campaigns")

    if _due("evergreen", INTERVAL_EVERGREEN):
        _run_guarded(run_evergreen_campaigns, 300, "evergreen")

    if _due("evergreen_followups", INTERVAL_EVERGREEN_FOLLOWUPS):
        _run_guarded(process_evergreen_followups, 120, "evergreen_followups")

    if _due("shopify_sync", INTERVAL_SHOPIFY_SYNC):
        _run_guarded(_shopify_sync_and_enroll, 180, "shopify_sync")

    if _due("abandoned_checkouts", INTERVAL_ABANDONED_CHECKOUTS):
        _run_guarded(_abandoned_sync_and_enroll, 180, "abandoned_checkouts")


def start_scheduler() -> None:
    def loop():
        time.sleep(10)
        while True:
            try:
                _tick()
            except Exception as exc:
                logger.exception("Scheduler loop error: %s", exc)
            time.sleep(60)

    t = threading.Thread(target=loop, daemon=True, name="automation-scheduler")
    t.start()
    logger.info(
        "Scheduler started (enrollments=%ds, fast_triggers=%ds, slow_triggers=%ds, shopify=%ds)",
        INTERVAL_ENROLLMENTS,
        INTERVAL_FAST_TRIGGERS,
        INTERVAL_TRIGGERS,
        INTERVAL_SHOPIFY_SYNC,
    )
