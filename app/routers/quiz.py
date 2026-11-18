"""5-minute timed QR quiz endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.config import UPLOADS_DIR
from app.database import get_db
from app.models import QuizQuestion
from app.schemas import QuizSubmitRequest, QuizTriggerRequest
from app.services.quiz_service import quiz_manager
from app.services.ws_manager import ws_manager

router = APIRouter(prefix="/api/quiz", tags=["Quiz"])


@router.post("/upload-excel")
async def upload_quiz_excel(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """Upload and parse an .xlsx question bank into SQLite."""
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    target_path = UPLOADS_DIR / (file.filename or "questions.xlsx")
    target_path.write_bytes(await file.read())

    questions = quiz_manager.load_questions_from_excel(db, target_path, session_id=session_id)
    return {
        "loaded_count": len(questions),
        "questions": [
            {
                "id": q.id,
                "question_text": q.question_text,
                "option_a": q.option_a,
                "option_b": q.option_b,
                "option_c": q.option_c,
                "option_d": q.option_d,
                "is_used": q.is_used,
            }
            for q in questions
        ],
    }


@router.get("/questions")
def list_questions(db: Session = Depends(get_db)) -> dict:
    """List loaded questions and report whether the question bank is exhausted."""
    questions = db.query(QuizQuestion).order_by(QuizQuestion.id.asc()).all()
    remaining = sum(1 for q in questions if not q.is_used)
    return {
        "total": len(questions),
        "remaining": remaining,
        "questions_exhausted": len(questions) > 0 and remaining == 0,
        "questions": [
            {
                "id": q.id,
                "question_text": q.question_text,
                "option_a": q.option_a,
                "option_b": q.option_b,
                "option_c": q.option_c,
                "option_d": q.option_d,
                "is_used": q.is_used,
            }
            for q in questions
        ],
    }


@router.post("/trigger")
def trigger_question(payload: QuizTriggerRequest, db: Session = Depends(get_db)) -> dict:
    """Activate a question with a 5-minute expiring QR token."""
    return quiz_manager.trigger_question(
        db=db,
        session_id=payload.session_id,
        question_id=payload.question_id,
        lecturer_id=payload.lecturer_id,
    )


@router.get("/token/{token}")
def inspect_token(token: str, db: Session = Depends(get_db)) -> dict:
    """Fetch active question details for the student mobile view."""
    return quiz_manager.get_token_question(db, token)


@router.post("/submit")
async def submit_quiz_answer(payload: QuizSubmitRequest, db: Session = Depends(get_db)) -> dict:
    """Submit a student answer within the 5-minute window and broadcast QUIZ_UPDATE."""
    result = quiz_manager.submit_answer(
        db=db,
        token=payload.token,
        student_id=payload.student_id,
        full_name=payload.full_name,
        selected_option=payload.selected_option,
    )
    await ws_manager.broadcast_event(
        result["session_id"],
        "QUIZ_UPDATE",
        {
            "total_responses": result["total_responses"],
            "option_counts": result["option_counts"],
        },
    )
    return result
