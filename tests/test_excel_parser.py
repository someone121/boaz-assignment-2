"""Unit tests for Excel (.xlsx) quiz question bank parser."""

from fastapi import HTTPException
import openpyxl
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.services.quiz_service import QuizSessionManager


def _make_in_memory_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


def test_valid_excel_parsing(tmp_path):
    """Valid .xlsx workbook populates quiz_questions accurately."""
    xlsx_path = tmp_path / "questions.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Question", "Option A", "Option B", "Option C", "Option D", "Correct"])
    ws.append(["What does SRP stand for?", "Single Responsibility", "Static Runtime", "Sync Protocol", "None", "A"])
    ws.append(["Is SQLite serverless?", "True", "False", None, None, "A"])
    wb.save(xlsx_path)

    db = _make_in_memory_db()
    manager = QuizSessionManager()
    loaded = manager.load_questions_from_excel(db, xlsx_path)

    assert len(loaded) == 2
    assert loaded[0].question_text == "What does SRP stand for?"
    assert loaded[0].correct_option == "A"
    assert loaded[1].option_c is None
    db.close()


def test_empty_excel_raises_400(tmp_path):
    """Empty .xlsx workbook raises HTTP 400."""
    xlsx_path = tmp_path / "empty.xlsx"
    wb = openpyxl.Workbook()
    wb.save(xlsx_path)

    db = _make_in_memory_db()
    manager = QuizSessionManager()
    with pytest.raises(HTTPException) as exc:
        manager.load_questions_from_excel(db, xlsx_path)
    assert exc.value.status_code == 400
    db.close()
