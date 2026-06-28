import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlmodel import Session

from app.core.deps import get_current_user, require_editor
from app.database import get_session
from app.models.favorite_block import FavoriteBlockCreate, FavoriteBlockRead, FavoriteBlockUpdate
from app.models.user import User
from app.services.favorite_blocks_seed import DEFAULT_FAVORITE_BLOCKS

router = APIRouter()


def ensure_favorite_blocks_table(session: Session) -> None:
    session.execute(text("""
        CREATE TABLE IF NOT EXISTS favorite_blocks (
            id SERIAL PRIMARY KEY,
            name VARCHAR NOT NULL,
            block_type VARCHAR NOT NULL,
            props JSONB NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """))
    session.commit()


def seed_default_favorite_blocks(session: Session) -> None:
    ensure_favorite_blocks_table(session)
    count = session.execute(text("SELECT COUNT(*) FROM favorite_blocks")).scalar()
    if count and int(count) > 0:
        return
    now = datetime.utcnow()
    for item in DEFAULT_FAVORITE_BLOCKS:
        session.execute(
            text("""
                INSERT INTO favorite_blocks (name, block_type, props, sort_order, created_at, updated_at)
                VALUES (:name, :type, CAST(:props AS jsonb), :sort_order, :now, :now)
            """),
            {
                "name": item["name"],
                "type": item["block_type"],
                "props": json.dumps(item["props"], ensure_ascii=False),
                "sort_order": item.get("sort_order", 0),
                "now": now,
            },
        )
    session.commit()


@router.get("", response_model=list[FavoriteBlockRead])
def list_favorite_blocks(session: Session = Depends(get_session), _: User = Depends(get_current_user)):
    seed_default_favorite_blocks(session)
    rows = session.execute(
        text("""
            SELECT id, name, block_type, props, sort_order, created_at, updated_at
            FROM favorite_blocks ORDER BY sort_order ASC, id ASC
        """)
    ).fetchall()
    return [
        FavoriteBlockRead(
            id=r[0], name=r[1], block_type=r[2], props=r[3] or {},
            sort_order=r[4], created_at=r[5], updated_at=r[6],
        )
        for r in rows
    ]


@router.post("", response_model=FavoriteBlockRead, status_code=201)
def create_favorite_block(
    payload: FavoriteBlockCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_editor),
):
    seed_default_favorite_blocks(session)
    now = datetime.utcnow()
    row = session.execute(
        text("""
            INSERT INTO favorite_blocks (name, block_type, props, sort_order, created_by, created_at, updated_at)
            VALUES (:name, :type, CAST(:props AS jsonb), :sort_order, :uid, :now, :now)
            RETURNING id, name, block_type, props, sort_order, created_at, updated_at
        """),
        {
            "name": payload.name,
            "type": payload.block_type,
            "props": json.dumps(payload.props, ensure_ascii=False),
            "sort_order": payload.sort_order,
            "uid": current_user.id,
            "now": now,
        },
    ).fetchone()
    session.commit()
    return FavoriteBlockRead(
        id=row[0], name=row[1], block_type=row[2], props=row[3] or {},
        sort_order=row[4], created_at=row[5], updated_at=row[6],
    )


@router.patch("/{block_id}", response_model=FavoriteBlockRead)
def update_favorite_block(
    block_id: int,
    payload: FavoriteBlockUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
):
    seed_default_favorite_blocks(session)
    existing = session.execute(
        text("SELECT 1 FROM favorite_blocks WHERE id = :id"), {"id": block_id}
    ).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Bloque favorito no encontrado")

    updates = []
    params: dict = {"id": block_id, "now": datetime.utcnow()}
    if payload.name is not None:
        updates.append("name = :name")
        params["name"] = payload.name
    if payload.block_type is not None:
        updates.append("block_type = :type")
        params["type"] = payload.block_type
    if payload.props is not None:
        updates.append("props = CAST(:props AS jsonb)")
        params["props"] = json.dumps(payload.props, ensure_ascii=False)
    if payload.sort_order is not None:
        updates.append("sort_order = :sort_order")
        params["sort_order"] = payload.sort_order
    if not updates:
        row = session.execute(
            text("SELECT id, name, block_type, props, sort_order, created_at, updated_at FROM favorite_blocks WHERE id = :id"),
            {"id": block_id},
        ).fetchone()
    else:
        updates.append("updated_at = :now")
        row = session.execute(
            text(f"""
                UPDATE favorite_blocks SET {', '.join(updates)} WHERE id = :id
                RETURNING id, name, block_type, props, sort_order, created_at, updated_at
            """),
            params,
        ).fetchone()
    session.commit()
    return FavoriteBlockRead(
        id=row[0], name=row[1], block_type=row[2], props=row[3] or {},
        sort_order=row[4], created_at=row[5], updated_at=row[6],
    )


@router.delete("/{block_id}", status_code=204)
def delete_favorite_block(
    block_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
):
    seed_default_favorite_blocks(session)
    result = session.execute(text("DELETE FROM favorite_blocks WHERE id = :id"), {"id": block_id})
    session.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Bloque favorito no encontrado")
