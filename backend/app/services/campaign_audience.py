from typing import List, Optional

from sqlmodel import Session, select

from app.models.contact import Contact
from app.models.segment import Segment
from app.services.segment_evaluator import count_segment, evaluate_segment, evaluate_segment_ids


def get_campaign_recipient_ids(
    session: Session,
    segment_id: int,
    exclude_segment_ids: Optional[List[int]] = None,
) -> List[int]:
    seg = session.get(Segment, segment_id)
    if not seg:
        return []

    ids = evaluate_segment_ids(seg.conditions, session)
    if not exclude_segment_ids:
        return ids

    excluded: set[int] = set()
    for excl_id in exclude_segment_ids:
        excl_seg = session.get(Segment, excl_id)
        if excl_seg:
            excluded.update(evaluate_segment_ids(excl_seg.conditions, session))

    return [i for i in ids if i not in excluded]


def get_campaign_recipients(
    session: Session,
    segment_id: int,
    exclude_segment_ids: Optional[List[int]] = None,
) -> List[Contact]:
    ids = get_campaign_recipient_ids(session, segment_id, exclude_segment_ids)
    if not ids:
        return []
    return list(session.exec(select(Contact).where(Contact.id.in_(ids))).all())


def count_campaign_recipients(
    session: Session,
    segment_id: int,
    exclude_segment_ids: Optional[List[int]] = None,
) -> dict[str, int]:
    seg = session.get(Segment, segment_id)
    if not seg:
        return {"segment_count": 0, "excluded_count": 0, "recipient_count": 0}

    segment_count = count_segment(seg.conditions, session)
    recipient_ids = get_campaign_recipient_ids(session, segment_id, exclude_segment_ids)
    recipient_count = len(recipient_ids)
    if not exclude_segment_ids:
        return {
            "segment_count": segment_count,
            "excluded_count": 0,
            "recipient_count": recipient_count,
        }

    return {
        "segment_count": segment_count,
        "excluded_count": segment_count - recipient_count,
        "recipient_count": recipient_count,
    }
