from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.core.deps import get_current_user, require_editor, get_current_shop
from app.models.user import User
from app.models.shop import Shop
from app.models.segment import Segment, SegmentCreate, SegmentRead, SegmentUpdate
from app.services.segment_evaluator import count_segment, evaluate_segment
from app.models.contact import ContactRead

router = APIRouter()


@router.get("", response_model=List[SegmentRead])
def list_segments(session: Session = Depends(get_session), _: User = Depends(get_current_user), shop: Shop = Depends(get_current_shop)):
    segments = session.exec(
        select(Segment).where(Segment.shop_id == shop.id).order_by(Segment.created_at.desc())
    ).all()
    result = []
    for seg in segments:
        read = SegmentRead.model_validate(seg)
        try:
            read.contact_count = count_segment(seg.conditions, session, shop.id)
        except Exception:
            read.contact_count = 0
        result.append(read)
    return result


@router.post("", response_model=SegmentRead, status_code=201)
def create_segment(
    payload: SegmentCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_editor),
    shop: Shop = Depends(get_current_shop),
):
    seg = Segment(**payload.model_dump(), created_by=current_user.id, shop_id=shop.id)
    session.add(seg)
    session.commit()
    session.refresh(seg)
    read = SegmentRead.model_validate(seg)
    read.contact_count = count_segment(seg.conditions, session, shop.id)
    return read


@router.get("/{segment_id}", response_model=SegmentRead)
def get_segment(segment_id: int, session: Session = Depends(get_session), _: User = Depends(get_current_user), shop: Shop = Depends(get_current_shop)):
    seg = session.get(Segment, segment_id)
    if not seg or seg.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Segmento no encontrado")
    read = SegmentRead.model_validate(seg)
    read.contact_count = count_segment(seg.conditions, session, shop.id)
    return read


@router.patch("/{segment_id}", response_model=SegmentRead)
def update_segment(
    segment_id: int,
    payload: SegmentUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
    shop: Shop = Depends(get_current_shop),
):
    seg = session.get(Segment, segment_id)
    if not seg or seg.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Segmento no encontrado")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(seg, k, v)
    seg.updated_at = datetime.utcnow()
    session.add(seg)
    session.commit()
    session.refresh(seg)
    read = SegmentRead.model_validate(seg)
    read.contact_count = count_segment(seg.conditions, session, shop.id)
    return read


@router.delete("/{segment_id}", status_code=204)
def delete_segment(
    segment_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
    shop: Shop = Depends(get_current_shop),
):
    seg = session.get(Segment, segment_id)
    if not seg or seg.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Segmento no encontrado")
    session.delete(seg)
    session.commit()


@router.get("/{segment_id}/preview", response_model=List[ContactRead])
def preview_segment(
    segment_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
    shop: Shop = Depends(get_current_shop),
):
    seg = session.get(Segment, segment_id)
    if not seg or seg.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Segmento no encontrado")
    contacts = evaluate_segment(seg.conditions, session, shop.id)
    return contacts[:20]
