from typing import List, Optional

from sqlmodel import Session

from app.models.contact import Contact
from app.models.segment import Segment
from app.services.segment_evaluator import evaluate_segment


def get_campaign_recipients(
    session: Session,
    segment_id: int,
    exclude_segment_ids: Optional[List[int]] = None,
) -> List[Contact]:
    seg = session.get(Segment, segment_id)
    if not seg:
        return []

    contacts = evaluate_segment(seg.conditions, session)
    if not exclude_segment_ids:
        return contacts

    excluded_ids: set[int] = set()
    for excl_id in exclude_segment_ids:
        excl_seg = session.get(Segment, excl_id)
        if excl_seg:
            excluded_ids.update(ct.id for ct in evaluate_segment(excl_seg.conditions, session))

    return [ct for ct in contacts if ct.id not in excluded_ids]


def count_campaign_recipients(
    session: Session,
    segment_id: int,
    exclude_segment_ids: Optional[List[int]] = None,
) -> dict[str, int]:
    seg = session.get(Segment, segment_id)
    if not seg:
        return {"segment_count": 0, "excluded_count": 0, "recipient_count": 0}

    contacts = evaluate_segment(seg.conditions, session)
    segment_count = len(contacts)
    if not exclude_segment_ids:
        return {
            "segment_count": segment_count,
            "excluded_count": 0,
            "recipient_count": segment_count,
        }

    filtered = get_campaign_recipients(session, segment_id, exclude_segment_ids)
    recipient_count = len(filtered)
    return {
        "segment_count": segment_count,
        "excluded_count": segment_count - recipient_count,
        "recipient_count": recipient_count,
    }
