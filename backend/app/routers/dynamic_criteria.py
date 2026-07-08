import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlmodel import Session

from app.core.deps import get_current_user, require_editor
from app.database import get_session
from app.models.dynamic_criteria import DynamicCriteriaRead, DynamicCriteriaUpdate
from app.models.user import User
from app.services.dynamic_criteria_store import CRITERIA_CATALOG, ensure_dynamic_criteria, list_criteria

router = APIRouter()


def _row_to_read(row) -> DynamicCriteriaRead:
    variables = row[3]
    if isinstance(variables, str):
        variables = json.loads(variables)
    config = row[4]
    if isinstance(config, str):
        config = json.loads(config)
    return DynamicCriteriaRead(
        criteria_key=row[0],
        name=row[1],
        description=row[2],
        variables=variables or [],
        config=config or {},
        updated_at=row[5],
    )


@router.get("", response_model=list[DynamicCriteriaRead])
def get_all_criteria(session: Session = Depends(get_session), _: User = Depends(get_current_user)):
    ensure_dynamic_criteria(session)
    rows = session.execute(
        text("""
            SELECT criteria_key, name, description, variables, config, updated_at
            FROM dynamic_criteria ORDER BY criteria_key
        """)
    ).fetchall()
    return [_row_to_read(r) for r in rows]


@router.get("/{criteria_key}", response_model=DynamicCriteriaRead)
def get_criteria(
    criteria_key: str,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    ensure_dynamic_criteria(session)
    row = session.execute(
        text("""
            SELECT criteria_key, name, description, variables, config, updated_at
            FROM dynamic_criteria WHERE criteria_key = :k
        """),
        {"k": criteria_key},
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Criterio no encontrado")
    return _row_to_read(row)


@router.put("/{criteria_key}", response_model=DynamicCriteriaRead)
def update_criteria(
    criteria_key: str,
    payload: DynamicCriteriaUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
):
    if criteria_key not in CRITERIA_CATALOG:
        raise HTTPException(status_code=404, detail="Criterio no encontrado")
    ensure_dynamic_criteria(session)
    now = datetime.utcnow()
    session.execute(
        text("""
            UPDATE dynamic_criteria
            SET config = CAST(:config AS jsonb), updated_at = :now
            WHERE criteria_key = :k
        """),
        {"k": criteria_key, "config": json.dumps(payload.config), "now": now},
    )
    session.commit()
    return get_criteria(criteria_key, session)
