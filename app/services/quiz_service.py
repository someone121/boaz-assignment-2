"""Quiz management service: Excel ingestion, 5-minute (300s) token gating, and telemetry."""

from datetime import datetime, timedelta
from pathlib import Path
import secrets
from typing import Optional

from fastapi import HTTPException, status
import openpyxl
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    ActiveQuestionToken,
    QuizQuestion,
    QuizSubmission,
    Student,
    utcnow,
)
from app.services.attendance_service import attendance_manager


class TimedTokenManager:
    """Issues and strictly validates 300-second (5-minute) quiz access tokens."""

    def __init__(self, ttl_seconds: int = settings.QUIZ_TOKEN_TTL_SECONDS) -> None:
        self.ttl = timedelta(seconds=ttl_seconds)

    def build_token_record(
        self,
        session_id: str,
        question_id: int,
        lecturer_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> ActiveQuestionToken:
        """Create a cryptographically random token expiring in exactly 5 minutes."""
        issued_at = now or utcnow()
        token_value = f"q{question_id}_{secrets.token_urlsafe(12)}"
        return ActiveQuestionToken(
            token=token_value,
            session_id=session_id,
            question_id=question_id,
            lecturer_id=lecturer_id,
            created_at=issued_at,
            expires_at=issued_at + self.ttl,
            is_active=True,
        )

    def is_valid(self, token_row: ActiveQuestionToken, now: Optional[datetime] = None) -> bool:
        """Return True only if the token is active and within its 300-second window."""
        current = now or utcnow()
        return bool(token_row.is_active and current <= token_row.expires_at)


class QuizSessionManager:
    """Handles Excel question banks, dynamic QR triggers, and live student submissions."""

    def __init__(self) -> None:
        self.token_manager = TimedTokenManager()

    def load_questions_from_excel(
        self, db: Session, file_path: Path, session_id: Optional[str] = None
    ) -> list[QuizQuestion]:
        """Parse an uploaded .xlsx question bank and store questions in SQLite."""
        workbook = openpyxl.load_workbook(file_path, data_only=True)
        sheet = workbook.active
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded Excel workbook is empty.",
            )

        headers = [str(cell).strip().lower() if cell is not None else "" for cell in rows[0]]
        has_header = any(h in {"question", "question_text", "prompt"} for h in headers)
        data_rows = rows[1:] if has_header else rows

        created: list[QuizQuestion] = []
        for row in data_rows:
            if not row or not row[0]:
                continue
            q_text = str(row[0]).strip()
            opt_a = str(row[1]).strip() if len(row) > 1 and row[1] is not None else "True"
            opt_b = str(row[2]).strip() if len(row) > 2 and row[2] is not None else "False"
            opt_c = str(row[3]).strip() if len(row) > 3 and row[3] is not None else None
            opt_d = str(row[4]).strip() if len(row) > 4 and row[4] is not None else None
            correct = str(row[5]).strip().upper() if len(row) > 5 and row[5] is not None else "A"

            question = QuizQuestion(
                session_id=session_id,
                question_text=q_text,
                option_a=opt_a,
                option_b=opt_b,
                option_c=opt_c,
                option_d=opt_d,
                correct_option=correct[:2],
                is_used=False,
            )
            db.add(question)
            created.append(question)

        if not created:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid question rows found in Excel file.",
            )

        db.commit()
        for q in created:
            db.refresh(q)
        return created

    def trigger_question(
        self,
        db: Session,
        session_id: str,
        question_id: Optional[int] = None,
        lecturer_id: Optional[str] = None,
    ) -> dict:
        """Activate a question for 5 minutes and return its QR URL + remaining bank status."""
        if question_id is not None:
            question = db.get(QuizQuestion, question_id)
        else:
            question = (
                db.query(QuizQuestion)
                .filter(QuizQuestion.is_used.is_(False))
                .order_by(QuizQuestion.id.asc())
                .first()
            )

        if question is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No unused questions remaining in the uploaded Excel bank.",
            )

        question.is_used = True
        token_row = self.token_manager.build_token_record(
            session_id=session_id,
            question_id=question.id,
            lecturer_id=lecturer_id,
        )
        db.add(token_row)
        db.commit()
        db.refresh(token_row)

        remaining_count = (
            db.query(QuizQuestion).filter(QuizQuestion.is_used.is_(False)).count()
        )
        return {
            "token": token_row.token,
            "session_id": session_id,
            "question_id": question.id,
            "question_text": question.question_text,
            "options": {
                "A": question.option_a,
                "B": question.option_b,
                "C": question.option_c,
                "D": question.option_d,
            },
            "expires_at": token_row.expires_at.isoformat(),
            "ttl_seconds": settings.QUIZ_TOKEN_TTL_SECONDS,
            "qr_path": f"/s/{token_row.token}",
            "remaining_questions": remaining_count,
            "questions_exhausted": remaining_count == 0,
        }

    def get_token_question(self, db: Session, token: str) -> dict:
        """Fetch question metadata for a student QR landing page, enforcing 5-min expiry."""
        token_row = db.get(ActiveQuestionToken, token)
        if token_row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz token not found.")
        if not self.token_manager.is_valid(token_row):
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="The 5-minute submission window has closed.",
            )

        question = token_row.question
        seconds_left = max(0, int((token_row.expires_at - utcnow()).total_seconds()))
        return {
            "token": token_row.token,
            "session_id": token_row.session_id,
            "question_id": question.id,
            "question_text": question.question_text,
            "options": {
                k: v
                for k, v in {
                    "A": question.option_a,
                    "B": question.option_b,
                    "C": question.option_c,
                    "D": question.option_d,
                }.items()
                if v
            },
            "seconds_remaining": seconds_left,
        }

    def submit_answer(
        self,
        db: Session,
        token: str,
        student_id: str,
        full_name: str,
        selected_option: str,
    ) -> dict:
        """Record a student's quiz answer if within the 5-minute window and compute live counts."""
        token_row = db.get(ActiveQuestionToken, token)
        if token_row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz token not found.")
        if not self.token_manager.is_valid(token_row):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The 5-minute submission window has closed.",
            )

        student = db.get(Student, student_id)
        if student is None:
            student = Student(student_id=student_id, full_name=full_name)
            db.add(student)
            db.flush()

        normalized = selected_option.strip().upper()[:2]
        question = token_row.question
        is_correct = normalized == question.correct_option.strip().upper()

        submission = QuizSubmission(
            token=token,
            student_id=student_id,
            selected_option=normalized,
            submitted_at=utcnow(),
            is_correct=is_correct,
        )
        db.add(submission)
        db.commit()

        # Dual-factor correlation with active attendance session.
        attendance_manager.link_student_to_session(db, token_row.session_id, student_id)

        all_subs = (
            db.query(QuizSubmission).filter(QuizSubmission.token == token).all()
        )
        option_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
        for sub in all_subs:
            option_counts[sub.selected_option] = option_counts.get(sub.selected_option, 0) + 1

        return {
            "status": "recorded",
            "session_id": token_row.session_id,
            "is_correct": is_correct,
            "total_responses": len(all_subs),
            "option_counts": option_counts,
        }


quiz_manager = QuizSessionManager()
