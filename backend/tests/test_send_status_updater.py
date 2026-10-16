"""Un rebote es final: los eventos que SES emite después (p. ej. el Open que se
dispara al mirar el aviso de MAILER-DAEMON en nuestra bandeja) no deben
convertir un envío rebotado en "opened"."""
from datetime import datetime

import pytest
from sqlmodel import SQLModel

from app.models import segment, template, user  # noqa: F401 — tablas referenciadas por FK
from app.models.automation import AutomationRun
from app.models.campaign import CampaignSend
from app.models.contact import Contact
from app.models.evergreen import EvergreenSend
from app.services import send_status_updater
from app.services.send_status_updater import apply_send_status_update


@pytest.fixture()
def session(sqlite_engine, db_session, monkeypatch):
    SQLModel.metadata.create_all(
        sqlite_engine,
        tables=[Contact.__table__, CampaignSend.__table__, AutomationRun.__table__, EvergreenSend.__table__],
    )
    monkeypatch.setattr(send_status_updater, "_maybe_fix_typo_on_bounce", lambda *a, **k: None)
    return db_session


def _campaign_send(session, status="sent") -> CampaignSend:
    send = CampaignSend(campaign_id=1, contact_id=1, resend_id="msg-1", status=status,
                        sent_at=datetime.utcnow())
    session.add(send)
    session.commit()
    session.refresh(send)
    return send


def test_open_after_bounce_is_ignored(session):
    send = _campaign_send(session)
    apply_send_status_update(session, "msg-1", "bounced", bounce_type="Transient/MailboxFull")
    apply_send_status_update(session, "msg-1", "opened")
    apply_send_status_update(session, "msg-1", "clicked")
    apply_send_status_update(session, "msg-1", "delivered")

    session.refresh(send)
    assert send.status == "bounced"
    assert send.bounce_type == "Transient/MailboxFull"
    assert send.opened_at is None
    assert send.clicked_at is None
    assert send.delivered_at is None


def test_bounce_after_open_still_marks_bounced(session):
    send = _campaign_send(session)
    apply_send_status_update(session, "msg-1", "delivered")
    apply_send_status_update(session, "msg-1", "opened")
    apply_send_status_update(session, "msg-1", "bounced", bounce_type="Permanent/General")

    session.refresh(send)
    assert send.status == "bounced"
    assert send.opened_at is not None


def test_normal_flow_unchanged(session):
    send = _campaign_send(session)
    apply_send_status_update(session, "msg-1", "delivered")
    apply_send_status_update(session, "msg-1", "opened")
    apply_send_status_update(session, "msg-1", "clicked")

    session.refresh(send)
    assert send.status == "clicked"
    assert send.opened_at is not None and send.clicked_at is not None


def test_automation_run_open_after_bounce_is_ignored(session):
    run = AutomationRun(automation_id=1, contact_email="a@b.cl", trigger_key="t", resend_id="msg-2",
                        status="sent")
    session.add(run)
    session.commit()
    apply_send_status_update(session, "msg-2", "bounced")
    apply_send_status_update(session, "msg-2", "opened")

    session.refresh(run)
    assert run.status == "bounced"
    assert run.opened_at is None
