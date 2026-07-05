from typing import List, Optional

from sqlmodel import Session, select

from app.models.contact import Contact
from app.models.segment import Segment
from app.services.segment_evaluator import evaluate_segment_ids


def campaign_segment_ids(campaign) -> List[int]:
    """Return the effective list of segment IDs for a campaign (supports old single segment_id)."""
    ids = campaign.segment_ids or []
    if ids:
        return list(ids)
    if campaign.segment_id:
        return [campaign.segment_id]
    return []


def _resolve_ids(
    session: Session,
    segment_id: Optional[int],
    segment_ids: Optional[List[int]],
) -> set[int]:
    """Union contact IDs from all selected segments."""
    ids_to_use = segment_ids if segment_ids else ([segment_id] if segment_id else [])
    all_ids: set[int] = set()
    for sid in ids_to_use:
        seg = session.get(Segment, sid)
        if seg:
            all_ids.update(evaluate_segment_ids(seg.conditions, session))
    return all_ids


def get_campaign_recipient_ids(
    session: Session,
    segment_id: Optional[int] = None,
    exclude_segment_ids: Optional[List[int]] = None,
    segment_ids: Optional[List[int]] = None,
) -> List[int]:
    all_ids = _resolve_ids(session, segment_id, segment_ids)
    if not all_ids:
        return []

    if not exclude_segment_ids:
        return list(all_ids)

    excluded: set[int] = set()
    for excl_id in exclude_segment_ids:
        excl_seg = session.get(Segment, excl_id)
        if excl_seg:
            excluded.update(evaluate_segment_ids(excl_seg.conditions, session))

    return [i for i in all_ids if i not in excluded]


def get_campaign_recipients(
    session: Session,
    segment_id: Optional[int] = None,
    exclude_segment_ids: Optional[List[int]] = None,
    segment_ids: Optional[List[int]] = None,
) -> List[Contact]:
    ids = get_campaign_recipient_ids(session, segment_id, exclude_segment_ids, segment_ids)
    if not ids:
        return []
    return list(session.exec(select(Contact).where(Contact.id.in_(ids))).all())


def count_campaign_recipients(
    session: Session,
    segment_id: Optional[int] = None,
    exclude_segment_ids: Optional[List[int]] = None,
    segment_ids: Optional[List[int]] = None,
) -> dict[str, int]:
    all_ids = _resolve_ids(session, segment_id, segment_ids)
    segment_count = len(all_ids)

    if not all_ids:
        return {"segment_count": 0, "excluded_count": 0, "recipient_count": 0}

    if not exclude_segment_ids:
        return {"segment_count": segment_count, "excluded_count": 0, "recipient_count": segment_count}

    excluded: set[int] = set()
    for excl_id in exclude_segment_ids:
        excl_seg = session.get(Segment, excl_id)
        if excl_seg:
            excluded.update(evaluate_segment_ids(excl_seg.conditions, session))

    recipient_count = len([i for i in all_ids if i not in excluded])
    return {
        "segment_count": segment_count,
        "excluded_count": segment_count - recipient_count,
        "recipient_count": recipient_count,
    }
