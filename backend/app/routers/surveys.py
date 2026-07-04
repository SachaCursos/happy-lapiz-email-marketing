from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session
from sqlalchemy import text
from app.database import get_session
from app.core.deps import get_current_user, require_admin
from app.models.user import User

router = APIRouter()

MIGRATIONS = [
    """CREATE TABLE IF NOT EXISTS surveys (
        id SERIAL PRIMARY KEY,
        name VARCHAR NOT NULL,
        slug VARCHAR UNIQUE NOT NULL,
        description TEXT,
        status VARCHAR NOT NULL DEFAULT 'active',
        created_by INTEGER,
        created_at TIMESTAMP NOT NULL DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS survey_questions (
        id SERIAL PRIMARY KEY,
        survey_id INTEGER NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
        question TEXT NOT NULL,
        type VARCHAR NOT NULL,
        options JSONB,
        required BOOLEAN NOT NULL DEFAULT TRUE,
        sort_order INTEGER NOT NULL DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS survey_responses (
        id SERIAL PRIMARY KEY,
        survey_id INTEGER NOT NULL REFERENCES surveys(id),
        respondent_email VARCHAR,
        submitted_at TIMESTAMP NOT NULL DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS survey_answers (
        id SERIAL PRIMARY KEY,
        response_id INTEGER NOT NULL REFERENCES survey_responses(id) ON DELETE CASCADE,
        question_id INTEGER NOT NULL REFERENCES survey_questions(id),
        answer_text TEXT,
        answer_number INTEGER,
        answer_choice VARCHAR
    )""",
]


def run_survey_migrations(session: Session):
    for sql in MIGRATIONS:
        try:
            session.execute(text(sql))
            session.commit()
        except Exception:
            session.rollback()


# ── Models ──────────────────────────────────────────────────────────────────

class QuestionIn(BaseModel):
    question: str
    type: str  # "text" | "multiple_choice" | "stars" | "nps"
    options: Optional[list[str]] = None
    required: bool = True
    sort_order: int = 0


class SurveyCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    questions: list[QuestionIn]


class AnswerIn(BaseModel):
    question_id: int
    answer_text: Optional[str] = None
    answer_number: Optional[int] = None
    answer_choice: Optional[str] = None


class SurveySubmit(BaseModel):
    respondent_email: Optional[str] = None
    answers: list[AnswerIn]


# ── Public endpoints (MUST be before /{survey_id} to avoid conflict) ─────────

@router.get("/public/{slug}")
def get_survey_public(slug: str, session: Session = Depends(get_session)):
    run_survey_migrations(session)
    survey = session.execute(
        text("SELECT id, name, slug, description, status FROM surveys WHERE slug = :slug"),
        {"slug": slug},
    ).fetchone()
    if not survey or survey[4] != "active":
        raise HTTPException(status_code=404, detail="Encuesta no encontrada")

    import json
    questions = session.execute(
        text("SELECT id, question, type, options, required, sort_order FROM survey_questions WHERE survey_id = :sid ORDER BY sort_order"),
        {"sid": survey[0]},
    ).fetchall()

    return {
        "id": survey[0],
        "name": survey[1],
        "slug": survey[2],
        "description": survey[3],
        "questions": [
            {
                "id": q[0], "question": q[1], "type": q[2],
                "options": json.loads(q[3]) if q[3] else None,
                "required": q[4],
                "sort_order": q[5],
            }
            for q in questions
        ],
    }


@router.post("/public/{slug}/submit")
def submit_survey(slug: str, body: SurveySubmit, session: Session = Depends(get_session)):
    survey = session.execute(
        text("SELECT id, status FROM surveys WHERE slug = :slug"), {"slug": slug}
    ).fetchone()
    if not survey or survey[1] != "active":
        raise HTTPException(status_code=404, detail="Encuesta no encontrada")

    row = session.execute(
        text("INSERT INTO survey_responses (survey_id, respondent_email) VALUES (:sid, :email) RETURNING id"),
        {"sid": survey[0], "email": body.respondent_email},
    ).fetchone()
    session.commit()
    response_id = row[0]

    for a in body.answers:
        session.execute(
            text("""
                INSERT INTO survey_answers (response_id, question_id, answer_text, answer_number, answer_choice)
                VALUES (:rid, :qid, :txt, :num, :choice)
            """),
            {
                "rid": response_id,
                "qid": a.question_id,
                "txt": a.answer_text,
                "num": a.answer_number,
                "choice": a.answer_choice,
            },
        )
    session.commit()
    return {"ok": True, "response_id": response_id}


# ── Admin endpoints ──────────────────────────────────────────────────────────

