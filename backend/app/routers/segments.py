from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.core.deps import get_current_user, require_editor
from app.models.user import User
from app.models.segment import Segment, SegmentCreate, SegmentRead, SegmentUpdate
from app.services.segment_evaluator import count_segment, evaluate_segment
from app.models.contact import ContactRead

router = APIRouter()


@router.get("", response_model=List[SegmentRead])
def list_segments(session: Session = Depends(get_session), _: User = Depends(get_current_user)):
    segments = session.exec(select(Segment).order_by(Segment.created_at.desc())).all()
    result = []
    for seg in segments:
        read = SegmentRead.model_validate(seg)
        try:
            read.contact_count = count_segment(seg.conditions, session)
        except Exception:
            read.contact_count = 0
        result.append(read)
    return result


@router.post("", response_model=SegmentRead, status_code=201)
def create_segment(
    payload: SegmentCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_editor),
):
    seg = Segment(**payload.model_dump(), created_by=current_user.id)
    session.add(seg)
    session.commit()
    session.refresh(seg)
    read = SegmentRead.model_validate(seg)
    read.contact_count = count_segment(seg.conditions, session)
    return read


@router.get("/{segment_id}", response_model=SegmentRead)
def get_segment(segment_id: int, session: Session = Depends(get_session), _: User = Depends(get_current_user)):
    seg = session.get(Segment, segment_id)
    if not seg:
        raise HTTPException(status_code=404, detail="Segmento no encontrado")
    read = SegmentRead.model_validate(seg)
    read.contact_count = count_segment(seg.conditions, session)
    return read


@router.patch("/{segment_id}", response_model=SegmentRead)
def update_segment(
    segment_id: int,
    payload: SegmentUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
):
    seg = session.get(Segment, segment_id)
    if not seg:
        raise HTTPException(status_code=404, detail="Segmento no encontrado")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(seg, k, v)
    seg.updated_at = datetime.utcnow()
    session.add(seg)
    session.commit()
    session.refresh(seg)
    read = SegmentRead.model_validate(seg)
    read.contact_count = count_segment(seg.conditions, session)
    return read


@router.delete("/{segment_id}", status_code=204)
def delete_segment(
    segment_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
):
    seg = session.get(Segment, segment_id)
    if not seg:
        raise HTTPException(status_code=404, detail="Segmento no encontrado")
    session.delete(seg)
    session.commit()


@router.get("/{segment_id}/preview", response_model=List[ContactRead])
def preview_segment(
    segment_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    seg = session.get(Segment, segment_id)
    if not seg:
        raise HTTPException(status_code=404, detail="Segmento no encontrado")
    contacts = evaluate_segment(seg.conditions, session)
    return contacts[:20]