@router.post("")
def create_survey(
    body: SurveyCreate,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    run_survey_migrations(session)
    slug = body.slug.lower().strip().replace(" ", "-")
    existing = session.execute(
        text("SELECT id FROM surveys WHERE slug = :slug"), {"slug": slug}
    ).fetchone()
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe una encuesta con ese slug.")

    row = session.execute(
        text("""
            INSERT INTO surveys (name, slug, description)
            VALUES (:name, :slug, :desc)
            RETURNING id
        """),
        {"name": body.name, "slug": slug, "desc": body.description},
    ).fetchone()
    session.commit()
    survey_id = row[0]

    import json
    for q in body.questions:
        session.execute(
            text("""
                INSERT INTO survey_questions (survey_id, question, type, options, required, sort_order)
                VALUES (:sid, :q, :t, :opts, :req, :ord)
            """),
            {
                "sid": survey_id,
                "q": q.question,
                "t": q.type,
                "opts": json.dumps(q.options) if q.options else None,
                "req": q.required,
                "ord": q.sort_order,
            },
        )
    session.commit()
    return {"id": survey_id, "slug": slug}


@router.get("")
def list_surveys(
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    run_survey_migrations(session)
    rows = session.execute(text("""
        SELECT s.id, s.name, s.slug, s.description, s.status, s.created_at,
               COUNT(DISTINCT r.id) as response_count
        FROM surveys s
        LEFT JOIN survey_responses r ON r.survey_id = s.id
        GROUP BY s.id
        ORDER BY s.created_at DESC
    """)).fetchall()
    return [
        {
            "id": r[0], "name": r[1], "slug": r[2], "description": r[3],
            "status": r[4], "created_at": r[5], "response_count": r[6],
        }
        for r in rows
    ]


@router.get("/{survey_id}/responses")
def get_responses(
    survey_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    run_survey_migrations(session)
    survey = session.execute(
        text("SELECT id, name, slug FROM surveys WHERE id = :id"), {"id": survey_id}
    ).fetchone()
    if not survey:
        raise HTTPException(status_code=404, detail="Encuesta no encontrada")

    questions = session.execute(
        text("SELECT id, question, type, options, sort_order FROM survey_questions WHERE survey_id = :sid ORDER BY sort_order"),
        {"sid": survey_id},
    ).fetchall()

    responses = session.execute(
        text("SELECT id, respondent_email, submitted_at FROM survey_responses WHERE survey_id = :sid ORDER BY submitted_at DESC"),
        {"sid": survey_id},
    ).fetchall()

    import json
    response_ids = [r[0] for r in responses]
    answers_by_response: dict[int, list] = {r[0]: [] for r in responses}

    if response_ids:
        answers = session.execute(
            text("SELECT response_id, question_id, answer_text, answer_number, answer_choice FROM survey_answers WHERE response_id = ANY(:ids)"),
            {"ids": response_ids},
        ).fetchall()
        for a in answers:
            answers_by_response[a[0]].append({
                "question_id": a[1],
                "answer_text": a[2],
                "answer_number": a[3],
                "answer_choice": a[4],
            })

    return {
        "survey": {"id": survey[0], "name": survey[1], "slug": survey[2]},
        "questions": [
            {
                "id": q[0], "question": q[1], "type": q[2],
                "options": json.loads(q[3]) if q[3] else None,
                "sort_order": q[4],
            }
            for q in questions
        ],
        "responses": [
            {
                "id": r[0],
                "email": r[1],
                "submitted_at": r[2],
                "answers": answers_by_response[r[0]],
            }
            for r in responses
        ],
    }


@router.get("/{survey_id}")
def get_survey(
    survey_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    run_survey_migrations(session)
    import json
    survey = session.execute(
        text("SELECT id, name, slug, description, status FROM surveys WHERE id = :id"),
        {"id": survey_id},
    ).fetchone()
    if not survey:
        raise HTTPException(status_code=404, detail="Encuesta no encontrada")
    questions = session.execute(
        text("SELECT id, question, type, options, required, sort_order FROM survey_questions WHERE survey_id = :sid ORDER BY sort_order"),
        {"sid": survey_id},
    ).fetchall()
    return {
        "id": survey[0], "name": survey[1], "slug": survey[2],
        "description": survey[3], "status": survey[4],
        "questions": [
            {
                "id": q[0], "question": q[1], "type": q[2],
                "options": json.loads(q[3]) if q[3] else None,
                "required": q[4], "sort_order": q[5],
            }
            for q in questions
        ],
    }


@router.put("/{survey_id}")
def update_survey(
    survey_id: int,
    body: SurveyCreate,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    run_survey_migrations(session)
    import json
    survey = session.execute(
        text("SELECT id FROM surveys WHERE id = :id"), {"id": survey_id}
    ).fetchone()
    if not survey:
        raise HTTPException(status_code=404, detail="Encuesta no encontrada")

    slug = body.slug.lower().strip().replace(" ", "-")
    conflict = session.execute(
        text("SELECT id FROM surveys WHERE slug = :slug AND id != :id"),
        {"slug": slug, "id": survey_id},
    ).fetchone()
    if conflict:
        raise HTTPException(status_code=400, detail="Ya existe otra encuesta con ese slug.")

    session.execute(
        text("UPDATE surveys SET name = :name, slug = :slug, description = :desc WHERE id = :id"),
        {"name": body.name, "slug": slug, "desc": body.description, "id": survey_id},
    )
    session.execute(text("DELETE FROM survey_questions WHERE survey_id = :sid"), {"sid": survey_id})
    for q in body.questions:
        session.execute(
            text("""
                INSERT INTO survey_questions (survey_id, question, type, options, required, sort_order)
                VALUES (:sid, :q, :t, :opts, :req, :ord)
            """),
            {
                "sid": survey_id, "q": q.question, "t": q.type,
                "opts": json.dumps(q.options) if q.options else None,
                "req": q.required, "ord": q.sort_order,
            },
        )
    session.commit()
    return {"id": survey_id, "slug": slug}


@router.delete("/{survey_id}")
def delete_survey(
    survey_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    run_survey_migrations(session)
    session.execute(text("DELETE FROM surveys WHERE id = :id"), {"id": survey_id})
    session.commit()
    return {"ok": True}
